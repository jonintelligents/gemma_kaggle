#!/usr/bin/env python3
"""
Unsloth Gemma 3n Image Description Tool
Takes a local image file path or URL and outputs a detailed description using Gemma 3n with Unsloth
Based on the Kaggle notebook: https://www.kaggle.com/code/danielhanchen/gemma-3n-4b-multimodal-finetuning-inference
"""

import argparse
import base64
import os
import sys
import requests
from urllib.parse import urlparse
import torch
from PIL import Image
from io import BytesIO

# Unsloth imports
try:
    from unsloth import FastLanguageModel
    from transformers import TextStreamer
    import transformers
except ImportError:
    print("Error: Required libraries not installed. Please install:")
    print("pip install unsloth[colab-new] torch transformers pillow")
    sys.exit(1)

def load_model_and_tokenizer(model_name="unsloth/gemma-3n-E4B-it-GGUF", max_seq_length=2048):
    """Load Gemma 3n model and tokenizer using Unsloth"""
    print(f"Loading model: {model_name}")
    print("This may take a few minutes on first run...")
    
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=None,  # Auto detection
            load_in_4bit=True,  # Use 4-bit quantization for memory efficiency
        )
        
        # Enable faster inference
        FastLanguageModel.for_inference(model)
        
        print("✅ Model loaded successfully!")
        return model, tokenizer
        
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        print("Make sure you have the required dependencies installed:")
        print("pip install unsloth[colab-new] torch transformers pillow")
        return None, None

def load_image_from_url(image_url: str) -> Image.Image:
    """Download and load an image from URL"""
    try:
        print(f"Downloading image from URL...")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except Exception as e:
        print(f"Error downloading image from URL: {e}")
        return None

def load_image_from_file(image_path: str) -> Image.Image:
    """Load an image from local file"""
    try:
        if not os.path.exists(image_path):
            print(f"Error: Image file '{image_path}' does not exist")
            return None
            
        print(f"Loading local image file...")
        image = Image.open(image_path)
        return image
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

def do_gemma_3n_inference(model, tokenizer, messages, max_new_tokens=256, temperature=1.0, top_k=64, top_p=0.95):
    """Perform inference with Gemma 3n model using Unsloth approach"""
    try:
        # Apply chat template
        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(model.device)

        # Create text streamer for real-time output
        text_streamer = TextStreamer(tokenizer, skip_prompt=True)
        
        print("Generating response...")
        print("=" * 50)
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs,
                streamer=text_streamer,
                max_new_tokens=max_new_tokens,
                use_cache=True,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                min_p=0.0,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        
        return True
        
    except Exception as e:
        print(f"Error during inference: {e}")
        return False

def get_image_description(image_source: str, model_name: str = "unsloth/gemma-3n-E4B-it-GGUF"):
    """Get detailed description of an image using Unsloth Gemma 3n"""
    print(f"Analyzing image: {image_source}")
    print(f"Using model: {model_name}")
    print("-" * 50)
    
    # Load model and tokenizer
    model, tokenizer = load_model_and_tokenizer(model_name)
    if model is None or tokenizer is None:
        return
    
    # Load image
    if is_url(image_source):
        image = load_image_from_url(image_source)
    else:
        image = load_image_from_file(image_source)
    
    if image is None:
        return
    
    # Convert image to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    print(f"Image loaded: {image.size} pixels, mode: {image.mode}")
    
    # Create messages in the format expected by Gemma 3n
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Please provide a detailed description of this image. Include information about objects, people, animals, colors, composition, setting, and any other notable details you can observe."}
        ]
    }]
    
    # Perform inference
    success = do_gemma_3n_inference(
        model, 
        tokenizer, 
        messages, 
        max_new_tokens=512,  # Allow for longer descriptions
        temperature=1.0,
        top_k=64,
        top_p=0.95
    )
    
    if not success:
        print("❌ Failed to generate description")

def main():
    parser = argparse.ArgumentParser(
        description="Generate detailed descriptions of images using Unsloth Gemma 3n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unsloth_image_describe.py /path/to/image.jpg
  python unsloth_image_describe.py photo.png
  python unsloth_image_describe.py https://example.com/image.jpg
  python unsloth_image_describe.py --model unsloth/gemma-3n-E2B-it-GGUF https://site.com/photo.png

Requirements:
  pip install unsloth[colab-new] torch transformers pillow
        """
    )
    
    parser.add_argument(
        'image_source',
        help='Path to local image file or URL to image'
    )
    
    parser.add_argument(
        '--model',
        default='unsloth/gemma-3n-E4B-it-GGUF',
        help='Unsloth Gemma 3n model to use (default: unsloth/gemma-3n-E4B-it-GGUF)'
    )
    
    args = parser.parse_args()
    
    # If it's a local file, validate image file extension
    if not is_url(args.image_source):
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        file_ext = os.path.splitext(args.image_source)[1].lower()
        
        if file_ext not in valid_extensions:
            print(f"Warning: '{file_ext}' may not be a supported image format")
            print(f"Supported formats: {', '.join(valid_extensions)}")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
    
    # Check if CUDA is available
    if torch.cuda.is_available():
        print(f"✅ CUDA available - GPU: {torch.cuda.get_device_name()}")
    else:
        print("⚠️  CUDA not available - using CPU (this will be slow)")
    
    get_image_description(args.image_source, args.model)

if __name__ == "__main__":
    main()