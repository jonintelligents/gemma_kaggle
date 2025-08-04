import streamlit as st
import json
import os
import base64
from PIL import Image
from pathlib import Path
import tempfile
import logging
from datetime import datetime
import io
import traceback

from gemma_chat import GemmaChat
from GraphPersonManager import GraphPersonManager
from PromptManager import PromptManager

MODULES_AVAILABLE = True

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Page configuration
st.set_page_config(
    page_title="LLM Tool Demo with GemmaChat",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "gemma_chat" not in st.session_state:
        st.session_state.gemma_chat = None
    if "tool_manager" not in st.session_state:
        st.session_state.tool_manager = None
    if "prompt_manager" not in st.session_state:
        st.session_state.prompt_manager = None
    if "system_prompts" not in st.session_state:
        st.session_state.system_prompts = {}
    if "api_initialized" not in st.session_state:
        st.session_state.api_initialized = False

# Image processing functions
def validate_image_file(uploaded_file):
    """Validate uploaded image file."""
    if uploaded_file is None:
        return False
    
    supported_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    file_extension = Path(uploaded_file.name).suffix.lower()
    
    if file_extension not in supported_extensions:
        st.error(f"Unsupported image format: {file_extension}. Supported formats: {', '.join(supported_extensions)}")
        return False
    
    return True

def save_uploaded_file_temporarily(uploaded_file):
    """Save uploaded file temporarily and return the path."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Failed to save uploaded file: {e}")
        return None

# Setup functions
def initialize_managers_and_chat(api_key):
    """Initialize all managers and GemmaChat instance."""
    try:
        # Set API key in environment
        os.environ['GEMINI_API_KEY'] = api_key
        
        # Initialize managers
        prompt_manager = PromptManager()
        tool_manager = GraphPersonManager()  # or ExamplePersonToolManager()
        
        # Setup unified system prompt for both text and images
        unified_system_prompt = prompt_manager.get_prompt("system", {
            "tool_function_descriptions": tool_manager.get_available_tools_detailed()
        })
        
        # Initialize GemmaChat with the same system prompt for both text and images
        gemma_chat = GemmaChat(
            text_model="gemma-3n-e4b-it",           # Default for text
            image_model="gemma-3-4b-it",            # Default for images
            default_text_system_prompt=unified_system_prompt,
            default_image_system_prompt=unified_system_prompt,  # Same prompt for images
            prompt_manager=prompt_manager
        )
        
        return gemma_chat, tool_manager, prompt_manager, {
            "unified": unified_system_prompt
        }
        
    except Exception as e:
        st.error(f"Failed to initialize managers and chat: {e}")
        return None, None, None, None

# UI Helper functions
def display_message(message, is_user=True):
    """Display a chat message."""
    if is_user:
        with st.chat_message("user"):
            if message.get("image_path"):
                try:
                    st.image(message["image_path"], width=300)
                except:
                    st.write(f"🖼️ Image: {message['image_path']}")
            if message.get("audio_name"):
                st.write(f"🎵 Audio file: {message['audio_name']}")
            st.write(message["text"])
    else:
        with st.chat_message("assistant"):
            st.write(message["text"])
            if message.get("tool_results"):
                with st.expander("Tool Execution Details"):
                    for result in message["tool_results"]:
                        if not result.get("success", True):
                            st.error(f"❌ Tool '{result['tool']}' failed: {result.get('error', 'Unknown error')}")
                        else:
                            st.success(f"✅ Tool '{result['tool']}' executed successfully")
                            if "output" in result:
                                st.json(result["output"])

def handle_chat_response(result, user_message):
    """Handle the response from GemmaChat and update chat history."""
    if result["success"]:
        # Add AI response to chat history
        ai_message = {
            "role": "assistant",
            "text": result["response"],
            "tool_results": result.get("tool_results", []),
            "timestamp": datetime.now()
        }
        st.session_state.chat_messages.append(ai_message)
        
        # Clean up temporary files
        if user_message.get("temp_image_path") and os.path.exists(user_message["temp_image_path"]):
            try:
                os.unlink(user_message["temp_image_path"])
            except:
                pass
                
        return True
    else:
        st.error(f"Error: {result['error']}")
        return False

def get_default_prompt_for_image():
    """Return the default prompt when an image is uploaded without text."""
    return "Extract the information about this person from the image and store them"

def main():
    st.title("🤖 LLM Tool Demo with GemmaChat")
    
    if not MODULES_AVAILABLE:
        st.stop()
    
    initialize_session_state()
    
    # Sidebar for application info and tools
    with st.sidebar:
        st.header("📋 Application Info")
        st.write("**LLM Tool Demo** - Interactive chat interface with automated tool execution for person information management.")
        
        # Check for API key in environment first
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            # API Key input if not in environment
            st.header("🔑 API Configuration")
            api_key = st.text_input("Gemini API Key", type="password", 
                                   help="Enter your Google Gemini API key (or set GEMINI_API_KEY environment variable)")
        
        if api_key and not st.session_state.api_initialized:
            with st.spinner("Initializing GemmaChat and managers..."):
                gemma_chat, tool_manager, prompt_manager, system_prompts = initialize_managers_and_chat(api_key)
                
                if gemma_chat and tool_manager and prompt_manager:
                    st.session_state.gemma_chat = gemma_chat
                    st.session_state.tool_manager = tool_manager
                    st.session_state.prompt_manager = prompt_manager
                    st.session_state.system_prompts = system_prompts
                    st.session_state.api_initialized = True
                    st.rerun()
        
        if st.session_state.api_initialized:
            # Model information
            st.header("🤖 Models")
            st.write("• **Text:** gemma-3n-e4b-it")
            st.write("• **Images:** gemma-3-4b-it")
            
            # Available tools
            st.header("🛠️ Available Tools")
            if st.session_state.tool_manager:
                try:
                    available_tools = st.session_state.tool_manager.get_available_tools()
                    for tool in available_tools:
                        st.write(f"🔧 {tool}")
                except Exception as e:
                    st.error(f"Error loading tools: {e}")
        else:
            if not api_key:
                st.warning("⚠️ Please set GEMINI_API_KEY environment variable or enter your API key above")
    
    if not st.session_state.api_initialized:
        st.warning("Please set GEMINI_API_KEY environment variable or configure your API key in the sidebar to get started.")
        return
    
    # Main interface tabs (removed Advanced Settings tab)
    tab1, tab2 = st.tabs(["💬 Chat Mode", "⚡ One-Shot Prompts"])
    
    with tab1:
        st.header("Chat Mode")
        st.write("Have a conversation with the AI. Tool calls will be executed automatically.")
        
        # Settings for chat mode
        auto_execute = st.checkbox("Auto-execute tools", value=True, key="chat_auto_exec")
        
        # Display chat history
        for message in st.session_state.chat_messages:
            display_message(message, is_user=message["role"] == "user")
        
        # Chat input area
        chat_prompt = st.text_input("Type your message:", key="chat_input")
        
        # Send button
        if st.button("Send", key="chat_send"):
            if chat_prompt:
                # Add user message to chat history
                user_message = {
                    "role": "user",
                    "text": chat_prompt,
                    "timestamp": datetime.now()
                }
                st.session_state.chat_messages.append(user_message)
                
                # Get AI response using GemmaChat
                with st.spinner("Processing..."):
                    result = st.session_state.gemma_chat.call_with_tools(
                        chat_prompt,
                        st.session_state.tool_manager,
                        auto_execute=auto_execute
                    )
                
                # Handle response
                if handle_chat_response(result, user_message):
                    st.rerun()
            else:
                st.warning("Please enter a message.")
        
        # Clear chat button
        if st.button("Clear Chat History", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()
    
    with tab2:
        st.header("One-Shot Prompts")
        st.write("Send individual prompts with automatic tool execution.")
        st.info("💡 Tip: You can upload an image without text - the system will automatically extract person information from the image.")
        
        # Settings for one-shot mode
        oneshot_auto_execute = st.checkbox("Auto-execute tools", value=True, key="oneshot_auto_exec")
        
        # One-shot input area
        oneshot_prompt = st.text_area(
            "Enter your prompt (optional if uploading image):", 
            height=100,
            key="oneshot_input"
        )
        
        oneshot_image = st.file_uploader(
            "Upload image (optional)", 
            type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
            key="oneshot_image"
        )
        
        if oneshot_image:
            st.image(oneshot_image, caption="Uploaded Image", width=300)
        
        # Submit button
        if st.button("Submit", key="oneshot_submit"):
            # Check if we have either text or image
            if oneshot_prompt or oneshot_image:
                temp_image_path = None
                actual_prompt = oneshot_prompt
                
                # Handle image upload
                if oneshot_image and validate_image_file(oneshot_image):
                    temp_image_path = save_uploaded_file_temporarily(oneshot_image)
                    if not temp_image_path:
                        st.error("Failed to process uploaded image")
                        return
                    
                    # If no text prompt provided with image, use default
                    if not oneshot_prompt.strip():
                        actual_prompt = get_default_prompt_for_image()
                        st.info(f"Using default prompt: '{actual_prompt}'")
                
                # Show user prompt
                st.subheader("Your Prompt:")
                st.write(actual_prompt)
                
                if oneshot_image:
                    st.image(oneshot_image, width=300)
                
                # Get AI response using GemmaChat
                with st.spinner("Processing..."):
                    if oneshot_auto_execute:
                        result = st.session_state.gemma_chat.call_with_tools(
                            actual_prompt,
                            st.session_state.tool_manager,
                            image_path=temp_image_path,
                            auto_execute=True
                        )
                    else:
                        # Manual tool execution
                        result = st.session_state.gemma_chat.call_with_tools(
                            actual_prompt,
                            st.session_state.tool_manager,
                            image_path=temp_image_path,
                            auto_execute=False
                        )
                        
                        # If there are tool calls, ask user to confirm
                        if result["success"] and result.get("tool_calls"):
                            st.subheader("Tools to Execute:")
                            for tool in result["tool_calls"]:
                                st.write(f"- **{tool['name']}**: {tool.get('parameters', {})}")
                            
                            if st.button("Execute Tools", key="execute_tools"):
                                with st.spinner("Executing tools..."):
                                    tool_results = st.session_state.gemma_chat.execute_pending_tools(
                                        result["tool_calls"], 
                                        st.session_state.tool_manager
                                    )
                                    result["tool_results"] = tool_results
                
                # Display response
                st.subheader("AI Response:")
                if result["success"]:
                    st.write(result["response"])
                    
                    if result.get("tool_results"):
                        st.subheader("Tool Execution Results:")
                        for tool_result in result["tool_results"]:
                            if not tool_result.get("success", True):
                                st.error(f"❌ Tool '{tool_result['tool']}' failed: {tool_result.get('error', 'Unknown error')}")
                            else:
                                st.success(f"✅ Tool '{tool_result['tool']}' executed successfully")
                                with st.expander(f"View {tool_result['tool']} results"):
                                    if "output" in tool_result:
                                        st.json(tool_result["output"])
                else:
                    st.error(f"Error: {result['error']}")
                
                # Clean up temporary file
                if temp_image_path and os.path.exists(temp_image_path):
                    try:
                        os.unlink(temp_image_path)
                    except:
                        pass
                        
            else:
                st.warning("Please enter a prompt or upload an image before submitting.")

if __name__ == "__main__":
    main()