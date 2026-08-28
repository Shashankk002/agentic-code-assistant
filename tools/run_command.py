import os
import subprocess

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    # `resource` is POSIX-only (no Windows support). Fall back gracefully
    # instead of crashing on import for Windows users.
    _HAS_RESOURCE = False

# --- Sandbox limits (tune these as needed) ---
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 45      # hard ceiling — no caller (including the model
                               # itself, via the timeout tool parameter) can
                               # request more than this. Without a ceiling,
                               # a helpful-but-wrong model can simply ask for
                               # a bigger timeout and bypass the sandbox.
MAX_CPU_SECONDS = 10          # hard CPU time cap for the child process
MAX_MEMORY_BYTES = 512 * 1024 * 1024   # 512 MB address space cap
MAX_OUTPUT_CHARS = 20_000     # truncate huge stdout/stderr so it can't flood context
MAX_PROCESSES = 32            # cap on forked/spawned subprocesses (fork bombs)


def _apply_resource_limits():
    """
    Runs in the child process right after fork(), before exec().
    This is what actually enforces CPU/memory/process caps on the command —
    the parent process (this Python program) is unaffected.

    POSIX only. On Windows this is skipped (see _HAS_RESOURCE above); the
    timeout and working-directory jail still apply there.

    Each limit is applied independently and failures are swallowed rather
    than raised: RLIMIT_AS (memory) and RLIMIT_NPROC (process count) are
    known to be unsupported or unreliable on macOS's kernel, even though the
    constants exist in the `resource` module. If any one of these raised
    inside a single unguarded block, subprocess would report the whole
    preexec_fn as failed and the command would never run at all -- which is
    exactly what happened here. Setting each limit in its own try/except
    means an unsupported limit is silently skipped instead of blocking
    otherwise-harmless commands like `sleep 40`.
    """
    for limit_type, values in (
        (resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS)),
        (resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES)),
        # RLIMIT_NPROC caps how many processes the resulting UID can have,
        # a cheap guard against fork bombs like `:(){ :|:& };:` -- where supported.
        (resource.RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES)),
    ):
        try:
            resource.setrlimit(limit_type, values)
        except (ValueError, OSError):
            # Not supported/enforceable on this platform -- skip it rather
            # than aborting the whole command.
            pass


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
    Execute a shell command with sandboxing, and return exit code and output.

    Sandboxing applied:
      - timeout: the command is killed if it runs longer than `timeout` seconds
        (this was previously broken — TimeoutExpired was caught but never
        actually triggered, since no timeout was passed to subprocess.run).
      - resource limits: CPU time, memory, and process count are capped for
        the child process (POSIX only).
      - working-directory jail: the command's cwd is restricted to the
        repository root (or `workdir`, if given) and cannot be pointed
        outside of it.
      - output truncation: stdout/stderr are capped so a runaway command
        can't blow up the agent's context window.

    NOT protected against by this alone: this is process-level sandboxing,
    not a real security boundary. A command can still read/write/delete any
    file the resolved workdir has access to, and network access is
    unrestricted. For a stronger boundary, run inside a container (see notes
    in PROJECT_GUIDE.md).
    """
    # Clamp regardless of what was requested. This line is the whole point:
    # the timeout parameter exists so a caller can *lower* the limit for
    # commands expected to be fast, not raise it past what the sandbox allows.
    timeout = min(max(timeout, 1), MAX_TIMEOUT_SECONDS)

    repo_root = os.getcwd()
    resolved_workdir = os.path.realpath(workdir) if workdir else repo_root

    if not _is_within_directory(repo_root, resolved_workdir):
        return (
            f"Error: workdir '{workdir}' resolves outside the allowed "
            f"directory '{repo_root}'. Refusing to execute."
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=resolved_workdir,
            timeout=timeout,
            check=False,
            preexec_fn=_apply_resource_limits if _HAS_RESOURCE else None,
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout.strip())
        if result.stderr:
            output_parts.append(result.stderr.strip())

        output_str = "\n".join(output_parts)
        if len(output_str) > MAX_OUTPUT_CHARS:
            output_str = (
                output_str[:MAX_OUTPUT_CHARS]
                + f"\n... [truncated, {len(output_str) - MAX_OUTPUT_CHARS} more characters]"
            )

        if output_str:
            return f"Exit code: {result.returncode}\n{output_str}"
        return f"Exit code: {result.returncode}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {e}"