READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Read and return the contents of a file.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read."
            }
        },
        "required": ["file_path"]
    }
}

SEARCH_CODE_SCHEMA = {
    "name": "search_code",
    "description": "Search for a query pattern across files using ripgrep (rg). Returns concise matching file paths, line numbers, and matching lines.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search pattern or keyword to look for."
            },
            "path": {
                "type": "string",
                "description": "Optional directory or file path to search within. Defaults to current directory."
            }
        },
        "required": ["query"]
    }
}

EDIT_FILE_SCHEMA = {
    "name": "edit_file",
    "description": "Edit an existing file by replacing a unique occurrence of old_text with new_text.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit."
            },
            "old_text": {
                "type": "string",
                "description": "The exact existing text to be replaced (must occur exactly once in the file)."
            },
            "new_text": {
                "type": "string",
                "description": "The new replacement text."
            }
        },
        "required": ["file_path", "old_text", "new_text"]
    }
}

RUN_COMMAND_SCHEMA = {
    "name": "run_command",
    "description": (
        "Execute a shell command in the repository working directory, capturing "
        "stdout, stderr, and exit code. The command runs in a sandboxed subprocess "
        "with a timeout and resource limits — long-running or resource-heavy "
        "commands will be killed automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command string to execute."
            },
            "timeout": {
                "type": "integer",
                "description": (
                    "Maximum seconds to let the command run before it is killed. "
                    "Defaults to 30. Increase only for commands you expect to be slow "
                    "(e.g. installing dependencies)."
                )
            }
        },
        "required": ["command"]
    }
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": (
        "Create a new file with the given content, or fully overwrite an existing "
        "one. Use this to create files from scratch. To make a targeted change to "
        "part of an existing file, use edit_file instead -- write_file replaces the "
        "whole file's contents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file to create or overwrite."
            },
            "content": {
                "type": "string",
                "description": "The full content to write to the file."
            },
            "overwrite": {
                "type": "boolean",
                "description": (
                    "If false, refuses to write when the file already exists "
                    "(use edit_file instead for existing files). Defaults to true."
                )
            }
        },
        "required": ["file_path", "content"]
    }
}


LIST_DIRECTORY_SCHEMA = {
    "name": "list_directory",
    "description": (
        "List the immediate (non-recursive) contents of a directory. Directories "
        "are shown with a trailing '/'. Common noise directories (__pycache__, "
        ".git, .venv, node_modules) are filtered out by default. Use this to "
        "discover what files exist before reading or editing them -- do not use "
        "run_command's ls or search_code for this."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list. Defaults to the current directory."
            },
            "include_noise": {
                "type": "boolean",
                "description": (
                    "If true, includes normally-filtered directories like "
                    "__pycache__ and .git. Defaults to false."
                )
            }
        },
        "required": []
    }
}