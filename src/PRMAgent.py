import json
import os
from google import genai
from PromptManager import PromptManager
from ToolManager import Neo4jToolManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Neo4j Configuration ---
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

def init_neo4j():
    """
    Initialize Neo4j connection and verify it's working.
    The Neo4jToolManager handles constraint creation automatically.
    """
    logging.info(f"Initializing Neo4j connection to: {NEO4J_URI}")
    try:
        # Create tool manager - this will test the connection and create constraints
        tool_manager = Neo4jToolManager(
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD
        )
        logging.info("Neo4j database initialized successfully.")
        return tool_manager
    except Exception as e:
        logging.error(f"Failed to initialize Neo4j: {e}")
        raise

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

# --- Graph visualization helper (optional) ---
def show_graph_stats(tool_manager):
    """Display basic statistics about the graph."""
    try:
        stats_query = """
        MATCH (n)
        RETURN labels(n) as labels, count(n) as count
        ORDER BY count DESC
        """
        result = tool_manager.execute_tool("query_graph", {"cypher_query": stats_query})
        
        print("\n📊 Graph Statistics:")
        stats = json.loads(result)
        if stats:
            for stat in stats:
                labels = stat.get('labels', ['Unknown'])
                count = stat.get('count', 0)
                print(f"  {labels[0] if labels else 'Unknown'}: {count} nodes")
        
        # Count relationships
        rel_query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        """
        result = tool_manager.execute_tool("query_graph", {"cypher_query": rel_query})
        rel_stats = json.loads(result)
        
        if rel_stats:
            print("  Relationships:")
            for stat in rel_stats:
                rel_type = stat.get('relationship_type', 'Unknown')
                count = stat.get('count', 0)
                print(f"    {rel_type}: {count}")
        
        print()
    except Exception as e:
        logging.error(f"Error getting graph stats: {e}")

# --- Interactive graph exploration commands ---
def handle_special_commands(user_input: str, tool_manager):
    """Handle special commands for graph exploration."""
    user_input = user_input.strip().lower()
    
    if user_input == "/stats":
        show_graph_stats(tool_manager)
        return True
    
    elif user_input == "/contacts":
        try:
            result = tool_manager.execute_tool("get_contact", {"include_relationships": False})
            contacts = json.loads(result)
            if contacts and contacts != "No contact found matching the criteria.":
                print("\n👥 All Contacts:")
                for contact in contacts:
                    name = contact.get('name', 'Unknown')
                    summary = contact.get('summary', '')
                    print(f"  • {name}" + (f" - {summary}" if summary else ""))
            else:
                print("\n👥 No contacts found.")
        except Exception as e:
            print(f"Error retrieving contacts: {e}")
        return True
    
    elif user_input.startswith("/network "):
        contact_name = user_input[9:].strip()
        try:
            result = tool_manager.execute_tool("get_contact_network", {
                "contact_name": contact_name,
                "depth": 2
            })
            network = json.loads(result)
            if "center_contact" in network:
                print(f"\n🕸️ Network for {contact_name}:")
                connected = network.get('connected_nodes', [])
                relationships = network.get('relationships', [])
                print(f"  Connected to {len(connected)} entities")
                print(f"  {len(relationships)} relationships")
                
                # Show some examples
                for i, node in enumerate(connected[:5]):
                    node_name = node.get('name') or node.get('id', 'Unknown')
                    labels = node.get('labels', [])
                    label_str = f" ({labels[0]})" if labels else ""
                    print(f"    • {node_name}{label_str}")
                
                if len(connected) > 5:
                    print(f"    ... and {len(connected) - 5} more")
            else:
                print(f"\n🕸️ {result}")
        except Exception as e:
            print(f"Error getting network: {e}")
        return True
    
    elif user_input == "/help":
        print("""
🔧 Special Commands:
  /stats          - Show graph statistics
  /contacts       - List all contacts
  /network <name> - Show network for a contact
  /help           - Show this help
  exit            - Quit the application

💡 You can also ask natural language questions like:
  "Add John as a contact who works at Acme Corp"
  "Show me all software engineers"
  "Who knows someone at Google?"
  "Create a relationship between Alice and Bob"
        """)
        return True
    
    return False

# --- Main loop ---
def main():
    print("🚀 Starting Neo4j LLM + Tooling Demo...")
    
    # Initialize Neo4j
    try:
        tool_manager = init_neo4j()
        print(f"✅ Neo4j ToolManager initialized with tools: {', '.join(tool_manager.get_available_tools())}")
    except Exception as e:
        print(f"❌ Failed to initialize Neo4j: {e}")
        print("Make sure Neo4j is running and credentials are correct.")
        print("Set environment variables: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        return

    # Initialize Gemini API
    try:
        client = setup_gemini_api()
        print("✅ Gemini API configured successfully!")
    except ValueError as e:
        print(f"❌ Error: {e}")
        return

    # Setup prompt manager
    prompt_manager, system_prompt = setup_prompt_manager()
    if system_prompt:
        print("✅ Using custom system prompt.")
    else:
        print("⚠️ No system prompt loaded - using default behavior.")

    chat_history = []

    print("""
🎯 Welcome to the Neo4j Graph LLM Demo!

This system can manage contacts, entities, and relationships in a Neo4j graph database.
You can ask questions in natural language or use special commands.

Type '/help' for commands or 'exit' to quit.
""")

    # Show initial stats
    show_graph_stats(tool_manager)

    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() == "exit":
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Handle special commands
            if handle_special_commands(user_input, tool_manager):
                continue

            # Add to chat history
            chat_history.append({"role": "user", "content": user_input})

            # Call LLM
            result = call_gemini_llm(user_input, chat_history, client, system_prompt, tool_manager)

            if result["type"] == "text":
                # Response already printed inside the function
                continue
            elif result["type"] == "tool_call_complete":
                # Show updated stats after tool execution
                print("\n📊 Updated graph:")
                show_graph_stats(tool_manager)
                continue
            elif result["type"] == "cancelled":
                continue
            else:
                print("⚠️ Unexpected response type.")

        except KeyboardInterrupt:
            print("\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ An error occurred: {e}")
            logging.error(f"Main loop error: {e}", exc_info=True)

    # Clean up
    try:
        tool_manager.close()
        print("✅ Neo4j connection closed.")
    except Exception as e:
        logging.error(f"Error closing Neo4j connection: {e}")

if __name__ == "__main__":
    main()