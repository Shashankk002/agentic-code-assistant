def read_file(file_path):
    try:
        with open(file_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except OSError as e:
        return f"Error reading file: {e}"