import os
from dotenv import load_dotenv

from llm.gemini import GeminiLLM
from tools import default_registry
from agents.agent import Agent
from prompts import SYSTEM_PROMPT

load_dotenv()

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set in environment or .env file.")

    llm = GeminiLLM(model="gemini-3.5-flash-lite", api_key=api_key)
    agent = Agent(
        llm=llm,
        tools=default_registry,
        system_prompt=SYSTEM_PROMPT,
    )

    prompt = "read every file in tools/, summarize each one, then tell me which has the most lines"
    print(f"User: {prompt}\n")

    response = agent.run(prompt)
    print(f"Agent:\n{response}")


if __name__ == "__main__":
    main()