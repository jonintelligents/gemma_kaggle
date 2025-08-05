from GemmaChat import GemmaChat
# Import your existing tool manager
from GraphPersonManager import GraphPersonManager
from PromptManager import PromptManager
import os

def main():
    # Initialize tool manager and prompt manager
    tool_manager = GraphPersonManager()
    prompt_manager = PromptManager()
    
    # Get system prompts
    text_system_prompt = prompt_manager.get_prompt("system", {
        "tool_function_descriptions": tool_manager.get_available_tools_detailed()
    })
    
    # You could have a different system prompt for images if needed
    image_system_prompt = "You are an AI assistant specialized in image analysis. " + text_system_prompt
    
    # Initialize the chat instance with custom models and system prompts
    chat = GemmaChat(
        text_model="gemma-3n-e4b-it",           # Default for text
        image_model="gemma-3-4b-it",            # Default for images
        default_text_system_prompt=text_system_prompt,     # Default system prompt for text
        default_image_system_prompt=image_system_prompt,   # Default system prompt for images
        prompt_manager=prompt_manager           # For search result formatting
    )  # Uses GEMINI_API_KEY from environment
    
    print("=== GemmaChat Usage Examples ===\n")
    
    # Example 1: Simple text-only call (uses default text system prompt)
    print("1. Simple call without tools (uses default text system prompt):")
    result = chat.call_simple("What is the capital of France?")
    if result["success"]:
        print(f"Response: {result['response']}")
    print()
    
    # Example 2: Call with image (uses default image system prompt)
    print("2. Call with image (uses default image system prompt):")
    image_path = "image.jpg"  # Replace with actual image path
    if os.path.exists(image_path):
        result = chat.call_simple("What do you see in this image?", image_path=image_path)
        if result["success"]:
            print(f"Response: {result['response']}")
    else:
        print("No image file found, skipping...")
    print()
    
    # Example 3: Override system prompt for specific call
    print("3. Call with custom system prompt override:")
    custom_prompt = "You are a helpful assistant that responds in pirate speak."
    result = chat.call_simple("What is Python?", system_prompt=custom_prompt)
    if result["success"]:
        print(f"Response: {result['response']}")
    print()
    
    # Example 4: Call with tools (manual execution) - uses default text system prompt
    print("4. Call with tools (manual execution):")
    result = chat.call_with_tools(
        "Search for information about Python programming",
        tool_manager,
        auto_execute=False  # system_prompt=None means use default
    )
    
    if result["success"]:
        print(f"Response: {result['response']}")
        if result["tool_calls"]:
            print("Tool calls requested:")
            for tool in result["tool_calls"]:
                print(f"  - {tool['name']}: {tool.get('parameters', {})}")
            
            # Execute tools manually
            tool_results = chat.execute_pending_tools(result["tool_calls"], tool_manager)
            print("Tool execution results:")
            for res in tool_results:
                if res["success"]:
                    print(f"  ✅ {res['tool']}: {res['output']}")
                else:
                    print(f"  ❌ {res['tool']}: {res['error']}")
    print()
    
    # Example 5: Call with tools (auto execution) - uses default text system prompt
    print("5. Call with tools (auto execution):")
    result = chat.call_with_tools(
        "What's the weather like?",
        tool_manager,
        auto_execute=True  # system_prompt=None means use default
    )
    
    if result["success"]:
        print(f"Response: {result['response']}")
        if result.get("tool_results"):  # Use .get() to avoid KeyError
            print("Tools were automatically executed:")
            for res in result["tool_results"]:
                if res["success"]:
                    print(f"  ✅ {res['tool']}")
                else:
                    print(f"  ❌ {res['tool']}: {res['error']}")
    print()
    
    # Example 6: Interactive chat session (uses appropriate defaults automatically)
    print("6. Starting interactive chat session...")
    print("You can now chat interactively. Use @/path/to/image.jpg to include images.")
    print("Commands: 'exit', 'clear', 'history'")
    print("System prompts will be automatically selected based on content type.")
    
    # This will start an interactive session
    chat.start_chat_session(
        tool_manager=tool_manager,
        # system_prompt=None means use defaults (text or image based on content)
        auto_execute_tools=False  # Set to True for automatic tool execution
    )

if __name__ == "__main__":
    main()

# Alternative: Quick usage patterns

def quick_examples():
    """Quick usage patterns for common scenarios"""
    
    # Initialize
    chat = GemmaChat()
    
    # 1. Quick text question
    result = chat.call_simple("Explain quantum computing in simple terms")
    print(result["response"] if result["success"] else f"Error: {result['error']}")
    
    # 2. Question with image
    result = chat.call_simple(
        "What objects do you see in this image?", 
        image_path="photo.jpg"
    )
    
    # 3. One-shot tool call
    from GraphPersonManager import GraphPersonManager
    tool_manager = GraphPersonManager()
    
    result = chat.call_with_tools(
        "Search for the latest news about AI",
        tool_manager,
        auto_execute=True
    )
    
    # 4. Start interactive session with tools
    chat.start_chat_session(tool_manager=tool_manager)

# Integration with your existing code
def integrate_with_existing():
    """How to integrate with your existing main.py structure"""
    
    # Replace your call_gemini_llm function with:
    chat = GemmaChat()
    
    # For single prompts (replace run_single_prompt):
    def run_single_prompt_new(prompt, tool_manager, client, system_prompt, 
                             retry_count=3, image_path=None):
        result = chat.call_with_tools(
            prompt, 
            tool_manager, 
            system_prompt, 
            image_path=image_path,
            max_retries=retry_count,
            auto_execute=True
        )
        
        if result["success"]:
            print(f"Response: {result['response']}")
            if result.get("tool_results"):  # Use .get() to avoid KeyError
                print("Tools executed:")
                for res in result["tool_results"]:
                    if res["success"]:
                        print(f"✅ {res['tool']}")
        else:
            print(f"Error: {result['error']}")
    
    # For chat mode (replace run_chat_mode):
    def run_chat_mode_new(tool_manager, client, system_prompt):
        chat.start_chat_session(
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            auto_execute_tools=False  # Ask before executing
        )