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
import re

from GemmaChat import GemmaChat
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

# Prompt helper functions
def extract_variables_from_prompt(prompt_text):
    """Extract variable placeholders from prompt text."""
    if not prompt_text:
        return []
    
    # Find all {variable} patterns
    variables = re.findall(r'\{([^}]+)\}', prompt_text)
    return list(set(variables))  # Remove duplicates

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
    
    # Main interface tabs (added Prompts tab)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["💬 Chat Mode", "⚡ One-Shot Prompts", "👥 People Database", "🎯 Custom Chat", "📝 Prompts"])
    
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
    
    with tab3:
        st.header("People Database")
        st.write("View all people stored in the knowledge graph with their facts and properties.")
        
        if st.session_state.api_initialized:
            # Database statistics at the top
            try:
                stats = st.session_state.tool_manager.get_graph_statistics()
                st.info(stats)
            except Exception as e:
                st.error(f"Error loading statistics: {e}")
            
            # Refresh button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔄 Refresh", key="refresh_people"):
                    st.rerun()
            
            # Get all people data
            with st.spinner("Loading people data..."):
                try:
                    people_data_result = st.session_state.tool_manager.get_all_people(include_relationships=True)
                    
                    # Extract JSON from the result string
                    if "People data: " in people_data_result:
                        json_start = people_data_result.find('People data: ') + len('People data: ')
                        json_data = people_data_result[json_start:]
                        people_data = json.loads(json_data)
                        
                        if people_data:
                            st.success(f"Found {len(people_data)} people in the database")
                            
                            # Display each person in an expander
                            for idx, person in enumerate(people_data):
                                person_name = person.get('name', 'Unknown')
                                person_id = person.get('id', 'N/A')
                                # Create unique key using index to avoid duplicates
                                unique_key = f"{person_id}_{idx}" if person_id != 'N/A' else f"person_{idx}"
                                
                                with st.expander(f"👤 {person_name}", expanded=False):
                                    # Person basic info
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**ID:** {person_id}")
                                    with col2:
                                        st.write(f"**Name:** {person_name}")
                                    
                                    # Properties section
                                    properties = person.get('properties', {})
                                    if properties:
                                        st.subheader("📋 Properties")
                                        for key, value in properties.items():
                                            if key != 'name':  # Skip name as it's already displayed
                                                st.write(f"**{key.title()}:** {value}")
                                    
                                    # Facts section
                                    facts = person.get('facts', [])
                                    if facts:
                                        st.subheader(f"📝 Facts ({len(facts)})")
                                        for i, fact in enumerate(facts, 1):
                                            fact_text = fact.get('text', 'No text')
                                            fact_type = fact.get('type', 'general')
                                            fact_id = fact.get('id', 'N/A')
                                            
                                            # Color code by fact type
                                            type_colors = {
                                                'work': '🔵',
                                                'hobby': '🟢', 
                                                'relationship': '❤️',
                                                'volunteer': '🟡',
                                                'general': '⚪'
                                            }
                                            
                                            type_icon = type_colors.get(fact_type, '⚪')
                                            
                                            st.write(f"{type_icon} **{i}.** {fact_text}")
                                            st.caption(f"Type: {fact_type} | ID: {fact_id}")
                                            st.divider()
                                    
                                    # Relationships section
                                    relationships = person.get('relationships', {})
                                    if relationships:
                                        st.subheader("🔗 Relationships")
                                        
                                        # Connected people
                                        connected_people = relationships.get('connected_people', [])
                                        if connected_people:
                                            st.write("**👥 Connected People:**")
                                            for connection in connected_people:
                                                st.write(f"• {connection}")
                                        
                                        # Connected entities
                                        connected_entities = relationships.get('connected_entities', [])
                                        if connected_entities:
                                            st.write("**🏢 Connected Entities:**")
                                            for entity in connected_entities:
                                                entity_name = entity.get('name', 'Unknown')
                                                entity_type = entity.get('type', 'unknown')
                                                st.write(f"• {entity_name} ({entity_type})")
                                    
                                    # Delete button at bottom
                                    st.markdown("---")
                                    if st.button(f"🗑️ DELETE PERSON", key=f"delete_{unique_key}", type="primary", 
                                                use_container_width=True):
                                        st.session_state[f"confirm_delete_{unique_key}"] = True
                                    
                                    # Delete confirmation
                                    if st.session_state.get(f"confirm_delete_{unique_key}", False):
                                        st.error(f"⚠️ Are you sure you want to delete {person_name}?")
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button(f"✅ Yes, Delete", key=f"confirm_yes_{unique_key}"):
                                                # Use person_id for deletion, fallback to name if needed
                                                if person_id != 'N/A':
                                                    result = st.session_state.tool_manager.delete_person(person_id=person_id)
                                                else:
                                                    result = st.session_state.tool_manager.delete_person(name=person_name)
                                                st.success(f"Person deleted: {result}")
                                                st.session_state[f"confirm_delete_{unique_key}"] = False
                                                st.rerun()
                                        with col2:
                                            if st.button(f"❌ Cancel", key=f"confirm_no_{unique_key}"):
                                                st.session_state[f"confirm_delete_{unique_key}"] = False
                                                st.rerun()
                        else:
                            st.info("No people found in the database")
                            st.write("Use the Chat Mode or One-Shot Prompts to add people to the database.")
                    
                    else:
                        st.error("Unable to parse people data")
                        st.code(people_data_result)
                        
                except json.JSONDecodeError as e:
                    st.error(f"Error parsing people data: {e}")
                    st.code(people_data_result)
                except Exception as e:
                    st.error(f"Error loading people data: {e}")
        
        else:
            st.warning("Please configure your API key first to view the people database.")
    
    with tab4:
        st.header("Custom Chat Analysis")
        st.write("Analyze your conversation with specific people from your database to get suggestions on how to communicate more effectively.")
        
        if st.session_state.api_initialized:
            # Get list of people for dropdown
            with st.spinner("Loading people list..."):
                try:
                    people_data_result = st.session_state.tool_manager.get_all_people(include_relationships=True)
                    
                    if "People data: " in people_data_result:
                        json_start = people_data_result.find('People data: ') + len('People data: ')
                        json_data = people_data_result[json_start:]
                        people_data = json.loads(json_data)
                        
                        if people_data:
                            # Create dropdown options
                            people_options = ["Select a person..."] + [person.get('name', 'Unknown') for person in people_data]
                            
                            # Person selection dropdown
                            selected_person = st.selectbox(
                                "👤 Select person to analyze conversation with:",
                                options=people_options,
                                key="custom_chat_person"
                            )
                            
                            if selected_person != "Select a person...":
                                # Find the selected person's data
                                person_data = next((p for p in people_data if p.get('name') == selected_person), None)
                                
                                if person_data:
                                    # Show person info in an expander
                                    with st.expander(f"ℹ️ About {selected_person}", expanded=False):
                                        # Display person's facts for context
                                        facts = person_data.get('facts', [])
                                        if facts:
                                            st.write("**Known facts about this person:**")
                                            for i, fact in enumerate(facts, 1):
                                                fact_text = fact.get('text', 'No text')
                                                fact_type = fact.get('type', 'general')
                                                
                                                # Color code by fact type
                                                type_colors = {
                                                    'work': '🔵',
                                                    'hobby': '🟢', 
                                                    'relationship': '❤️',
                                                    'volunteer': '🟡',
                                                    'general': '⚪'
                                                }
                                                type_icon = type_colors.get(fact_type, '⚪')
                                                
                                                st.write(f"{type_icon} {fact_text}")
                                        else:
                                            st.write("No facts available for this person.")
                                    
                                    st.markdown("---")
                                    
                                    # Input fields for conversation analysis
                                    st.subheader("📝 Conversation Analysis")
                                    
                                    # Previous conversation context
                                    previous_conversation = st.text_area(
                                        "📜 Previous conversation context:",
                                        height=150,
                                        placeholder="Paste the previous conversation or context here...",
                                        help="Include any relevant conversation history to provide context for the analysis.",
                                        key="previous_conversation"
                                    )
                                    
                                    # Your next message
                                    your_message = st.text_area(
                                        "💬 Your next message:",
                                        height=100,
                                        placeholder="Type the message you want to send...",
                                        help="Enter the message you're planning to send and get suggestions for improvement.",
                                        key="your_message"
                                    )
                                    
                                    # Analyze button
                                    if st.button("🔍 Analyze", key="analyze_conversation", type="primary", use_container_width=True):
                                        if your_message.strip():
                                            # Create analysis prompt
                                            person_facts = "\n".join([f"- {fact.get('text', '')}" for fact in facts])

                                            if not person_facts :
                                                person_facts =  "No specific information available."

                                            if not previous_conversation.strip() :
                                                previous_conversation = "No previous context provided."
                                           
                                            analysis_prompt = st.session_state.prompt_manager.get_prompt('message_analysis', {
                                                'selected_person' : selected_person,
                                                'person_facts' : person_facts,
                                                'previous_conversation' : previous_conversation,
                                                'message' : your_message
                                            })
                                            
                                            # Call the Gemma model for analysis
                                            with st.spinner(f"Analyzing your message for {selected_person}..."):
                                                try:
                                                    # Use the text model directly for this analysis
                                                    result = st.session_state.gemma_chat.call_simple(
                                                        analysis_prompt,
                                                        system_prompt="You are a helpful communication expert who provides thoughtful, constructive feedback on interpersonal communications."
                                                    )
                                                    
                                                    if result["success"]:
                                                        st.subheader("🎯 Analysis Results")
                                                        
                                                        # Display the analysis in a nice format
                                                        st.json(result['response'])
                                                        
                                                    else:
                                                        st.error(f"Analysis failed: {result['error']}")
                                                        
                                                except Exception as e:
                                                    st.error(f"Error during analysis: {str(e)}")
                                        else:
                                            st.warning("Please enter a message to analyze.")
                                
                                else:
                                    st.error("Could not find data for the selected person.")
                            
                            else:
                                st.info("👆 Please select a person from the dropdown to begin conversation analysis.")
                        
                        else:
                            st.warning("No people found in the database.")
                            st.write("Add some people using the Chat Mode or One-Shot Prompts first.")
                    
                    else:
                        st.error("Unable to load people data.")
                        
                except json.JSONDecodeError as e:
                    st.error(f"Error parsing people data: {e}")
                except Exception as e:
                    st.error(f"Error loading people data: {e}")
        
        else:
            st.warning("Please configure your API key first to use Custom Chat Analysis.")
    
    with tab5:
        st.header("Prompt Templates")
        st.write("View and explore all available prompt templates used by the system.")
        
        if st.session_state.api_initialized:
            # Refresh button for prompts
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔄 Refresh Prompts", key="refresh_prompts"):
                    # Reload prompts from disk
                    if hasattr(st.session_state.prompt_manager, 'reload'):
                        st.session_state.prompt_manager.reload()
                    st.rerun()
            
            # Load and display prompt templates
            with st.spinner("Loading prompt templates..."):
                try:
                    prompt_manager = st.session_state.prompt_manager
                    
                    if prompt_manager and hasattr(prompt_manager, 'list_prompts'):
                        # Get list of all available prompts
                        prompt_names = prompt_manager.list_prompts()
                        
                        if prompt_names:
                            st.success(f"Found {len(prompt_names)} prompt templates")
                            
                            # Display each prompt template in an expander
                            for prompt_name in prompt_names:
                                try:
                                    # Get prompt variables
                                    variables = prompt_manager.get_prompt_variables(prompt_name)
                                    
                                    # Create title with variables
                                    if variables:
                                        variables_str = ", ".join([f"{{{var}}}" for var in variables])
                                        title = f"📝 {prompt_name} - Variables: {variables_str}"
                                    else:
                                        title = f"📝 {prompt_name} - No variables"
                                    
                                    with st.expander(title, expanded=False):
                                        # Display prompt metadata
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.write(f"**Prompt Name:** `{prompt_name}`")
                                        with col2:
                                            st.write(f"**Variables Found:** {len(variables)}")
                                        
                                        if variables:
                                            st.write("**Required Variables:**")
                                            for var in variables:
                                                st.write(f"• `{{{var}}}`")
                                            st.markdown("---")
                                        
                                        # Get the raw prompt content
                                        prompt_content = prompt_manager.get_raw_prompt(prompt_name)
                                        
                                        # Display the prompt content
                                        st.subheader("Prompt Content:")
                                        st.code(prompt_content, language="text")
                                        
                                        # Show character and word count
                                        char_count = len(prompt_content)
                                        word_count = len(prompt_content.split())
                                        st.caption(f"📊 Characters: {char_count:,} | Words: {word_count:,}")
                                 
                                except Exception as prompt_e:
                                    st.error(f"Error loading prompt '{prompt_name}': {prompt_e}")
                                    with st.expander(f"⚠️ Error Details for {prompt_name}", expanded=False):
                                        st.code(str(prompt_e))
                        
                        else:
                            st.warning("No prompt templates found in the prompts directory.")
                            st.info("Make sure your prompts directory contains .md files with prompt templates.")
                    
                    else:
                        st.error("PromptManager is not properly initialized or doesn't have the expected methods.")
                        st.info("Expected PromptManager methods: `list_prompts()`, `get_prompt_variables()`, `get_raw_prompt()`, `get_prompt()`")
                        
                        # Show available methods for debugging
                        if prompt_manager:
                            st.subheader("Available PromptManager methods:")
                            methods = [method for method in dir(prompt_manager) 
                                    if not method.startswith('_') and callable(getattr(prompt_manager, method))]
                            for method in sorted(methods):
                                st.write(f"• `{method}()`")
                            
                            # Show PromptManager info
                            if hasattr(prompt_manager, '__repr__'):
                                st.write(f"**PromptManager Info:** {repr(prompt_manager)}")
                
                except Exception as e:
                    st.error(f"Error loading prompt templates: {e}")
                    st.write("**Debug Information:**")
                    st.write(f"Error type: {type(e).__name__}")
                    st.write(f"Error details: {str(e)}")
                    
                    # Show traceback for debugging
                    if st.checkbox("Show detailed error traceback", key="show_traceback"):
                        import traceback
                        st.code(traceback.format_exc())
                    
                    # Try to get some basic info about PromptManager
                    try:
                        if hasattr(st.session_state, 'prompt_manager') and st.session_state.prompt_manager:
                            st.write("**PromptManager Object Info:**")
                            st.write(f"Type: {type(st.session_state.prompt_manager)}")
                            st.write(f"String representation: {st.session_state.prompt_manager}")
                            
                            # Check if prompts directory exists
                            if hasattr(st.session_state.prompt_manager, 'prompts_dir'):
                                prompts_dir = st.session_state.prompt_manager.prompts_dir
                                st.write(f"Prompts directory: {prompts_dir}")
                                st.write(f"Directory exists: {os.path.exists(prompts_dir)}")
                                if os.path.exists(prompts_dir):
                                    try:
                                        files = os.listdir(prompts_dir)
                                        md_files = [f for f in files if f.endswith('.md')]
                                        st.write(f"Markdown files found: {md_files}")
                                    except Exception as dir_e:
                                        st.write(f"Error reading directory: {dir_e}")
                            
                    except Exception as debug_e:
                        st.write(f"Could not get PromptManager debug info: {debug_e}")
        
        else:
            st.warning("Please configure your API key first to view prompt templates.")
            
            # Show some example of what the prompts tab will look like
            st.subheader("Preview: What you'll see when configured")
            st.info("Once you configure your API key, this tab will show all available prompt templates with their variables and content.")
            
            # Example prompt display
            with st.expander("📝 Example: system - Variables: {tool_function_descriptions}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**Prompt Name:** `system`")
                with col2:
                    st.write("**Variables Found:** 1")
                with col3:
                    st.button("🔍 Debug Info", disabled=True)
                
                st.write("**Required Variables:**")
                st.write("• `{tool_function_descriptions}`")
                st.markdown("---")
                st.subheader("Prompt Content:")
                example_content = """You are an AI assistant that helps manage information about people.
    You have access to tools for storing and retrieving person information.
    Available tools: {tool_function_descriptions}

    Always be helpful and accurate when working with person data."""
                st.code(example_content, language="text")
                st.caption("📊 Characters: 234 | Words: 42")
                
                st.subheader("Test Template with Variables:")
                st.text_input("Value for `{tool_function_descriptions}`:", disabled=True, placeholder="Enter value for tool_function_descriptions")
                st.button("Test Template", disabled=True)
                
                st.subheader("Copy Raw Prompt:")
                st.text_area("Select all and copy:", value=example_content, height=100, disabled=True)

if __name__ == "__main__":
    main()