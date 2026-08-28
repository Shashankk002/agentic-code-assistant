def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """Edit an existing file by replacing a unique occurrence of old_text with new_text."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except OSError as e:
        return f"Error reading file '{file_path}': {e}"

    count = content.count(old_text)

    if count == 0:
        return f"Error: 'old_text' not found in {file_path}."

    if count > 1:
        return (
            f"Error: 'old_text' occurs {count} times in {file_path}. "
            "Please provide a unique snippet with more surrounding context."
        )

    updated_content = content.replace(old_text, new_text, 1)

    try:
        with open(file_path, "w") as f:
            f.write(updated_content)
        return f"Successfully updated {file_path}."
    except OSError as e:
        return f"Error writing to file '{file_path}': {e}"
