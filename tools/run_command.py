import os
import signal
import subprocess

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    # `resource` is POSIX-only. On Windows the timeout and working-directory
    # jail still apply; CPU/memory limits are skipped.
    _HAS_RESOURCE = False

DEFAULT_TIMEOUT_SECONDS = 30
# Hard ceiling. The model can lower the timeout via the tool parameter but
# never raise it past this, otherwise it could bypass the sandbox by simply
# asking for a bigger number.
MAX_TIMEOUT_SECONDS = 45
MAX_CPU_SECONDS = 10
MAX_MEMORY_BYTES = 512 * 1024 * 1024
MAX_OUTPUT_CHARS = 20_000


def _apply_resource_limits():
    """
    Runs in the child between fork() and exec(), so the limits apply to the
    command and not to this program.

    Each limit is set in its own try/except. RLIMIT_AS is rejected on macOS
    ("current limit exceeds maximum limit"), and if that exception escaped,
    subprocess would report the whole preexec_fn as failed and the command
    would never run. An unsupported limit is skipped instead.

    RLIMIT_NPROC is deliberately not set. It counts every process owned by
    the *user*, not just this command's subtree, so a small value makes the
    shell unable to fork at all -- pipelines and `a && b` fail with
    "fork: Resource temporarily unavailable" while single commands still
    work because sh exec()s them directly.
    """
    for limit_type, values in (
        (resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS)),
        (resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES)),
    ):
        try:
            resource.setrlimit(limit_type, values)
        except (ValueError, OSError):
            pass


def _kill_process_group(proc: subprocess.Popen) -> None:
    if hasattr(os, "killpg"):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        proc.kill()


def _is_within_directory(base_dir: str, target_dir: str) -> bool:
    """True if target_dir is base_dir itself or a subdirectory of it."""
    base_dir = os.path.realpath(base_dir)
    target_dir = os.path.realpath(target_dir)
    return target_dir == base_dir or target_dir.startswith(base_dir + os.sep)


def run_command(
    command: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    workdir: str | None = None,
) -> str:
    """
    Execute a shell command and return its exit code and combined output.

    Sandboxing applied:
      - timeout: the command and every process it spawned are killed after
        `timeout` seconds (clamped to MAX_TIMEOUT_SECONDS).
      - resource limits: CPU time and address space are capped for the child
        (POSIX only; see _apply_resource_limits).
      - working-directory jail: cwd must be the repository root or inside it.
      - output truncation: stdout/stderr are capped at MAX_OUTPUT_CHARS so a
        runaway command can't flood the model's context.

    This is process-level sandboxing, not a security boundary: the command
    can still touch any path the user can, and network access is
    unrestricted.
    """
    timeout = min(max(timeout, 1), MAX_TIMEOUT_SECONDS)

    repo_root = os.getcwd()
    resolved_workdir = os.path.realpath(workdir) if workdir else repo_root

    if not _is_within_directory(repo_root, resolved_workdir):
        return (
            f"Error: workdir '{workdir}' resolves outside the allowed "
            f"directory '{repo_root}'. Refusing to execute."
        )

    try:
        # start_new_session puts the shell and everything it spawns in their
        # own process group, so a timeout can kill the whole tree. Killing
        # just the shell would leave e.g. `sleep 100 | cat` running after
        # we report the timeout.
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=resolved_workdir,
            start_new_session=True,
            preexec_fn=_apply_resource_limits if _HAS_RESOURCE else None,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            proc.communicate()
            return f"Error: Command timed out after {timeout} seconds."

        output_parts = []
        if stdout:
            output_parts.append(stdout.strip())
        if stderr:
            output_parts.append(stderr.strip())

        output_str = "\n".join(output_parts)
        if len(output_str) > MAX_OUTPUT_CHARS:
            output_str = (
                output_str[:MAX_OUTPUT_CHARS]
                + f"\n... [truncated, {len(output_str) - MAX_OUTPUT_CHARS} more characters]"
            )

        if output_str:
            return f"Exit code: {proc.returncode}\n{output_str}"
        return f"Exit code: {proc.returncode}"

    except Exception as e:
        return f"Error executing command: {e}"
