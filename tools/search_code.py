import subprocess


def search_code(query: str, path: str = ".") -> str:
    """Search for a pattern with ripgrep. Returns path:line_number:line matches."""
    # `-e` so a query beginning with '-' is treated as a pattern, not a flag.
    cmd = ["rg", "-n", "-H", "--no-heading", "--color=never", "-e", query, path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return "ripgrep (rg) command not found. Please install ripgrep."
    except Exception as e:
        return f"Error executing search_code: {e}"

    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return f"No matches found for query: '{query}'"
    error_msg = result.stderr.strip() or f"Search exited with code {result.returncode}"
    return f"Error executing search: {error_msg}"
