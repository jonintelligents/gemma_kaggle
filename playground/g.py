import datetime
import json
import sqlite3
import os
from google import genai

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

# --- Tool Definitions (Python functions interacting with the DB) ---

def get_current_datetime():
    """
    Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def add_contact(name: str, summary: str = None):
    """Adds a new contact to the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO contacts (name, summary) VALUES (?, ?)", (name, summary))
        conn.commit()
        contact_id = cursor.lastrowid
        return f"Contact '{name}' added successfully with ID: {contact_id}."
    except sqlite3.IntegrityError:
        return f"Error: Contact with name '{name}' already exists."
    finally:
        conn.close()

def get_contact(contact_id: int = None, name: str = None):
    """Retrieves contact(s) from the database by ID or name, including all facts."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    contacts = []
    fact_columns = ", ".join([f"fact_{i}" for i in range(1, 11)])
    select_query = f"SELECT id, name, summary, {fact_columns} FROM contacts"

    if contact_id:
        cursor.execute(f"{select_query} WHERE id = ?", (contact_id,))
    elif name:
        cursor.execute(f"{select_query} WHERE name LIKE ?", (f"%{name}%",))
    else:
        cursor.execute(select_query)

    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    conn.close()

    if not rows:
        return "No contact found matching the criteria."

    for row in rows:
        contact_data = {}
        for i, col_name in enumerate(column_names):
            contact_data[col_name] = row[i]
        contacts.append(contact_data)
    return json.dumps(contacts) # Return as JSON string for LLM processing

def update_contact_summary(contact_id: int, new_summary: str):
    """Updates a contact's summary in the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET summary = ? WHERE id = ?", (new_summary, contact_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    if rows_affected > 0:
        return f"Summary for contact ID {contact_id} updated successfully."
    else:
        return f"No contact found with ID {contact_id} to update."

def delete_contact(contact_id: int):
    """Deletes a contact from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    if rows_affected > 0:
        return f"Contact with ID {contact_id} deleted successfully."
    else:
        return f"No contact found with ID {contact_id} to delete."

def add_fact_to_contact(contact_id: int, fact_text: str):
    """
    Adds a fact to the next available fact_N column for a given contact.
    Returns an error if all 10 fact columns are full.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Check if contact_id exists and get current fact values
        cursor.execute(f"SELECT {', '.join([f'fact_{i}' for i in range(1, 11)])} FROM contacts WHERE id = ?", (contact_id,))
        current_facts = cursor.fetchone()

        if current_facts is None:
            return f"Error: Contact with ID {contact_id} does not exist. Cannot add fact."

        # Find the first available (NULL or empty string) fact column
        available_fact_column = -1
        for i, fact_value in enumerate(current_facts):
            if fact_value is None or (isinstance(fact_value, str) and fact_value.strip() == ""): # Added isinstance check
                available_fact_column = i + 1 # Column number (1-indexed)
                break

        if available_fact_column != -1:
            update_column_name = f"fact_{available_fact_column}"
            cursor.execute(f"UPDATE contacts SET {update_column_name} = ? WHERE id = ?", (fact_text, contact_id))
            conn.commit()
            return f"Fact added to contact ID {contact_id} in column '{update_column_name}'."
        else:
            return f"Error: All 10 fact columns for contact ID {contact_id} are already full. Please update or delete an existing fact."
    except Exception as e:
        return f"Error adding fact to contact: {e}"
    finally:
        conn.close()

def update_fact_for_contact(contact_id: int, fact_number: int, new_fact_text: str):
    """Updates a specific fact (fact_N) for a given contact."""
    if not (1 <= fact_number <= 10):
        return "Error: Fact number must be between 1 and 10."

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        update_column_name = f"fact_{fact_number}"
        cursor.execute(f"UPDATE contacts SET {update_column_name} = ? WHERE id = ?", (new_fact_text, contact_id))
        conn.commit()
        rows_affected = cursor.rowcount
        if rows_affected > 0:
            return f"Fact {fact_number} for contact ID {contact_id} updated successfully."
        else:
            return f"No contact found with ID {contact_id} to update fact {fact_number}."
    except Exception as e:
        return f"Error updating fact: {e}"
    finally:
        conn.close()

def delete_fact_from_contact(contact_id: int, fact_number: int):
    """Deletes a specific fact (fact_N) for a given contact by setting it to NULL."""
    if not (1 <= fact_number <= 10):
        return "Error: Fact number must be between 1 and 10."

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        delete_column_name = f"fact_{fact_number}"
        cursor.execute(f"UPDATE contacts SET {delete_column_name} = NULL WHERE id = ?", (contact_id,))
        conn.commit()
        rows_affected = cursor.rowcount
        if rows_affected > 0:
            return f"Fact {fact_number} for contact ID {contact_id} deleted successfully."
        else:
            return f"No contact found with ID {contact_id} to delete fact {fact_number}."
    except Exception as e:
        return f"Error deleting fact: {e}"
    finally:
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

# --- LLM Interaction with Google Gemini API ---

def call_gemini_llm(user_query: str, chat_history: list, client):
    """
    Calls the Google Gemini API with a system prompt that includes
    the tool definitions and instructions for responding with a JSON tool call.
    """
    try:
        # Define the system prompt with all embedded tool definitions
        system_prompt = """You are an AI assistant with access to the following tools:

1.  Tool Name: get_current_datetime
    Description: Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    Parameters:
        - None

2.  Tool Name: add_contact
    Description: Adds a new contact to the database.
    Parameters:
        - name (string, required): The name of the contact.
        - summary (string, optional): A brief summary of the contact.

3.  Tool Name: get_contact
    Description: Retrieves contact(s) from the database by ID or name, including all associated facts.
    Parameters:
        - contact_id (integer, optional): The ID of the contact.
        - name (string, optional): The name of the contact (can be partial).

4.  Tool Name: update_contact_summary
    Description: Updates an existing contact's summary in the database.
    Parameters:
        - contact_id (integer, required): The ID of the contact to update.
        - new_summary (string, required): The new summary for the contact.

5.  Tool Name: delete_contact
    Description: Deletes a contact from the database.
    Parameters:
        - contact_id (integer, required): The ID of the contact to delete.

6.  Tool Name: add_fact_to_contact
    Description: Adds a new fact to the next available fact column (fact_1 to fact_10) for an existing contact.
    Parameters:
        - contact_id (integer, required): The ID of the contact to add the fact to.
        - fact_text (string, required): The text of the fact.

7.  Tool Name: update_fact_for_contact
    Description: Updates a specific fact (fact_1 to fact_10) for a given contact.
    Parameters:
        - contact_id (integer, required): The ID of the contact.
        - fact_number (integer, required): The number of the fact column to update (1-10).
        - new_fact_text (string, required): The new text for the fact.

8.  Tool Name: delete_fact_from_contact
    Description: Deletes a specific fact (fact_1 to fact_10) for a given contact by setting its column to NULL.
    Parameters:
        - contact_id (integer, required): The ID of the contact.
        - fact_number (integer, required): The number of the fact column to delete (1-10).

When you need to use a tool, respond ONLY with a JSON object in the following format, and nothing else:
{"tool_call": {"name": "tool_name", "parameters": {"param1": "value1", "param2": "value2"}}}

If you do not need to use a tool, respond with a natural language answer.
"""
        
        # Build the full conversation context including system prompt and chat history
        full_context = system_prompt + "\n\nConversation history:\n"
        
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


def execute_tool(tool_name: str, arguments: dict):
    """
    Executes a registered tool based on its name and arguments.
    """
    # Map tool names to their corresponding Python functions
    tool_functions = {
        "get_current_datetime": get_current_datetime,
        "add_contact": add_contact,
        "get_contact": get_contact,
        "update_contact_summary": update_contact_summary,
        "delete_contact": delete_contact,
        "add_fact_to_contact": add_fact_to_contact,
        "update_fact_for_contact": update_fact_for_contact,
        "delete_fact_from_contact": delete_fact_from_contact,
    }

    if tool_name in tool_functions:
        func = tool_functions[tool_name]
        try:
            # Call the function with unpacked arguments
            return func(**arguments)
        except TypeError as e:
            return f"Error: Incorrect arguments for tool '{tool_name}'. Details: {e}. Arguments provided: {arguments}"
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

def main():
    """
    Main function to demonstrate the LLM interaction with Google Gemini API
    and manual parsing of tool calls from the LLM's text response.
    """
    init_db() # Initialize the database at startup
    
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

    print("Welcome to the LLM Demo with Google Gemini API and CRUD Tooling!")
    print("Using Gemma 3N E4B model via Google AI API.")
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

    chat_history = [] # To maintain conversation context

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'exit':
            print("Exiting demo. Goodbye!")
            break

        chat_history.append({"role": "user", "content": user_input})
        print(f"LLM (Gemma 3N E4B via Google AI) processing: '{user_input}'")

        # Step 1: Get the Gemini LLM response (could be text or a tool call JSON)
        llm_response = call_gemini_llm(user_input, chat_history, client)

        if llm_response["type"] == "tool_code":
            tool_name = llm_response["tool_name"]
            tool_arguments = llm_response["arguments"]
            print(f"LLM requested tool call: {tool_name} with arguments {tool_arguments}")

            # Add the LLM's tool call response to history for context
            chat_history.append({"role": "assistant", "content": json.dumps({"tool_call": {"name": tool_name, "parameters": tool_arguments}})})

            try:
                # Step 2: Execute the tool
                tool_output = execute_tool(tool_name, tool_arguments)
                print(f"Tool '{tool_name}' executed. Output: {tool_output}")

                # Step 3: Feed the tool output back to the LLM by adding it to the chat history
                tool_output_message = f"The tool '{tool_name}' returned the following result: {tool_output}. Please provide a natural language answer based on this."
                chat_history.append({"role": "user", "content": tool_output_message})

                # Get the final natural language response from the LLM
                final_llm_response = call_gemini_llm(tool_output_message, chat_history, client)

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