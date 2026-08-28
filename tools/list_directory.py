import os

# Directories that are almost never useful to an agent exploring source code,
# and tend to flood output with noise (compiled artifacts, VCS internals,
# dependency trees). Skipped by default; pass include_noise=True to see them.
_NOISE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache"}


def list_directory(path: str = ".", include_noise: bool = False) -> str:
    """
    List the immediate contents of a directory (non-recursive).

    Directories are shown with a trailing '/' to distinguish them from files.
    By default, common noise directories (__pycache__, .git, .venv, etc.) are
    filtered out, since they rarely matter when exploring a codebase and just
    add clutter. Set include_noise=True to see everything.

    This is the tool to reach for when you need to know what files exist in a
    directory -- prefer it over run_command's `ls` (loses sandboxing benefits
    and produces unstructured output) and over search_code (which requires a
    text pattern to search for and isn't meant for enumeration).
    """
    try:
        entries = sorted(os.listdir(path))
    except FileNotFoundError:
        return f"Directory not found: {path}"
    except NotADirectoryError:
        return f"Not a directory: {path}"
    except OSError as e:
        return f"Error listing directory '{path}': {e}"

    lines = []
    for entry in entries:
        if not include_noise and entry in _NOISE_DIRS:
            continue
        full_path = os.path.join(path, entry)
        lines.append(entry + "/" if os.path.isdir(full_path) else entry)

    if not lines:
        return f"'{path}' is empty (or contains only filtered noise directories)."

    return "\n".join(lines)