import os

# Directories that are almost never useful to an agent exploring source code,
# and tend to flood output with noise (compiled artifacts, VCS internals,
# dependency trees). Skipped by default; pass include_noise=True to see them.
_NOISE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache"}


def list_directory(path: str = ".", include_noise: bool = False, recursive: bool = False) -> str:
    """
    List a directory's contents. Non-recursive by default; pass recursive=True
    to walk the full tree in one call instead of listing one level at a time.

    Directories are shown with a trailing '/'. By default, common noise
    directories (__pycache__, .git, .venv, etc.) are filtered out -- this
    matters even more with recursive=True, since without it a recursive
    listing would walk into installed packages inside .venv and flood the
    output with thousands of irrelevant lines.

    This is the tool to reach for when you need to know what files exist --
    prefer it over run_command's `ls`/`find` (loses sandboxing benefits, and
    a hand-written os.walk script risks forgetting to exclude .venv/.git) and
    over search_code (which requires a text pattern and isn't for enumeration).
    """
    if not recursive:
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

    # Recursive case
    if not os.path.isdir(path):
        return f"Directory not found: {path}"

    lines = []
    for root, dirs, files in os.walk(path):
        if not include_noise:
            dirs[:] = [d for d in dirs if d not in _NOISE_DIRS]
        rel_root = os.path.relpath(root, path)
        for f in sorted(files):
            rel_path = f if rel_root == "." else os.path.join(rel_root, f)
            lines.append(rel_path)

    if not lines:
        return f"'{path}' is empty (or contains only filtered noise directories)."
    return "\n".join(sorted(lines))