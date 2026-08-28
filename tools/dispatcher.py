from tools.registry import ToolRegistry
from tools.read_file import read_file
from tools.search_code import search_code
from tools.edit_file import edit_file
from tools.run_command import run_command
from tools.write_file import write_file
from tools.list_directory import list_directory
from tools.schemas import (
    READ_FILE_SCHEMA,
    SEARCH_CODE_SCHEMA,
    EDIT_FILE_SCHEMA,
    RUN_COMMAND_SCHEMA,
    WRITE_FILE_SCHEMA,
    LIST_DIRECTORY_SCHEMA,
)

default_registry = ToolRegistry()
default_registry.register("read_file", read_file, READ_FILE_SCHEMA)
default_registry.register("search_code", search_code, SEARCH_CODE_SCHEMA)
default_registry.register("edit_file", edit_file, EDIT_FILE_SCHEMA)
default_registry.register("run_command", run_command, RUN_COMMAND_SCHEMA)
default_registry.register("write_file", write_file, WRITE_FILE_SCHEMA)
default_registry.register("list_directory", list_directory, LIST_DIRECTORY_SCHEMA)



def execute_tool(name: str, arguments: dict):
    return default_registry.execute(name, arguments)