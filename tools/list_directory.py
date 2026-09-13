import os

# Skipped by default so a recursive listing doesn't walk into .venv or .git.
_NOISE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache"}


def list_directory(path: str = ".", include_noise: bool = False, recursive: bool = False) -> str:
    """
    List a directory. Non-recursive by default (directories get a trailing
    '/'); with recursive=True, returns every file path under `path`.
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