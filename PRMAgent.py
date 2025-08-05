import json
import os
import argparse
from google import genai
from ToolManager import ExamplePersonToolManager
from GraphPersonManager import GraphPersonManager
from PromptManager import PromptManager
import logging
import base64
from pathlib import Path
import pyaudio
import wave
import threading
import tempfile
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

prompt_manager = PromptManager()

# --- Audio recording functions ---
class AudioRecorder:
    def __init__(self):
        self.chunk = 1024
        self.sample_format = pyaudio.paInt16
        self.channels = 1
        self.fs = 16000  # 16kHz sample rate (good for speech)
        self.recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        
    def start_recording(self):
        """Start recording audio in a separate thread."""
        self.recording = True
        self.frames = []
        
        stream = self.audio.open(format=self.sample_format,
                                channels=self.channels,
                                rate=self.fs,
                                frames_per_buffer=self.chunk,
                                input=True)
        
        print("🎤 Recording started... Press ENTER to stop recording.")
        
        while self.recording:
            data = stream.read(self.chunk)
            self.frames.append(data)
            
        stream.stop_stream()
        stream.close()
        print("🛑 Recording stopped.")
    
    def stop_recording(self):
        """Stop the recording."""
        self.recording = False
    
    def save_recording(self, filename):
        """Save the recorded audio to a WAV file."""
        if not self.frames:
            raise ValueError("No audio data recorded")
            
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        
    def cleanup(self):
        """Clean up PyAudio resources."""
        self.audio.terminate()

def record_audio_until_enter():
    """Record audio until user presses enter, return path to temporary audio file."""
    recorder = AudioRecorder()
    
    # Start recording in a separate thread
    recording_thread = threading.Thread(target=recorder.start_recording)
    recording_thread.start()
    
    # Wait for user to press enter
    input()
    
    # Stop recording
    recorder.stop_recording()
    recording_thread.join()
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_file.close()
    
    try:
        recorder.save_recording(temp_file.name)
        print(f"✅ Audio saved to: {temp_file.name}")
        return temp_file.name
    except ValueError as e:
        print(f"❌ Error saving audio: {e}")
        return None
    finally:
        recorder.cleanup()

# --- Audio processing functions ---
def validate_audio_file(audio_path):
    """Validate that the audio file exists and has a supported format."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    supported_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}
    file_extension = Path(audio_path).suffix.lower()
    
    if file_extension not in supported_extensions:
        raise ValueError(f"Unsupported audio format: {file_extension}. Supported formats: {', '.join(supported_extensions)}")
    
    return True

def encode_audio_to_base64(audio_path):
    """Encode audio file to base64 string."""
    try:
        with open(audio_path, "rb") as audio_file:
            encoded_string = base64.b64encode(audio_file.read()).decode('utf-8')
        return encoded_string
    except Exception as e:
        raise Exception(f"Failed to encode audio: {e}")

def get_audio_mime_type(audio_path):
    """Get MIME type for the audio file."""
    extension = Path(audio_path).suffix.lower()
    mime_types = {
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.flac': 'audio/flac',
        '.ogg': 'audio/ogg'
    }
    return mime_types.get(extension, 'audio/wav')

# --- Gemini API Setup ---
def setup_gemini_api():
    logging.info("Setting up Gemini API.")
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Please set the GEMINI_API_KEY environment variable")
    client = genai.Client()
    return client

# --- Image processing functions ---
def validate_image_file(image_path):
    """Validate that the image file exists and has a supported format."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    supported_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    file_extension = Path(image_path).suffix.lower()
    
    if file_extension not in supported_extensions:
        raise ValueError(f"Unsupported image format: {file_extension}. Supported formats: {', '.join(supported_extensions)}")
    
    return True

def encode_image_to_base64(image_path):
    """Encode image file to base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    except Exception as e:
        raise Exception(f"Failed to encode image: {e}")

def get_image_mime_type(image_path):
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

# --- Call Gemini and parse response ---
def call_gemini_llm(user_query: str, chat_history: list, client, system_prompt: str = None, tool_manager=None, is_chat_mode=True, max_retries=3, image_path=None, audio_path=None):
    logging.info(f"Calling Gemini LLM with query: '{user_query}'")
    
    if image_path:
        logging.info(f"Including image: {image_path}")
    if audio_path:
        logging.info(f"Including audio: {audio_path}")

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

            # Prepare the content for the API call
            parts = [{"text": full_context}]
            
            if image_path:
                # Validate and encode the image
                validate_image_file(image_path)
                image_base64 = encode_image_to_base64(image_path)
                mime_type = get_image_mime_type(image_path)
                
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                })
            
            if audio_path:
                # Validate and encode the audio
                validate_audio_file(audio_path)
                audio_base64 = encode_audio_to_base64(audio_path)
                mime_type = get_audio_mime_type(audio_path)
                
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_base64
                    }
                })

            # Create content structure
            if image_path or audio_path:
                contents = [
                    {
                        "role": "user",
                        "parts": parts
                    }
                ]
            else:
                # Text-only content
                contents = full_context

            # Make the API call
            logging.info(f"Making Gemini API call - attempt {attempt + 1}/{max_retries}")
            response = client.models.generate_content(
                #model="gemma-3-4b-it",
                model="gemma-3n-e4b-it",
                contents=contents
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
                                tool_output['result'] = output

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

def run_audio_chat_mode(tool_manager, client, system_prompt):
    """Run the interactive audio chat mode."""
    chat_history = []

    print("""
🎙️ Welcome to the Audio LLM Tool Demo!

In audio mode:
- Press ENTER to start recording
- Speak your message
- Press ENTER again to stop recording and send
- Type 'exit' to quit
""")

    while True:
        try:
            user_input = input("Press ENTER to start recording (or type 'exit'): ").strip()
            
            if user_input.lower() == "exit":
                print("👋 Goodbye!")
                break
            
            if user_input:
                # If they typed something instead of just pressing enter, treat it as text
                chat_history.append({"role": "user", "content": user_input})
                result = call_gemini_llm(user_input, chat_history, client, system_prompt, tool_manager, is_chat_mode=True, max_retries=3)
            else:
                # Record audio
                audio_file = record_audio_until_enter()
                if audio_file:
                    try:
                        # Use audio file as input (no text query needed for audio-only)
                        chat_history.append({"role": "user", "content": "[Audio message]"})
                        result = call_gemini_llm("Please process this audio input", chat_history, client, system_prompt, tool_manager, is_chat_mode=True, max_retries=3, audio_path=audio_file)
                    finally:
                        # Clean up temporary audio file
                        try:
                            os.unlink(audio_file)
                        except:
                            pass
                else:
                    print("❌ No audio recorded. Try again.")
                    continue

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

def run_single_prompt(prompt, tool_manager, client, system_prompt, retry_count=3, image_path=None, audio_path=None):
    """Run a single prompt and execute any tool calls automatically."""
    chat_history = []
    
    media_info = []
    if image_path:
        media_info.append(f"Image: {image_path}")
    if audio_path:
        media_info.append(f"Audio: {audio_path}")
    
    if media_info:
        print(f"🚀 Processing prompt with media: {prompt} ({', '.join(media_info)})")
    else:
        print(f"🚀 Processing prompt: {prompt}")
    
    # Add to chat history
    chat_history.append({"role": "user", "content": prompt})
    
    # Call LLM with retry logic
    result = call_gemini_llm(prompt, chat_history, client, system_prompt, tool_manager, is_chat_mode=False, max_retries=retry_count, image_path=image_path, audio_path=audio_path)
    
    if result["type"] == "tool_call_complete":
        print("\n✅ All tool calls completed successfully.")
    elif result["type"] == "text":
        print("📄 No tool calls were needed.")
        return result["content"]
    else:
        print("⚠️ Unexpected response type.")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="LLM Tool Demo with Image and Audio Support")
    parser.add_argument(
        "--chat", 
        action="store_true", 
        help="Run in interactive chat mode"
    )
    parser.add_argument(
        "--audio-chat", 
        action="store_true", 
        help="Run in interactive audio chat mode"
    )
    parser.add_argument(
        "--image", 
        type=str,
        help="Path to image file (PNG, JPEG, GIF, WebP) to process with the prompt"
    )
    parser.add_argument(
        "--audio", 
        type=str,
        help="Path to audio file (WAV, MP3, M4A, FLAC, OGG) to process with the prompt"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Single prompt to process (required if not using --chat or --audio-chat)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.chat and not args.audio_chat and not args.prompt:
        parser.error("Either --chat, --audio-chat flag, or a prompt argument is required")
    
    if sum([args.chat, args.audio_chat, bool(args.prompt)]) > 1:
        parser.error("Cannot use multiple modes simultaneously")
    
    if (args.chat or args.audio_chat) and (args.image or args.audio):
        parser.error("Media input is not supported in chat modes")
    
    if (args.image or args.audio) and not args.prompt:
        parser.error("Media input requires a prompt to be provided")
    
    return args

# --- Main function ---
def main():
    # Parse command line arguments
    args = parse_arguments()
    
    print("🚀 Starting LLM + Tooling Demo...")
    
    # Validate media files if provided
    if args.image:
        try:
            validate_image_file(args.image)
            print(f"✅ Image file validated: {args.image}")
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ Image validation error: {e}")
            return
    
    if args.audio:
        try:
            validate_audio_file(args.audio)
            print(f"✅ Audio file validated: {args.audio}")
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ Audio validation error: {e}")
            return
    
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
        elif args.audio_chat:
            run_audio_chat_mode(tool_manager, client, system_prompt)
        else:
            run_single_prompt(args.prompt, tool_manager, client, system_prompt, image_path=args.image, audio_path=args.audio)
    finally:
        # Clean up
        try:
            tool_manager.close()
            print("✅ Tool manager connection closed.")
        except Exception as e:
            logging.error(f"Error closing tool manager connection: {e}")

if __name__ == "__main__":
    main()