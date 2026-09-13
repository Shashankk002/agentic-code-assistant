import os


def _is_within_directory(base_dir: str, target_path: str) -> bool:
    """True if target_path resolves to base_dir itself or something inside it."""
    base_dir = os.path.realpath(base_dir)
    target_path = os.path.realpath(target_path)
    return target_path == base_dir or target_path.startswith(base_dir + os.sep)


def write_file(file_path: str, content: str, overwrite: bool = True) -> str:
    """
    Create a file (parent directories included) or overwrite an existing one.

    Refuses to write outside the current working directory, matching the
    workdir jail in run_command. With overwrite=False, an existing file is
    left untouched and an error is returned.
    """
    repo_root = os.getcwd()
    resolved_path = os.path.realpath(file_path)

    if not _is_within_directory(repo_root, resolved_path):
        return (
            f"Error: '{file_path}' resolves outside the allowed directory "
            f"'{repo_root}'. Refusing to write."
        )

    if not overwrite and os.path.exists(resolved_path):
        return (
            f"Error: {file_path} already exists and overwrite=False. "
            "Use edit_file to modify an existing file instead."
        )

    try:
        parent_dir = os.path.dirname(resolved_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(resolved_path, "w") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {file_path}."

    except OSError as e:
        return f"Error writing to file '{file_path}': {e}"