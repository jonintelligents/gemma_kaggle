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

from google import genai
from ToolManager import ExamplePersonToolManager
from GraphPersonManager import GraphPersonManager
from PromptManager import PromptManager
MODULES_AVAILABLE = True

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Page configuration
st.set_page_config(
    page_title="LLM Tool Demo",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "client" not in st.session_state:
        st.session_state.client = None
    if "tool_manager" not in st.session_state:
        st.session_state.tool_manager = None
    if "prompt_manager" not in st.session_state:
        st.session_state.prompt_manager = None
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = None
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

def encode_image_to_base64(image_bytes):
    """Encode image bytes to base64 string."""
    try:
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')
        return encoded_string
    except Exception as e:
        raise Exception(f"Failed to encode image: {e}")

def get_image_mime_type(filename):
    """Get MIME type for the image file."""
    extension = Path(filename).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    return mime_types.get(extension, 'image/jpeg')

# Audio processing functions
def validate_audio_file(uploaded_file):
    """Validate uploaded audio file."""
    if uploaded_file is None:
        return False
    
    supported_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}
    file_extension = Path(uploaded_file.name).suffix.lower()
    
    if file_extension not in supported_extensions:
        st.error(f"Unsupported audio format: {file_extension}. Supported formats: {', '.join(supported_extensions)}")
        return False
    
    return True

def encode_audio_to_base64(audio_bytes):
    """Encode audio bytes to base64 string."""
    try:
        encoded_string = base64.b64encode(audio_bytes).decode('utf-8')
        return encoded_string
    except Exception as e:
        raise Exception(f"Failed to encode audio: {e}")

def get_audio_mime_type(filename):
    """Get MIME type for the audio file."""
    extension = Path(filename).suffix.lower()
    mime_types = {
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.flac': 'audio/flac',
        '.ogg': 'audio/ogg'
    }
    return mime_types.get(extension, 'audio/wav')

# Setup functions
def setup_gemini_api(api_key):
    """Setup Gemini API client."""
    try:
        os.environ['GEMINI_API_KEY'] = api_key
        client = genai.Client()
        return client
    except Exception as e:
        st.error(f"Failed to setup Gemini API: {e}")
        return None

def initialize_managers():
    """Initialize tool and prompt managers."""
    try:
        # Initialize prompt manager
        prompt_manager = PromptManager()
        
        # Initialize tool manager (you can switch between ExamplePersonToolManager and GraphPersonManager)
        tool_manager = GraphPersonManager()  # or ExamplePersonToolManager()
        
        # Setup system prompt
        system_prompt = prompt_manager.get_prompt("system", {
            "tool_function_descriptions": tool_manager.get_available_tools_detailed()
        })
        
        return tool_manager, prompt_manager, system_prompt
    except Exception as e:
        st.error(f"Failed to initialize managers: {e}")
        return None, None, None

# Main LLM calling function (adapted from your original)
def call_gemini_llm(user_query, chat_history, client, system_prompt, tool_manager, 
                   is_chat_mode=True, max_retries=3, image_data=None, audio_data=None):
    """Call Gemini LLM with tool support."""
    
    for attempt in range(max_retries):
        try:
            # Build context
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

            # Prepare the content for the API call
            parts = [{"text": full_context}]
            
            # Add image if provided
            if image_data:
                parts.append({
                    "inline_data": {
                        "mime_type": image_data["mime_type"],
                        "data": image_data["base64"]
                    }
                })
            
            # Add audio if provided
            if audio_data:
                parts.append({
                    "inline_data": {
                        "mime_type": audio_data["mime_type"],
                        "data": audio_data["base64"]
                    }
                })

            # Create content structure
            if image_data or audio_data:
                contents = [{"role": "user", "parts": parts}]
            else:
                contents = full_context

            # Make the API call
            response = client.models.generate_content(
                model="gemma-3-4b-it",
                contents=contents
            )

            llm_content = response.text.strip()

            # Clean up JSON if wrapped in code blocks
            if llm_content.startswith("```json") and llm_content.endswith("```"):
                llm_content = llm_content[7:-3].strip()

            try:
                parsed = json.loads(llm_content)
                
                response_text = parsed.get("response", "").strip()
                tool_calls = parsed.get("tool_calls", [])

                if not tool_calls:
                    return {"type": "text", "content": response_text}
                else:
                    # Handle tool calls
                    tool_results = []
                    for tool in tool_calls:
                        try:
                            tool_output = tool_manager.execute_tool(
                                tool["name"], 
                                tool.get("parameters", {})
                            )
                            tool_results.append({
                                "tool": tool["name"],
                                "parameters": tool.get("parameters", {}),
                                "result": tool_output
                            })
                            
                            # Special handling for search results
                            if tool["name"] == "search":
                                # You might want to format search results here
                                pass
                                
                        except Exception as e:
                            tool_results.append({
                                "tool": tool["name"],
                                "parameters": tool.get("parameters", {}),
                                "error": str(e)
                            })
                    
                    return {
                        "type": "tool_calls",
                        "content": response_text,
                        "tool_results": tool_results
                    }
                    
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    continue
                else:
                    return {"type": "text", "content": llm_content}
                    
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            else:
                return {"type": "error", "content": f"API error after {max_retries} attempts: {e}"}
    
    return {"type": "error", "content": "Maximum retry attempts exceeded"}

# UI Helper functions
def display_message(message, is_user=True):
    """Display a chat message."""
    if is_user:
        with st.chat_message("user"):
            if message.get("image"):
                st.image(message["image"], width=300)
            if message.get("audio_name"):
                st.write(f"🎵 Audio file: {message['audio_name']}")
            st.write(message["text"])
    else:
        with st.chat_message("assistant"):
            st.write(message["text"])
            if message.get("tool_results"):
                with st.expander("Tool Execution Details"):
                    for result in message["tool_results"]:
                        if "error" in result:
                            st.error(f"❌ Tool '{result['tool']}' failed: {result['error']}")
                        else:
                            st.success(f"✅ Tool '{result['tool']}' executed successfully")
                            st.json(result["result"])

def main():
    st.title("🤖 LLM Tool Demo with Gemini")
    
    if not MODULES_AVAILABLE:
        st.stop()
    
    initialize_session_state()
    
    # Sidebar for API configuration
    with st.sidebar:
        st.header("🔧 Configuration")
        
        # API Key input
        api_key = st.text_input("Gemini API Key", type="password", 
                               help="Enter your Google Gemini API key")
        
        if api_key and not st.session_state.api_initialized:
            with st.spinner("Initializing API and managers..."):
                # Setup Gemini API
                client = setup_gemini_api(api_key)
                if client:
                    st.session_state.client = client
                    
                    # Initialize managers
                    tool_manager, prompt_manager, system_prompt = initialize_managers()
                    if tool_manager and prompt_manager and system_prompt:
                        st.session_state.tool_manager = tool_manager
                        st.session_state.prompt_manager = prompt_manager
                        st.session_state.system_prompt = system_prompt
                        st.session_state.api_initialized = True
                        st.success("✅ API and managers initialized!")
                        st.rerun()
        
        if st.session_state.api_initialized:
            st.success("✅ System Ready")
            
            # Tool manager info
            if st.session_state.tool_manager:
                available_tools = st.session_state.tool_manager.get_available_tools()
                st.write(f"**Available Tools:** {', '.join(available_tools)}")
        else:
            st.warning("⚠️ Please enter your API key to continue")
    
    if not st.session_state.api_initialized:
        st.warning("Please configure your API key in the sidebar to get started.")
        return
    
    # Main interface tabs
    tab1, tab2 = st.tabs(["💬 Chat Mode", "⚡ One-Shot Prompts"])
    
    with tab1:
        st.header("Chat Mode")
        st.write("Have a conversation with the AI. Tool calls will be executed automatically.")
        
        # Display chat history
        for message in st.session_state.chat_messages:
            display_message(message, is_user=message["role"] == "user")
        
        # Chat input area
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            chat_prompt = st.text_input("Type your message:", key="chat_input")
        
        with col2:
            chat_image = st.file_uploader(
                "Upload image", 
                type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
                key="chat_image"
            )
        
        with col3:
            chat_audio = st.file_uploader(
                "Upload audio", 
                type=['wav', 'mp3', 'm4a', 'flac', 'ogg'], 
                key="chat_audio"
            )
        
        # Send button
        if st.button("Send", key="chat_send"):
            if chat_prompt:
                # Process uploaded files
                image_data = None
                audio_data = None
                
                if chat_image and validate_image_file(chat_image):
                    image_bytes = chat_image.read()
                    image_data = {
                        "base64": encode_image_to_base64(image_bytes),
                        "mime_type": get_image_mime_type(chat_image.name)
                    }
                
                if chat_audio and validate_audio_file(chat_audio):
                    audio_bytes = chat_audio.read()
                    audio_data = {
                        "base64": encode_audio_to_base64(audio_bytes),
                        "mime_type": get_audio_mime_type(chat_audio.name)
                    }
                
                # Add user message to chat history
                user_message = {
                    "role": "user",
                    "text": chat_prompt,
                    "image": Image.open(io.BytesIO(chat_image.read())) if chat_image else None,
                    "audio_name": chat_audio.name if chat_audio else None,
                    "timestamp": datetime.now()
                }
                st.session_state.chat_messages.append(user_message)
                
                # Get AI response
                with st.spinner("Processing..."):
                    result = call_gemini_llm(
                        chat_prompt,
                        [{"role": msg["role"], "content": msg["text"]} for msg in st.session_state.chat_messages],
                        st.session_state.client,
                        st.session_state.system_prompt,
                        st.session_state.tool_manager,
                        is_chat_mode=True,
                        image_data=image_data,
                        audio_data=audio_data
                    )
                
                # Add AI response to chat history
                ai_message = {
                    "role": "assistant",
                    "text": result["content"],
                    "tool_results": result.get("tool_results"),
                    "timestamp": datetime.now()
                }
                st.session_state.chat_messages.append(ai_message)
                
                st.rerun()
        
        # Clear chat button
        if st.button("Clear Chat History", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()
    
    with tab2:
        st.header("One-Shot Prompts")
        st.write("Send individual prompts with automatic tool execution.")
        
        # One-shot input area
        oneshot_prompt = st.text_area(
            "Enter your prompt:", 
            height=100,
            key="oneshot_input"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            oneshot_image = st.file_uploader(
                "Upload image (optional)", 
                type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
                key="oneshot_image"
            )
            
            if oneshot_image:
                st.image(oneshot_image, caption="Uploaded Image", width=300)
        
        with col2:
            oneshot_audio = st.file_uploader(
                "Upload audio (optional)", 
                type=['wav', 'mp3', 'm4a', 'flac', 'ogg'], 
                key="oneshot_audio"
            )
            
            if oneshot_audio:
                st.audio(oneshot_audio, format=f"audio/{oneshot_audio.type.split('/')[-1]}")
        
        # Submit button
        if st.button("Submit", key="oneshot_submit"):
            if oneshot_prompt:
                # Process uploaded files
                image_data = None
                audio_data = None
                
                if oneshot_image and validate_image_file(oneshot_image):
                    image_bytes = oneshot_image.read()
                    image_data = {
                        "base64": encode_image_to_base64(image_bytes),
                        "mime_type": get_image_mime_type(oneshot_image.name)
                    }
                
                if oneshot_audio and validate_audio_file(oneshot_audio):
                    audio_bytes = oneshot_audio.read()
                    audio_data = {
                        "base64": encode_audio_to_base64(audio_bytes),
                        "mime_type": get_audio_mime_type(oneshot_audio.name)
                    }
                
                # Show user prompt
                st.subheader("Your Prompt:")
                st.write(oneshot_prompt)
                
                if oneshot_image:
                    st.image(oneshot_image, width=300)
                if oneshot_audio:
                    st.write(f"🎵 Audio file: {oneshot_audio.name}")
                
                # Get AI response
                with st.spinner("Processing..."):
                    result = call_gemini_llm(
                        oneshot_prompt,
                        [],  # Empty chat history for one-shot
                        st.session_state.client,
                        st.session_state.system_prompt,
                        st.session_state.tool_manager,
                        is_chat_mode=False,
                        image_data=image_data,
                        audio_data=audio_data
                    )
                
                # Display response
                st.subheader("AI Response:")
                if result["type"] == "error":
                    st.error(result["content"])
                else:
                    st.write(result["content"])
                    
                    if result.get("tool_results"):
                        st.subheader("Tool Execution Results:")
                        for tool_result in result["tool_results"]:
                            if "error" in tool_result:
                                st.error(f"❌ Tool '{tool_result['tool']}' failed: {tool_result['error']}")
                            else:
                                st.success(f"✅ Tool '{tool_result['tool']}' executed successfully")
                                with st.expander(f"View {tool_result['tool']} results"):
                                    st.json(tool_result["result"])
            else:
                st.warning("Please enter a prompt before submitting.")

if __name__ == "__main__":
    main()