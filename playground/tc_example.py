import datetime
import json
import ollama

# --- Define the Tool ---
def get_current_datetime():
    """
    Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    This simulates a tool that interacts with the operating system or an external API.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- LLM Interaction with Ollama ---

def call_ollama_llm(user_query: str, chat_history: list):
    """
    Calls the Ollama LLM (gemma3n:latest) with a system prompt that includes
    the tool definition and instructions for responding with a JSON tool call.
    """
    try:
        client = ollama.Client()

        # Define the system prompt with the embedded tool definition
        system_prompt = """You are an AI assistant with access to the following tools:

1.  Tool Name: get_current_datetime
    Description: Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    Parameters:
        - None

When you need to use a tool to get the current date and time, respond ONLY with a JSON object in the following format, and nothing else:
{"tool_call": {"name": "tool_name"}}

If you do not need to use a tool, respond with a natural language answer.
"""
        # Add the system prompt to the beginning of the chat history
        messages = [{"role": "system", "content": system_prompt}] + chat_history

        # Make the chat call to Ollama. Tools are no longer passed as a separate argument.
        response = client.chat(
            model="gemma3n:latest",
            messages=messages,
            stream=False # We want a single, complete response
        )

        # Process the LLM's response
        if response and response.get("message") and response["message"].get("content"):
            llm_content = response["message"]["content"]

            # Preprocess LLM content to remove markdown code block if present
            llm_content_to_parse = llm_content
            if llm_content.strip().startswith("```json") and llm_content.strip().endswith("```"):
                # Find the start and end of the actual JSON string within the markdown block
                json_start_index = llm_content.find("```json") + len("```json")
                json_end_index = llm_content.rfind("```")
                if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
                    llm_content_to_parse = llm_content[json_start_index:json_end_index].strip()
                else:
                    # Fallback if markdown parsing fails, try to parse original content
                    llm_content_to_parse = llm_content.strip()

            try:
                # Attempt to parse the (potentially cleaned) content as JSON
                parsed_json = json.loads(llm_content_to_parse)
                # Check if it matches the expected tool call format
                if isinstance(parsed_json, dict) and "tool_call" in parsed_json:
                    tool_call = parsed_json["tool_call"]
                    # Check for 'name' key, and safely get 'parameters' (default to empty dict if not present)
                    if isinstance(tool_call, dict) and "name" in tool_call:
                        tool_name = tool_call["name"]
                        tool_arguments = tool_call.get("parameters", {}) # Get parameters, default to empty dict
                        return {
                            "type": "tool_code",
                            "tool_name": tool_name,
                            "arguments": tool_arguments
                        }
            except json.JSONDecodeError:
                # Not a JSON response, treat as regular text
                pass
            except KeyError:
                # JSON but not in the expected tool_call format (e.g., missing 'name' or 'tool_call' structure)
                pass

            # If it's not a tool call JSON, return as regular text
            return {
                "type": "text",
                "content": llm_content # Return original content if not a tool call
            }
        return {"type": "text", "content": "I did not receive a clear text response from the LLM."}

    except ollama.ResponseError as e:
        print(f"Ollama API Error: {e}")
        return {"type": "text", "content": f"An error occurred while communicating with Ollama: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"type": "text", "content": f"An unexpected error occurred: {e}"}


def execute_tool(tool_name: str, arguments: dict):
    """
    Executes a registered tool based on its name and arguments.
    """
    if tool_name == "get_current_datetime":
        # Call the actual Python function for the tool
        return get_current_datetime()
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

def main():
    """
    Main function to demonstrate the LLM interaction with a system prompt
    and manual parsing of tool calls from the LLM's text response.
    """
    print("Welcome to the LLM Demo with Ollama and Embedded Tool Definition!")
    print("Ensure 'ollama serve' is running and 'gemma3n:latest' is available.")
    print("Type 'What is the current date and time?' to see the LLM attempt a tool call.")
    print("Type other queries for natural language responses.")
    print("Type 'exit' to quit.")

    chat_history = [] # To maintain conversation context

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'exit':
            print("Exiting demo. Goodbye!")
            break

        chat_history.append({"role": "user", "content": user_input})
        print(f"LLM (gemma3n:latest via Ollama) processing: '{user_input}'")

        # Step 1: Get the Ollama LLM response (could be text or a tool call JSON)
        llm_response = call_ollama_llm(user_input, chat_history)

        if llm_response["type"] == "tool_code":
            tool_name = llm_response["tool_name"]
            tool_arguments = llm_response["arguments"]
            print(f"LLM requested tool call: {tool_name} with arguments {tool_arguments}")

            # Add the LLM's tool call response to history for context
            # Note: We are echoing the LLM's raw JSON tool call back into history.
            # This ensures the LLM sees its own tool call in the conversation.
            chat_history.append({"role": "assistant", "content": json.dumps({"tool_call": {"name": tool_name, "parameters": tool_arguments}})})

            try:
                # Step 2: Execute the tool
                tool_output = execute_tool(tool_name, tool_arguments)
                print(f"Tool '{tool_name}' executed. Output: {tool_output}")

                # Step 3: Feed the tool output back to the LLM by adding it to the chat history
                # This is crucial for the LLM to formulate a coherent response based on the tool's result.
                # We'll simulate this as a user message for simplicity, as Ollama's `tool` role
                # might not be fully supported by Gemma3n in this embedded tool definition setup.
                tool_output_message = f"The tool '{tool_name}' returned the following result: {tool_output}. Please provide a natural language answer based on this."
                chat_history.append({"role": "user", "content": tool_output_message})

                # Get the final natural language response from the LLM
                final_llm_response = call_ollama_llm(tool_output_message, chat_history) # Pass the updated history

                if final_llm_response["type"] == "text":
                    print(f"LLM (gemma3n:latest) final response based on tool output:")
                    print(final_llm_response["content"])
                    chat_history.append({"role": "assistant", "content": final_llm_response["content"]}) # Add final response to history
                else:
                    print("LLM did not provide a final content response after tool execution.")
                    chat_history.append({"role": "assistant", "content": "Error: LLM did not provide a final response after tool execution."})


            except ValueError as e:
                print(f"Error executing tool: {e}")
                error_message = f"An error occurred trying to get that information: {e}"
                print(f"LLM (gemma3n:latest) response: {error_message}")
                chat_history.append({"role": "assistant", "content": error_message})
            except ollama.ResponseError as e:
                print(f"Ollama API Error during follow-up: {e}")
                error_message = f"An Ollama API error occurred during follow-up: {e}"
                print(f"LLM (gemma3n:latest) response: {error_message}")
                chat_history.append({"role": "assistant", "content": error_message})

        elif llm_response["type"] == "text":
            print(f"LLM (gemma3n:latest) response: {llm_response['content']}")
            chat_history.append({"role": "assistant", "content": llm_response["content"]}) # Add LLM's text response to history
        else:
            print("LLM (gemma3n:latest) returned an unexpected response type.")
            chat_history.append({"role": "assistant", "content": "Error: LLM returned an unexpected response type."})

if __name__ == "__main__":
    main()
