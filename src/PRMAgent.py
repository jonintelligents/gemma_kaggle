import json
import sqlite3
import os
from google import genai
from PromptManager import PromptManager
from ToolManager import ToolManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Database Setup ---
DATABASE_NAME = 'contacts.db'

def init_db():
    logging.info(f"Initializing database: {DATABASE_NAME}")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS contacts')

    fact_columns = ", ".join([f"fact_{i} TEXT" for i in range(1, 11)])
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            summary TEXT,
            {fact_columns}
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

# --- Gemini API Setup ---
def setup_gemini_api():
    logging.info("Setting up Gemini API.")
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Please set the GEMINI_API_KEY environment variable")
    client = genai.Client()
    return client

# --- Prompt Manager ---
def setup_prompt_manager(prompts_dir: str = "./prompts"):
    try:
        pm = PromptManager(prompts_dir)
        if pm.has_prompt("system"):
            return pm, pm.get_prompt("system")
        else:
            return pm, None
    except Exception:
        return None, None

# --- Call Gemini and parse response ---
def call_gemini_llm(user_query: str, chat_history: list, client, system_prompt: str = None, tool_manager=None):
    logging.info(f"Calling Gemini LLM with query: '{user_query}'")

    try:
        if system_prompt:
            full_context = system_prompt + "\n\nConversation history:\n"
        else:
            full_context = "Conversation history:\n"

        for message in chat_history:
            role = message["role"]
            content = message["content"]
            full_context += f"{role.capitalize()}: {content}\n"

        full_context += f"User: {user_query}\nAssistant:"

        response = client.models.generate_content(
            model="gemma-3n-e4b-it",
            contents=full_context
        )

        llm_content = response.text.strip()

        if llm_content.startswith("```json") and llm_content.endswith("```"):
            llm_content = llm_content[7:-3].strip()

        try:
            parsed = json.loads(llm_content)
            response_text = parsed.get("response", "").strip()
            tool_calls = parsed.get("tool_calls", [])

            if not tool_calls:
                print(f"\nLLM Response: {response_text}")
                chat_history.append({"role": "assistant", "content": response_text})
                return {"type": "text", "content": response_text}
            else:
                print(f"\nLLM Response: {response_text}")
                print("\nI'm going to perform these operations:")
                for i, tool in enumerate(tool_calls, 1):
                    print(f"{i}. Tool: {tool['name']} with arguments {tool.get('parameters', {})}")

                proceed = input("\nShall I proceed? (yes/No): ").strip().lower()
                if proceed == "yes":
                    for tool in tool_calls:
                        try:
                            tool_output = tool_manager.execute_tool(tool["name"], tool.get("parameters", {}))
                            print(f"\n✅ Tool '{tool['name']}' executed. Output: {tool_output}")
                            chat_history.append({
                                "role": "assistant",
                                "content": f"Executed tool '{tool['name']}' with result: {tool_output}"
                            })
                        except Exception as e:
                            print(f"❌ Error executing tool '{tool['name']}': {e}")
                            logging.error(f"Tool execution failed: {e}", exc_info=True)
                    return {"type": "tool_call_complete"}
                else:
                    print("Tool execution cancelled. Waiting for next prompt...")
                    chat_history.append({"role": "assistant", "content": "Tool execution was cancelled."})
                    return {"type": "cancelled"}
        except json.JSONDecodeError as e:
            print("❌ Failed to parse LLM JSON response.")
            logging.error(f"JSON decode error: {e}")
            return {"type": "text", "content": llm_content}
    except Exception as e:
        logging.error(f"Gemini API Error: {e}", exc_info=True)
        return {"type": "text", "content": f"An error occurred: {e}"}

# --- Main loop ---
def main():
    init_db()
    tool_manager = ToolManager(DATABASE_NAME)
    print(f"ToolManager initialized with tools: {', '.join(tool_manager.get_available_tools())}")

    try:
        client = setup_gemini_api()
        print("Gemini API configured successfully!")
    except ValueError as e:
        print(f"Error: {e}")
        return

    prompt_manager, system_prompt = setup_prompt_manager()
    if system_prompt:
        print("Using custom system prompt.")
    else:
        print("No system prompt loaded.")

    chat_history = []

    print("\nWelcome to the Gemini LLM + Tooling Demo!")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        chat_history.append({"role": "user", "content": user_input})

        result = call_gemini_llm(user_input, chat_history, client, system_prompt, tool_manager)

        if result["type"] == "text":
            # already printed inside the function
            continue
        elif result["type"] == "tool_call_complete":
            continue
        elif result["type"] == "cancelled":
            continue
        else:
            print("Unexpected response type.")

if __name__ == "__main__":
    main()
