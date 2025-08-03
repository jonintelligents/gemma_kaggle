import json
import os
import argparse
from google import genai
from ToolManager import ExamplePersonToolManager
from GraphPersonManager import GraphPersonManager
from PromptManager import PromptManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

prompt_manager = PromptManager()

# --- Gemini API Setup ---
def setup_gemini_api():
    logging.info("Setting up Gemini API.")
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Please set the GEMINI_API_KEY environment variable")
    client = genai.Client()
    return client

# --- Call Gemini and parse response ---
def call_gemini_llm(user_query: str, chat_history: list, client, system_prompt: str = None, tool_manager=None, is_chat_mode=True, max_retries=3):
    logging.info(f"Calling Gemini LLM with query: '{user_query}'")

    for attempt in range(max_retries):
        try:
            if system_prompt:
                full_context = system_prompt + "\n\n"
            else:
                full_context = ""
            
            # Add conversation history
            full_context += "Conversation history:\n"
            for message in chat_history:
                role = message["role"]
                content = message["content"]
                full_context += f"{role.capitalize()}: {content}\n"

            full_context += f"User: {user_query}\nAssistant:"

            # Make the API call
            logging.info(f"Making Gemini API call - attempt {attempt + 1}/{max_retries}")
            response = client.models.generate_content(
                model="gemma-3n-e4b-it",
                contents=full_context
            )

            llm_content = response.text.strip()

            if llm_content.startswith("```json") and llm_content.endswith("```"):
                llm_content = llm_content[7:-3].strip()

            try:
                parsed = json.loads(llm_content)
                # If we get here, JSON parsing succeeded
                logging.info(f"JSON parsing successful on attempt {attempt + 1}")
                
                response_text = parsed.get("response", "").strip()
                tool_calls = parsed.get("tool_calls", [])

                if not tool_calls:
                    print(f"\nLLM Response: {response_text}")
                    chat_history.append({"role": "assistant", "content": response_text})
                    return {"type": "text", "content": response_text}
                else:
                    print(f"\nLLM Response: {response_text}")
                    
                    if is_chat_mode:
                        print("\nI'm going to perform these operations:")
                        for i, tool in enumerate(tool_calls, 1):
                            print(f"{i}. Tool: {tool['name']} with arguments {tool.get('parameters', {})}")

                        proceed = input("\nShall I proceed? (yes/No): ").strip().lower()
                        if proceed != "yes":
                            print("Tool execution cancelled. Waiting for next prompt...")
                            chat_history.append({"role": "assistant", "content": "Tool execution was cancelled."})
                            return {"type": "cancelled"}
                    else:
                        print("\nExecuting tools:")
                        for i, tool in enumerate(tool_calls, 1):
                            print(f"{i}. Tool: {tool['name']} with arguments {tool.get('parameters', {})}")

                    # Execute tools
                    for tool in tool_calls:
                        try:
                            tool_output = tool_manager.execute_tool(tool["name"], tool.get("parameters", {}))
                            print(f"\n✅ Tool '{tool['name']}' executed. Output: {tool_output}")
                            print(tool_output['result'])
                            if 'name' in tool and tool['name'] == 'search' :
                                #format the results with the llm
                                output = run_single_prompt(prompt_manager.get_prompt("search_filter", {"search_results" : tool_output['result']}), None, client, None, retry_count=1)
                                print(output)

                            chat_history.append({
                                "role": "assistant",
                                "content": f"Executed tool '{tool['name']}' with result: {tool_output}"
                            })
                        except Exception as e:
                            print(f"❌ Error executing tool '{tool['name']}': {e}")
                            logging.error(f"Tool execution failed: {e}", exc_info=True)
                            
                    return {"type": "tool_call_complete"}
                    
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    logging.warning(f"JSON parse error on attempt {attempt + 1}/{max_retries}. Rerunning prompt... Error: {e}")
                    print(f"⚠️ JSON parse error on attempt {attempt + 1}/{max_retries}. Rerunning prompt...")
                    # Continue to next iteration to rerun the entire prompt
                    continue
                else:
                    logging.error(f"JSON parse failed after {max_retries} attempts. Final error: {e}")
                    print(f"❌ Failed to parse LLM JSON response after {max_retries} attempts.")
                    print(f"Raw response: {llm_content}")
                    return {"type": "text", "content": llm_content}
                    
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"Gemini API error on attempt {attempt + 1}/{max_retries}. Retrying... Error: {e}")
                print(f"⚠️ API error on attempt {attempt + 1}/{max_retries}. Retrying...")
                continue
            else:
                logging.error(f"Gemini API error after {max_retries} attempts. Final error: {e}", exc_info=True)
                return {"type": "text", "content": f"An error occurred after {max_retries} attempts: {e}"}
    
    # This should never be reached, but just in case
    return {"type": "text", "content": "Maximum retry attempts exceeded"}

def run_chat_mode(tool_manager, client, system_prompt):
    """Run the interactive chat mode."""
    chat_history = []

    print("""
🎯 Welcome to the LLM Tool Demo!

This system can execute tools based on your natural language requests.
Type 'exit' to quit.
""")

    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() == "exit":
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue

            # Add to chat history
            chat_history.append({"role": "user", "content": user_input})

            # Call LLM with retry logic
            result = call_gemini_llm(user_input, chat_history, client, system_prompt, tool_manager, is_chat_mode=True, max_retries=3)

            if result["type"] == "text":
                # Response already printed inside the function
                continue
            elif result["type"] == "tool_call_complete":
                print("\n✅ Tool execution completed.")
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

def run_single_prompt(prompt, tool_manager, client, system_prompt, retry_count=3):
    """Run a single prompt and execute any tool calls automatically."""
    chat_history = []
    
    print(f"🚀 Processing prompt: {prompt}")
    
    # Add to chat history
    chat_history.append({"role": "user", "content": prompt})
    
    # Call LLM with retry logic
    result = call_gemini_llm(prompt, chat_history, client, system_prompt, tool_manager, is_chat_mode=False, max_retries=retry_count)
    
    if result["type"] == "tool_call_complete":
        print("\n✅ All tool calls completed successfully.")
    elif result["type"] == "text":
        print("📄 No tool calls were needed.")
    else:
        print("⚠️ Unexpected response type.")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="LLM Tool Demo")
    parser.add_argument(
        "--chat", 
        action="store_true", 
        help="Run in interactive chat mode"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Single prompt to process (required if not using --chat)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.chat and not args.prompt:
        parser.error("Either --chat flag or a prompt argument is required")
    
    if args.chat and args.prompt:
        parser.error("Cannot use both --chat flag and prompt argument")
    
    return args

# --- Main function ---
def main():
    # Parse command line arguments
    args = parse_arguments()
    
    print("🚀 Starting LLM + Tooling Demo...")
    
    # Initialize tool manager
    try:
        #tool_manager = ExamplePersonToolManager()
        tool_manager = GraphPersonManager()
        print(f"✅ ToolManager initialized with tools: {', '.join(tool_manager.get_available_tools())}")
    except Exception as e:
        print(f"❌ Failed to initialize tool manager: {e}")
        return

    # Initialize Gemini API
    try:
        client = setup_gemini_api()
        print("✅ Gemini API configured successfully!")
    except ValueError as e:
        print(f"❌ Error: {e}")
        return

    # Setup system prompt
    system_prompt = prompt_manager.get_prompt("system", {"tool_function_descriptions" : tool_manager.get_available_tools_detailed()})

    try:
        if args.chat:
            run_chat_mode(tool_manager, client, system_prompt)
        else:
            run_single_prompt(args.prompt, tool_manager, client, system_prompt)
    finally:
        # Clean up
        try:
            tool_manager.close()
            print("✅ Tool manager connection closed.")
        except Exception as e:
            logging.error(f"Error closing tool manager connection: {e}")

if __name__ == "__main__":
    main()