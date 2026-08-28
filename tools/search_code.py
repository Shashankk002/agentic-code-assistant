import subprocess


def search_code(query: str, path: str = ".") -> str:
    """Search for a query pattern across files using ripgrep (rg).

    Returns concise matches in format: path:line_number:line_content
    """
    cmd = ["rg", "-n", "-H", "--no-heading", "--color=never", query, path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return f"No matches found for query: '{query}'"
        else:
            error_msg = result.stderr.strip() or f"Search exited with code {result.returncode}"
            return f"Error executing search: {error_msg}"
    except FileNotFoundError:
        return "ripgrep (rg) command not found. Please install ripgrep."
    except Exception as e:
        return f"Error executing search_code: {e}"
