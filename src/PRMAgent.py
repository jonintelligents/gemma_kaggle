import datetime
import json
import sqlite3
import os
from google import genai
from PromptManager import PromptManager

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

def update_graph(nodes: list, edges: list):
    """
    Updates the property graph with nodes and edges extracted from conversation.
    
    Args:
        nodes: List of node dictionaries with 'id', 'label', and optional 'properties'
               Example: [{"id": "Tomorrah", "label": "Person", "properties": {"type": "wife"}}, 
                        {"id": "Miami", "label": "Place", "properties": {"type": "city"}}]
        edges: List of edge dictionaries with 'from', 'to', 'relationship', and optional 'properties'
               Example: [{"from": "Tomorrah", "to": "Deja", "relationship": "friends_with"},
                        {"from": "Tomorrah", "to": "Miami", "relationship": "traveled_to"}]
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # Create graph tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                relationship TEXT NOT NULL,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_node, to_node, relationship)
            )
        ''')
        
        nodes_added = 0
        edges_added = 0
        nodes_updated = 0
        edges_updated = 0
        
        # Insert or update nodes
        for node in nodes:
            node_id = node.get('id')
            label = node.get('label')
            properties = json.dumps(node.get('properties', {})) if node.get('properties') else None
            
            if not node_id or not label:
                continue
                
            # Check if node exists
            cursor.execute("SELECT id FROM graph_nodes WHERE id = ?", (node_id,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE graph_nodes 
                    SET label = ?, properties = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (label, properties, node_id))
                nodes_updated += 1
            else:
                cursor.execute("""
                    INSERT INTO graph_nodes (id, label, properties) 
                    VALUES (?, ?, ?)
                """, (node_id, label, properties))
                nodes_added += 1
        
        # Insert or update edges
        for edge in edges:
            from_node = edge.get('from')
            to_node = edge.get('to')
            relationship = edge.get('relationship')
            properties = json.dumps(edge.get('properties', {})) if edge.get('properties') else None
            
            if not from_node or not to_node or not relationship:
                continue
                
            # Check if edge exists
            cursor.execute("""
                SELECT id FROM graph_edges 
                WHERE from_node = ? AND to_node = ? AND relationship = ?
            """, (from_node, to_node, relationship))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE graph_edges 
                    SET properties = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE from_node = ? AND to_node = ? AND relationship = ?
                """, (properties, from_node, to_node, relationship))
                edges_updated += 1
            else:
                cursor.execute("""
                    INSERT INTO graph_edges (from_node, to_node, relationship, properties) 
                    VALUES (?, ?, ?, ?)
                """, (from_node, to_node, relationship, properties))
                edges_added += 1
        
        conn.commit()
        
        result_parts = []
        if nodes_added > 0:
            result_parts.append(f"{nodes_added} nodes added")
        if nodes_updated > 0:
            result_parts.append(f"{nodes_updated} nodes updated")
        if edges_added > 0:
            result_parts.append(f"{edges_added} edges added")
        if edges_updated > 0:
            result_parts.append(f"{edges_updated} edges updated")
            
        if result_parts:
            return f"Graph updated successfully: {', '.join(result_parts)}."
        else:
            return "No valid nodes or edges provided for graph update."
            
    except Exception as e:
        return f"Error updating graph: {e}"
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
        "update_graph": update_graph,
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
        llm_response = call_gemini_llm(user_input, chat_history, client, system_prompt)

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