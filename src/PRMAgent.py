import json
import sqlite3
import os
from google import genai
from PromptManager import PromptManager
from ToolManager import ToolManager


# --- Database Setup ---
DATABASE_NAME = 'contacts.db'

def init_db():
    """
    Initializes the SQLite database and creates the contacts table.
    The contacts table now includes columns for up to 10 facts.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Drop table if it exists to ensure a clean schema for this demo
    cursor.execute('DROP TABLE IF EXISTS contacts')

    # Create contacts table with 10 fact columns
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


# --- Gemini API Configuration ---

def setup_gemini_api():
    """
    Configure the Google Gemini API. 
    Set your API key as an environment variable: GEMINI_API_KEY
    The client automatically gets the API key from the environment variable.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Please set the GEMINI_API_KEY environment variable")
    
    client = genai.Client()
    return client


# --- Prompt Manager Setup ---

def setup_prompt_manager(prompts_dir: str = "./prompts"):
    """
    Initialize the PromptManager and attempt to load prompts.
    Returns the PromptManager instance and the system prompt if available.
    """
    try:
        pm = PromptManager(prompts_dir)
        print(f"PromptManager initialized with {len(pm)} prompts from '{prompts_dir}'")
        
        # Check if system prompt exists
        if pm.has_prompt("system"):
            system_prompt = pm.get_prompt("system")
            print("System prompt loaded from 'system.md'")
            return pm, system_prompt
        else:
            print("No 'system.md' prompt found, proceeding without system prompt")
            return pm, None
            
    except FileNotFoundError:
        print(f"Prompts directory '{prompts_dir}' not found, proceeding without system prompt")
        return None, None
    except Exception as e:
        print(f"Error setting up PromptManager: {e}")
        print("Continuing without system prompt")
        return None, None


# --- LLM Interaction with Google Gemini API ---

def call_gemini_llm(user_query: str, chat_history: list, client, system_prompt: str = None):
    """
    Calls the Google Gemini API with an optional system prompt.
    If no system prompt is provided, conversation starts without one.
    """
    try:
        # Build the full conversation context
        if system_prompt:
            full_context = system_prompt + "\n\nConversation history:\n"
        else:
            full_context = "Conversation history:\n"
        
        # Add chat history
        for message in chat_history:
            if message["role"] == "user":
                full_context += f"User: {message['content']}\n"
            elif message["role"] == "assistant":
                full_context += f"Assistant: {message['content']}\n"
        
        # Add current user query
        full_context += f"User: {user_query}\nAssistant:"
        
        # Make the API call
        response = client.models.generate_content(
            model="gemma-3n-e4b-it",
            contents=full_context
        )
        
        llm_content = response.text

        # Preprocess LLM content to remove markdown code block if present
        llm_content_to_parse = llm_content
        if llm_content.strip().startswith("```json") and llm_content.strip().endswith("```"):
            json_start_index = llm_content.find("```json") + len("```json")
            json_end_index = llm_content.rfind("```")
            if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
                llm_content_to_parse = llm_content[json_start_index:json_end_index].strip()
            else:
                llm_content_to_parse = llm_content.strip()

        try:
            # Attempt to parse the (potentially cleaned) content as JSON
            parsed_json = json.loads(llm_content_to_parse)
            # Check if it matches the expected tool call format
            if isinstance(parsed_json, dict) and "tool_call" in parsed_json:
                tool_call = parsed_json["tool_call"]
                if isinstance(tool_call, dict) and "name" in tool_call:
                    tool_name = tool_call["name"]
                    tool_arguments = tool_call.get("parameters", {})
                    return {
                        "type": "tool_code",
                        "tool_name": tool_name,
                        "arguments": tool_arguments
                    }
        except json.JSONDecodeError:
            pass
        except KeyError:
            pass

        # If it's not a tool call JSON, return as regular text
        return {
            "type": "text",
            "content": llm_content
        }

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {"type": "text", "content": f"An error occurred while communicating with Gemini API: {e}"}


def main():
    """
    Main function to demonstrate the LLM interaction with Google Gemini API
    and manual parsing of tool calls from the LLM's text response.
    """
    init_db()  # Initialize the database at startup
    
    # Initialize the ToolManager
    tool_manager = ToolManager(DATABASE_NAME)
    print(f"ToolManager initialized with {len(tool_manager.get_available_tools())} tools")
    
    try:
        client = setup_gemini_api()
        print("Google Gemini API configured successfully!")
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set your Gemini API key as an environment variable:")
        print("export GEMINI_API_KEY='your-api-key-here'")
        return
    except Exception as e:
        print(f"Error setting up Gemini API: {e}")
        return

    # Setup PromptManager and load system prompt
    prompt_manager, system_prompt = setup_prompt_manager()
    
    if system_prompt:
        print("Using custom system prompt from prompts/system.md")
    else:
        print("No system prompt loaded - LLM will operate without initial instructions")

    print("\nWelcome to the LLM Demo with Google Gemini API and CRUD Tooling!")
    print("Using Gemma 3N E4B model via Google AI API.")
    
    if prompt_manager:
        available_prompts = prompt_manager.list_prompts()
        if available_prompts:
            print(f"Available prompts loaded: {', '.join(available_prompts)}")
    
    print(f"\nAvailable tools: {', '.join(tool_manager.get_available_tools())}")
    
    print("\nAvailable commands (try variations):")
    print(" - What is the current date and time?")
    print(" - Add a contact named Jane Doe with a summary of 'Marketing Specialist'.")
    print(" - Get contact with ID 1.")
    print(" - Find contact named Jane.")
    print(" - Update contact 1's summary to 'Senior Marketing Specialist'.")
    print(" - Add a fact to contact 1: 'Enjoys hiking.'")
    print(" - Add another fact to contact 1: 'Loves reading sci-fi.'")
    print(" - Get contact with ID 1 (to see facts).")
    print(" - Update fact 1 for contact 1 to 'Enjoys mountain biking.'")
    print(" - Delete fact 2 from contact 1.")
    print(" - Delete contact 1.")
    print(" - Type 'exit' to quit.")

    chat_history = []  # To maintain conversation context

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'exit':
            print("Exiting demo. Goodbye!")
            break

        chat_history.append({"role": "user", "content": user_input})
        print(f"LLM (Gemma 3N E4B via Google AI) processing: '{user_input}'")

        # Step 1: Get the Gemini LLM response (could be text or a tool call JSON)
        llm_response = call_gemini_llm(user_input, chat_history, client, system_prompt)

        if llm_response["type"] == "tool_code":
            tool_name = llm_response["tool_name"]
            tool_arguments = llm_response["arguments"]
            print(f"LLM requested tool call: {tool_name} with arguments {tool_arguments}")

            # Add the LLM's tool call response to history for context
            chat_history.append({"role": "assistant", "content": json.dumps({"tool_call": {"name": tool_name, "parameters": tool_arguments}})})

            try:
                # Step 2: Execute the tool using ToolManager
                tool_output = tool_manager.execute_tool(tool_name, tool_arguments)
                print(f"Tool '{tool_name}' executed. Output: {tool_output}")

                # Step 3: Feed the tool output back to the LLM by adding it to the chat history
                tool_output_message = f"The tool '{tool_name}' returned the following result: {tool_output}. Please provide a natural language answer based on this."
                chat_history.append({"role": "user", "content": tool_output_message})

                # Get the final natural language response from the LLM
                final_llm_response = call_gemini_llm(tool_output_message, chat_history, client, system_prompt)

                if final_llm_response["type"] == "text":
                    print(f"LLM (Gemma 3N E4B) final response based on tool output:")
                    print(final_llm_response["content"])
                    chat_history.append({"role": "assistant", "content": final_llm_response["content"]})
                else:
                    print("LLM did not provide a final content response after tool execution.")
                    chat_history.append({"role": "assistant", "content": "Error: LLM did not provide a final response after tool execution."})

            except ValueError as e:
                print(f"Error executing tool: {e}")
                error_message = f"An error occurred trying to get that information: {e}"
                print(f"LLM (Gemma 3N E4B) response: {error_message}")
                chat_history.append({"role": "assistant", "content": error_message})
            except Exception as e:
                print(f"API Error during follow-up: {e}")
                error_message = f"An API error occurred during follow-up: {e}"
                print(f"LLM (Gemma 3N E4B) response: {error_message}")
                chat_history.append({"role": "assistant", "content": error_message})

        elif llm_response["type"] == "text":
            print(f"LLM (Gemma 3N E4B) response: {llm_response['content']}")
            chat_history.append({"role": "assistant", "content": llm_response["content"]})
        else:
            print("LLM (Gemma 3N E4B) returned an unexpected response type.")
            chat_history.append({"role": "assistant", "content": "Error: LLM returned an unexpected response type."})


if __name__ == "__main__":
    main()