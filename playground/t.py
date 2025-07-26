#!/usr/bin/env python3
"""
Ollama Image Description Tool
Takes a local image file path and outputs a detailed description using gemma3n:latest
"""

import ollama
import argparse
import base64
import os
import sys
import requests
from urllib.parse import urlparse

def encode_image_from_url(image_url: str) -> str:
    """Download and encode an image from URL as base64"""
    try:
        print(f"Downloading image from URL...")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_data = response.content
        return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"Error downloading image from URL: {e}")
        return None

def encode_image_file(image_path: str) -> str:
    """Read and encode a local image file as base64"""
    try:
        if not os.path.exists(image_path):
            print(f"Error: Image file '{image_path}' does not exist")
            return None
            
        print(f"Reading local image file...")
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"Error reading image file: {e}")
        return None

def is_url(string: str) -> bool:
    """Check if a string is a valid URL"""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_image_description(image_source: str, model_name: str = "gemma3n:latest"):
    """Get detailed description of an image using ollama"""
    print(f"Analyzing image: {image_source}")
    print(f"Using model: {model_name}")
    print("-" * 50)
    
    try:
        client = ollama.Client()
        
        # Determine if input is URL or local file path
        if is_url(image_source):
            image_base64 = encode_image_from_url(image_source)
        else:
            image_base64 = encode_image_file(image_source)
        
        if not image_base64:
            return
        
        # Create message for detailed image description
        question = "Please provide a detailed description of this image. Include information about objects, people, animals, colors, composition, setting, and any other notable details you can observe."
        
        messages = [{
            "role": "user",
            "content": question,
            "images": [image_base64]
        }]
        
        print("Processing image...")
        response = client.chat(
            model=model_name,
            messages=messages,
            stream=False
        )
        
        if response and 'message' in response:
            description = response['message'].get('content', '')
            print("Image Description:")
            print("=" * 50)
            print(description)
        else:
            print("Error: No response content received")
            
    except ollama.ResponseError as e:
        print(f"Ollama Error: {e}")
        print("Note: Make sure the model supports image analysis and is available")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate detailed descriptions of images using Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python image_describe.py /path/to/image.jpg
  python image_describe.py photo.png
  python image_describe.py https://example.com/image.jpg
  python image_describe.py --model llama3.2-vision:latest https://site.com/photo.png
        """
    )
    
    parser.add_argument(
        'image_source',
        help='Path to local image file or URL to image'
    )
    
    parser.add_argument(
        '--model',
        default='gemma3n:latest',
        help='Ollama model to use for image analysis (default: gemma3n:latest)'
    )
    
    args = parser.parse_args()
    
    # If it's a local file, validate image file extension
    if not is_url(args.image_source):
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        file_ext = os.path.splitext(args.image_source)[1].lower()
        
        if file_ext not in valid_extensions:
            print(f"Warning: '{file_ext}' may not be a supported image format")
            print(f"Supported formats: {', '.join(valid_extensions)}")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
    
    get_image_description(args.image_source, args.model)

if __name__ == "__main__":
    main()