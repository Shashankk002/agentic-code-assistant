import argparse
import os
import sys

from dotenv import load_dotenv
from llm.gemini import GeminiLLM
from tools.dispatcher import default_registry
from agents.agent import Agent
from prompts import SYSTEM_PROMPT

load_dotenv()


def build_agent(no_confirm: bool = False) -> Agent:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
    llm = GeminiLLM(api_key=api_key)
    return Agent(
        llm=llm,
        tools=default_registry,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=10,
        require_confirmation=not no_confirm,
    )


def main():
    parser = argparse.ArgumentParser(description="Agentic coding assistant")
    parser.add_argument(
        "prompt", nargs="?", default=None,
        help="One-shot task. Omit to start an interactive session."
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip permission prompts for write_file/edit_file/run_command."
    )
    args = parser.parse_args()

    agent = build_agent(no_confirm=args.yes)

    if args.prompt:
        result = agent.run(args.prompt)
        print(f"\nAgent:\n{result}")
        return

    print("Agentic coding assistant. Type a task, or 'exit'/'quit' to stop.\n")
    while True:
        try:
            user_input = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        try:
            result = agent.run(user_input)
        except KeyboardInterrupt:
            print("\nInterrupted.\n")
            continue
        print(f"\nAgent:\n{result}\n")


if __name__ == "__main__":
    main()