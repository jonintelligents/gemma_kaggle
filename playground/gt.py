#!/usr/bin/env python3
"""
Google Gemini Image Description Tool
Takes a local image file path or URL and outputs a detailed description using Gemini models
"""

import argparse
import os
import sys
import requests
from urllib.parse import urlparse
from google import genai
from google.genai import types

def is_url(string: str) -> bool:
    """Check if a string is a valid URL"""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_image_description(image_source: str, model_name: str = "gemini-2.5-flash"):
    """Get detailed description of an image using Google Gemini API"""
    print(f"Analyzing image: {image_source}")
    print(f"Using model: {model_name}")
    print("-" * 50)
    
    try:
        # The client gets the API key from the environment variable `GEMINI_API_KEY`
        client = genai.Client()
        
        # Get image bytes
        if is_url(image_source):
            print(f"Downloading image from URL...")
            response = requests.get(image_source, timeout=30)
            response.raise_for_status()
            image_bytes = response.content
        else:
            if not os.path.exists(image_source):
                print(f"Error: Image file '{image_source}' does not exist")
                return
            print(f"Reading local image file...")
            with open(image_source, 'rb') as f:
                image_bytes = f.read()
        
        # Create message for detailed image description
        question = "Please provide a detailed description of this image. Include information about objects, people, animals, colors, composition, setting, and any other notable details you can observe."
        
        print("Processing image...")
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/jpeg'
                ),
                question
            ]
        )
        
        if response and hasattr(response, 'text'):
            description = response.text
            print("Image Description:")
            print("=" * 50)
            print(description)
        else:
            print("Error: No response content received")
            
    except Exception as e:
        print(f"Error: {e}")
        print("Note: Make sure GEMINI_API_KEY environment variable is set and the model supports image analysis")

def main():
    parser = argparse.ArgumentParser(
        description="Generate detailed descriptions of images using Google Gemini API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python image_describe.py /path/to/image.jpg
  python image_describe.py photo.png
  python image_describe.py https://example.com/image.jpg
  python image_describe.py --model gemini-1.5-flash https://site.com/photo.png

Note: Set GEMINI_API_KEY environment variable before running:
  export GEMINI_API_KEY="your-api-key-here"
        """
    )
    
    parser.add_argument(
        'image_source',
        help='Path to local image file or URL to image'
    )
    
    parser.add_argument(
        '--model',
        default='gemma-3n-e4b-it',
        help='Gemini model to use for image analysis (default: gemini-2.5-flash)'
    )
    
    args = parser.parse_args()
    
    # Check if API key is set
    if not os.getenv('GEMINI_API_KEY'):
        print("Error: GEMINI_API_KEY environment variable is not set")
        print("Please set it with: export GEMINI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
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