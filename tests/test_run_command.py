import os
import shutil
import subprocess
import time

import pytest

from tools.run_command import run_command, MAX_OUTPUT_CHARS

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX shell semantics")


def test_pipelines_and_compound_commands_can_fork():
    # Regression: a per-user RLIMIT_NPROC used to make the sandboxed shell
    # unable to fork, so anything beyond a single command failed with
    # "fork: Resource temporarily unavailable".
    assert run_command("echo a | cat && echo b") == "Exit code: 0\na\nb"


def test_timeout_kills_child_processes_too():
    marker = f"sleep 300 #agent-test-{os.getpid()}"
    start = time.time()
    result = run_command(f"{marker} | cat", timeout=1)
    assert "timed out" in result
    assert time.time() - start < 5

    # The shell was killed; the `sleep` it spawned must not outlive it.
    time.sleep(0.2)
    leftover = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout
    if leftover:
        subprocess.run(["pkill", "-f", marker])
    assert leftover == ""


def test_workdir_outside_repo_is_refused():
    result = run_command("ls", workdir="/")
    assert "Refusing to execute" in result


def test_output_is_truncated():
    result = run_command(f"head -c {MAX_OUTPUT_CHARS * 3} /dev/zero | tr '\\0' x")
    assert "truncated" in result
    assert len(result) < MAX_OUTPUT_CHARS + 200


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
def test_search_query_starting_with_dash(tmp_path):
    from tools.search_code import search_code

    f = tmp_path / "a.txt"
    f.write_text("use --verbose here\n")

    result = search_code("--verbose", str(tmp_path))

    assert "a.txt:1:" in result
