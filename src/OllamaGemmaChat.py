import json
import os
import logging
import base64
from pathlib import Path
from ollama import chat, ChatResponse
from typing import Optional, List, Dict, Any

class OllamaGemmaChat:
    """
    A class to encapsulate Ollama Gemma API calls with support for chat sessions,
    single prompts, tool calling, and image processing.
    """
    
    def __init__(self, text_model: str = "gemma3n:e4b", 
                 image_model: str = "gemma3n:e4b", default_text_system_prompt: Optional[str] = None,
                 default_image_system_prompt: Optional[str] = None, prompt_manager=None,
                 host: Optional[str] = None):
        """
        Initialize the OllamaGemmaChat instance.
        
        Args:
            text_model: Model name to use for text-only requests
            image_model: Model name to use for requests with images
            default_text_system_prompt: Default system prompt for text-only requests
            default_image_system_prompt: Default system prompt for image requests
            prompt_manager: Optional prompt manager for search result formatting
            host: Optional Ollama host URL (defaults to http://localhost:11434)
        """
        self.text_model = text_model
        self.image_model = image_model
        self.default_text_system_prompt = default_text_system_prompt
        self.default_image_system_prompt = default_image_system_prompt
        self.prompt_manager = prompt_manager
        self.chat_history = []
        self.host = host
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def validate_image_file(self, image_path: str) -> bool:
        """Validate that the image file exists and has a supported format."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        supported_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_extension = Path(image_path).suffix.lower()
        
        if file_extension not in supported_extensions:
            raise ValueError(f"Unsupported image format: {file_extension}. Supported formats: {', '.join(supported_extensions)}")
        
        return True
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image file to base64 string."""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
        except Exception as e:
            raise Exception(f"Failed to encode image: {e}")
    
    def get_image_mime_type(self, image_path: str) -> str:
        """Get MIME type for the image file."""
        extension = Path(image_path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(extension, 'image/jpeg')
    
    def _get_effective_system_prompt(self, provided_system_prompt: Optional[str], 
                                   has_image: bool) -> Optional[str]:
        """Get the effective system prompt to use based on context."""
        # If explicitly provided, use that
        if provided_system_prompt is not None:
            return provided_system_prompt
        
        # Otherwise use appropriate default
        if has_image and self.default_image_system_prompt:
            return self.default_image_system_prompt
        elif not has_image and self.default_text_system_prompt:
            return self.default_text_system_prompt
        
        return None
    
    def _format_search_results(self, search_results: str) -> str:
        """
        Format search results using the prompt manager if available.
        
        Args:
            search_results: Raw search results to format
            
        Returns:
            Formatted search results or original if no prompt manager
        """
        if not self.prompt_manager:
            return search_results
            
        try:
            # Get the search filter prompt
            filter_prompt = self.prompt_manager.get_prompt("search_filter", {"search_results": search_results})
            
            # Make a simple call to format the results (no history, no tools)
            result = self.call_simple(
                filter_prompt, 
                include_history=False  # Don't include chat history for formatting
            )
            
            if result["success"]:
                return result["response"]
            else:
                self.logger.warning(f"Failed to format search results: {result.get('error')}")
                return search_results
                
        except Exception as e:
            self.logger.warning(f"Error formatting search results: {e}")
            return search_results
    
    def _prepare_messages(self, prompt: str, system_prompt: Optional[str] = None, 
                         image_path: Optional[str] = None, include_history: bool = True) -> List[Dict[str, Any]]:
        """Prepare messages for Ollama API call."""
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add conversation history if requested
        if include_history and self.chat_history:
            for message in self.chat_history:
                # Ensure content is always a string
                content = message["content"]
                if isinstance(content, dict):
                    # If content is a dict, extract the text or convert to string
                    content = content.get("text", str(content))
                elif not isinstance(content, str):
                    content = str(content)
                
                messages.append({
                    "role": message["role"],
                    "content": content
                })
        
        # Prepare user message
        user_message = {
            "role": "user",
            "content": str(prompt)  # Ensure prompt is always a string
        }
        
        # Add image if provided
        if image_path:
            self.validate_image_file(image_path)
            image_base64 = self.encode_image_to_base64(image_path)
            user_message["images"] = [image_base64]
        
        messages.append(user_message)
        return messages
    
    def _extract_json_from_codeblock(self, llm_content):
        """Extract JSON from code blocks if present."""
        parts = llm_content.split("```")
        if len(parts) >= 3:
            # Take the middle part (index 1)
            json_part = parts[1]
            # Remove language identifier if present (first line)
            lines = json_part.split('\n', 1)
            if len(lines) > 1 and lines[0].strip().lower() in ['json', 'javascript', 'js', '']:
                return lines[1].strip()
            return json_part.strip()
        return llm_content

    def _make_api_call(self, messages: List[Dict[str, Any]], has_image: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """Make the actual Ollama API call with retry logic."""
        # Select appropriate model based on whether image is included
        model = self.image_model if has_image else self.text_model
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Making Ollama API call - attempt {attempt + 1}/{max_retries} using model: {model}")
                print(f"🤖 Using model: {model}")
                
                # Prepare chat arguments
                chat_args = {
                    'model': model,
                    'messages': messages
                }
                
                # Add host if specified
                if self.host:
                    chat_args['host'] = self.host
                
                response: ChatResponse = chat(**chat_args)
                
                # Extract content from response
                llm_content = response.message.content.strip()
                
                # Clean up JSON markdown formatting
                llm_content = self._extract_json_from_codeblock(llm_content)

                # Try to parse as JSON first (for tool calls)
                try:
                    parsed = json.loads(llm_content)
                    return {
                        "success": True,
                        "type": "json",
                        "content": parsed,
                        "raw_content": llm_content
                    }
                except json.JSONDecodeError:
                    # Not JSON, return as text
                    return {
                        "success": True,
                        "type": "text",
                        "content": llm_content,
                        "raw_content": llm_content
                    }
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"API error on attempt {attempt + 1}/{max_retries}. Retrying... Error: {e}")
                    continue
                else:
                    self.logger.error(f"API error after {max_retries} attempts. Final error: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "content": None
                    }
        
        return {"success": False, "error": "Maximum retry attempts exceeded", "content": None}
    
    def call_with_tools(self, prompt: str, tool_manager, system_prompt: Optional[str] = None,
                       image_path: Optional[str] = None, max_retries: int = 3, 
                       auto_execute: bool = False) -> Dict[str, Any]:
        """
        Make a call that can execute tools.
        
        Args:
            prompt: User prompt
            tool_manager: Tool manager instance with execute_tool method
            system_prompt: Optional system prompt (if None, uses default based on whether image is present)
            image_path: Optional path to image file
            max_retries: Number of retry attempts
            auto_execute: If True, automatically execute tools. If False, return tool calls for manual execution
            
        Returns:
            Dict with result information
        """
        # Get effective system prompt
        effective_system_prompt = self._get_effective_system_prompt(system_prompt, bool(image_path))
        
        # Prepare messages
        messages = self._prepare_messages(prompt, effective_system_prompt, image_path)
        
        # Make API call
        result = self._make_api_call(messages, has_image=bool(image_path), max_retries=max_retries)
        
        print(result)

        if not result["success"]:
            return result
        
        # Add to history
        self.chat_history.append({"role": "user", "content": str(prompt)})
        
        if result["type"] == "json":
            parsed = result["content"]
            response_text = parsed.get("response", "").strip()
            tool_calls = parsed.get("tool_calls", [])
            
            if not tool_calls:
                # No tools, just regular response
                self.chat_history.append({"role": "assistant", "content": str(response_text)})
                return {
                    "success": True,
                    "type": "text_response",
                    "response": response_text,
                    "tool_calls": [],
                    "tool_results": []  # Add empty tool_results for consistency
                }
            else:
                # Tools requested
                result_data = {
                    "success": True,
                    "type": "tool_calls",
                    "response": response_text,
                    "tool_calls": tool_calls,
                    "tool_results": []
                }
                
                if auto_execute:
                    # Execute tools automatically
                    for tool in tool_calls:
                        try:
                            tool_output = tool_manager.execute_tool(tool["name"], tool.get("parameters", {}))
                            
                            # Print tool execution output
                            print(f"\n✅ Tool '{tool['name']}' executed. Output: {tool_output}")
                            if isinstance(tool_output, dict) and 'result' in tool_output:
                                print(tool_output['result'])
                            
                            # Format search results if this is a search tool
                            if tool['name'] == 'search' and isinstance(tool_output, dict) and 'result' in tool_output:
                                formatted_results = self._format_search_results(tool_output['result'])
                                print("\n📄 Formatted Results:")
                                print(formatted_results)
                                # Update the tool output with formatted results
                                tool_output['result'] = formatted_results
                            
                            result_data["tool_results"].append({
                                "tool": tool["name"],
                                "success": True,
                                "output": tool_output
                            })
                            
                            # Add to chat history - ensure content is string
                            tool_result_text = f"Executed tool '{tool['name']}' with result: {tool_output}"
                            self.chat_history.append({
                                "role": "assistant",
                                "content": str(tool_result_text)
                            })
                            
                        except Exception as e:
                            self.logger.error(f"Tool execution failed: {e}")
                            result_data["tool_results"].append({
                                "tool": tool["name"],
                                "success": False,
                                "error": str(e)
                            })
                
                return result_data
        else:
            # Text response
            self.chat_history.append({"role": "assistant", "content": str(result["content"])})
            return {
                "success": True,
                "type": "text_response",
                "response": result["content"],
                "tool_calls": [],
                "tool_results": []  # Add empty tool_results for consistency
            }
    
    def call_simple(self, prompt: str, system_prompt: Optional[str] = None,
                   image_path: Optional[str] = None, max_retries: int = 3,
                   include_history: bool = True) -> Dict[str, Any]:
        """
        Make a simple call without tool execution capability.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (if None, uses default based on whether image is present)
            image_path: Optional path to image file
            max_retries: Number of retry attempts
            include_history: Whether to include chat history in the call
            
        Returns:
            Dict with response information
        """
        # Get effective system prompt
        effective_system_prompt = self._get_effective_system_prompt(system_prompt, bool(image_path))
        
        # Prepare messages
        messages = self._prepare_messages(prompt, effective_system_prompt, image_path, include_history)
        
        # Make API call
        result = self._make_api_call(messages, has_image=bool(image_path), max_retries=max_retries)
        
        if not result["success"]:
            return result
        
        # Add to history if including history
        if include_history:
            self.chat_history.append({"role": "user", "content": str(prompt)})
            self.chat_history.append({"role": "assistant", "content": str(result["content"])})
        
        return {
            "success": True,
            "type": "simple_response",
            "response": result["content"]
        }
    
    def start_chat_session(self, tool_manager=None, system_prompt: Optional[str] = None,
                          auto_execute_tools: bool = False):
        """
        Start an interactive chat session.
        
        Args:
            tool_manager: Optional tool manager for tool execution
            system_prompt: Optional system prompt (if None, uses defaults based on content type)
            auto_execute_tools: Whether to automatically execute tools or ask for confirmation
        """
        print("🎯 Welcome to Ollama Gemma Chat!")
        print("Type 'exit' to quit, 'clear' to clear history, 'history' to show conversation history")
        
        if tool_manager:
            print(f"🔧 Tools available: {', '.join(tool_manager.get_available_tools())}")
        
        print()
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() == "exit":
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == "clear":
                    self.clear_history()
                    print("🧹 Chat history cleared!")
                    continue
                elif user_input.lower() == "history":
                    self.print_history()
                    continue
                elif not user_input:
                    continue
                
                # Check if image path is provided (simple format: @/path/to/image.jpg message)
                image_path = None
                if user_input.startswith("@"):
                    parts = user_input.split(" ", 1)
                    if len(parts) == 2:
                        potential_path = parts[0][1:]  # Remove @
                        if os.path.exists(potential_path):
                            image_path = potential_path
                            user_input = parts[1]
                            print(f"📷 Including image: {image_path}")
                
                if tool_manager:
                    # Use tool-enabled call (will automatically select appropriate system prompt)
                    result = self.call_with_tools(
                        user_input, tool_manager, system_prompt, 
                        image_path, auto_execute=auto_execute_tools
                    )
                    
                    if result["success"]:
                        print(f"Assistant: {result['response']}")
                        
                        if result["type"] == "tool_calls" and not auto_execute_tools:
                            if result["tool_calls"]:
                                print("\n🔧 Tool calls requested:")
                                for i, tool in enumerate(result["tool_calls"], 1):
                                    print(f"{i}. {tool['name']} with parameters: {tool.get('parameters', {})}")
                                
                                proceed = input("\nExecute tools? (yes/No): ").strip().lower()
                                if proceed == "yes":
                                    for tool in result["tool_calls"]:
                                        try:
                                            tool_output = tool_manager.execute_tool(tool["name"], tool.get("parameters", {}))
                                            
                                            print(f"✅ Tool '{tool['name']}' executed: {tool_output}")
                                            if isinstance(tool_output, dict) and 'result' in tool_output:
                                                print(tool_output['result'])
                                            
                                            # Format search results if this is a search tool
                                            if tool['name'] == 'search' and isinstance(tool_output, dict) and 'result' in tool_output:
                                                formatted_results = self._format_search_results(tool_output['result'])
                                                print("\n📄 Formatted Results:")
                                                print(formatted_results)
                                                # Update the tool output with formatted results
                                                tool_output['result'] = formatted_results
                                            
                                            # Add to chat history
                                            self.chat_history.append({
                                                "role": "assistant",
                                                "content": f"Executed tool '{tool['name']}' with result: {tool_output}"
                                            })
                                        except Exception as e:
                                            print(f"❌ Error executing tool '{tool['name']}': {e}")
                                else:
                                    print("Tool execution cancelled.")
                    else:
                        print(f"❌ Error: {result.get('error', 'Unknown error')}")
                else:
                    # Use simple call (will automatically select appropriate system prompt)
                    result = self.call_simple(user_input, system_prompt, image_path)
                    
                    if result["success"]:
                        print(f"Assistant: {result['response']}")
                    else:
                        print(f"❌ Error: {result.get('error', 'Unknown error')}")
                
            except KeyboardInterrupt:
                print("\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ An error occurred: {e}")
                self.logger.error(f"Chat session error: {e}", exc_info=True)
    
    def execute_pending_tools(self, tool_calls: List[Dict], tool_manager) -> List[Dict]:
        """
        Execute a list of pending tool calls.
        
        Args:
            tool_calls: List of tool call dictionaries
            tool_manager: Tool manager instance
            
        Returns:
            List of execution results
        """
        results = []
        for tool in tool_calls:
            try:
                tool_output = tool_manager.execute_tool(tool["name"], tool.get("parameters", {}))
                
                # Format search results if this is a search tool
                if tool['name'] == 'search' and isinstance(tool_output, dict) and 'result' in tool_output:
                    formatted_results = self._format_search_results(tool_output['result'])
                    print(f"📄 Formatted search results:\n{formatted_results}")
                    # Update the tool output with formatted results
                    tool_output['result'] = formatted_results
                
                results.append({
                    "tool": tool["name"],
                    "success": True,
                    "output": tool_output
                })
                
                # Add to chat history - ensure content is string
                tool_result_text = f"Executed tool '{tool['name']}' with result: {tool_output}"
                self.chat_history.append({
                    "role": "assistant",
                    "content": str(tool_result_text)
                })
                
            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")
                results.append({
                    "tool": tool["name"],
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def clear_history(self):
        """Clear the chat history."""
        self.chat_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get the current chat history."""
        return self.chat_history.copy()
    
    def print_history(self):
        """Print the chat history in a readable format."""
        if not self.chat_history:
            print("No conversation history.")
            return
        
        print("\n--- Chat History ---")
        for i, message in enumerate(self.chat_history, 1):
            role = message["role"].capitalize()
            content = message["content"]
            print(f"{i}. {role}: {content}")
        print("--- End History ---\n")


# Example usage
if __name__ == "__main__":
    # Initialize the chat client
    chat_client = OllamaGemmaChat(
        text_model="gemma3n:e4b",
        default_text_system_prompt="You are a helpful AI assistant."
    )
    
    # Simple example
    result = chat_client.call_simple("What is the capital of France?")
    if result["success"]:
        print(f"Response: {result['response']}")
    else:
        print(f"Error: {result['error']}")