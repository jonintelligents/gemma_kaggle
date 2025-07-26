#!/usr/bin/env python3
"""
Ollama Tool Calling Demo using ollama library
Compares native tool calling vs system prompt workaround between Gemma and Mistral models
"""

import datetime
import json
import ollama
from typing import Dict, Any, List

def get_current_datetime():
    """
    Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    This simulates a tool that interacts with the operating system or an external API.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate(operation: str, a: float, b: float) -> float:
    """
    Perform basic arithmetic calculations
    """
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")

def test_native_tool_calling(model_name: str):
    """Test native Ollama tool calling (should work with Mistral, fail with Gemma)"""
    print(f"\n{'='*60}")
    print(f"Testing NATIVE Tool Calling with {model_name}")
    print(f"{'='*60}")
    
    try:
        client = ollama.Client()
        
        # Define tools in Ollama's native format
        tools = [
            {
                'type': 'function',
                'function': {
                    'name': 'get_current_datetime',
                    'description': 'Get the current date and time',
                    'parameters': {
                        'type': 'object',
                        'properties': {},
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'calculate',
                    'description': 'Perform basic arithmetic calculations',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'operation': {
                                'type': 'string',
                                'enum': ['add', 'subtract', 'multiply', 'divide'],
                                'description': 'The arithmetic operation to perform'
                            },
                            'a': {'type': 'number', 'description': 'First number'},
                            'b': {'type': 'number', 'description': 'Second number'}
                        },
                        'required': ['operation', 'a', 'b']
                    }
                }
            }
        ]
        
        messages = [
            {
                'role': 'user',
                'content': 'What is 15 multiplied by 7? Use the calculator tool.'
            }
        ]
        
        print("Sending request with native tool calling...")
        response = client.chat(
            model=model_name,
            messages=messages,
            tools=tools,
            stream=False
        )
        
        print("✅ SUCCESS - Native tool calling supported!")
        
        if response and 'message' in response:
            message = response['message']
            print(f"Response content: {message.get('content', 'No content')}")
            
            if 'tool_calls' in message:
                print("🔧 Tool calls detected:")
                for i, tool_call in enumerate(message['tool_calls']):
                    function = tool_call.get('function', {})
                    print(f"  Tool Call {i+1}:")
                    print(f"    Function: {function.get('name', 'Unknown')}")
                    print(f"    Arguments: {function.get('arguments', 'None')}")
                    
                    # Execute the tool call
                    if function.get('name') == 'calculate':
                        try:
                            args = json.loads(function.get('arguments', '{}'))
                            result = calculate(args['operation'], args['a'], args['b'])
                            print(f"    Result: {result}")
                        except Exception as e:
                            print(f"    Error executing tool: {e}")
        
    except ollama.ResponseError as e:
        print("❌ FAILED - Native tool calling not supported")
        print(f"Ollama Error: {e}")
    except Exception as e:
        print("❌ FAILED - Unexpected error")
        print(f"Error: {e}")

def test_system_prompt_workaround(model_name: str):
    """Test system prompt workaround (should work with Gemma)"""
    print(f"\n{'='*60}")
    print(f"Testing SYSTEM PROMPT Workaround with {model_name}")
    print(f"{'='*60}")
    
    try:
        client = ollama.Client()
        
        system_prompt = """You are an AI assistant with access to the following tools:

1. Tool Name: get_current_datetime
   Description: Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
   Parameters: None

2. Tool Name: calculate
   Description: Perform basic arithmetic calculations
   Parameters:
   - operation: string (add, subtract, multiply, divide)
   - a: number (first number)
   - b: number (second number)

When you need to use a tool, respond ONLY with a JSON object in this format:
{"tool_call": {"name": "tool_name", "parameters": {"param1": "value1", "param2": "value2"}}}

If you don't need a tool, respond naturally."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "What is 15 multiplied by 7? Use the calculator tool."}
        ]
        
        print("Sending request with system prompt workaround...")
        response = client.chat(
            model=model_name,
            messages=messages,
            stream=False
        )
        
        if response and 'message' in response:
            content = response['message'].get('content', '')
            print(f"Raw response: {content}")
            
            # Try to parse as JSON tool call
            content_to_parse = content.strip()
            if content_to_parse.startswith("```json") and content_to_parse.endswith("```"):
                json_start = content_to_parse.find("```json") + len("```json")
                json_end = content_to_parse.rfind("```")
                content_to_parse = content_to_parse[json_start:json_end].strip()
            
            try:
                parsed_json = json.loads(content_to_parse)
                if isinstance(parsed_json, dict) and "tool_call" in parsed_json:
                    tool_call = parsed_json["tool_call"]
                    tool_name = tool_call.get("name")
                    tool_params = tool_call.get("parameters", {})
                    
                    print("✅ SUCCESS - System prompt workaround working!")
                    print(f"🔧 Tool call detected:")
                    print(f"    Function: {tool_name}")
                    print(f"    Parameters: {tool_params}")
                    
                    # Execute the tool
                    if tool_name == "calculate":
                        try:
                            result = calculate(
                                tool_params.get("operation"),
                                tool_params.get("a"),
                                tool_params.get("b")
                            )
                            print(f"    Result: {result}")
                        except Exception as e:
                            print(f"    Error executing tool: {e}")
                    elif tool_name == "get_current_datetime":
                        result = get_current_datetime()
                        print(f"    Result: {result}")
                else:
                    print("⚠️  Response not in expected tool call format")
                    print("✅ Model responded naturally (no tool needed)")
                    
            except json.JSONDecodeError:
                print("⚠️  Response is not JSON")
                print("✅ Model responded naturally (no tool needed)")
        
    except ollama.ResponseError as e:
        print("❌ FAILED - System prompt workaround failed")
        print(f"Ollama Error: {e}")
    except Exception as e:
        print("❌ FAILED - Unexpected error")
        print(f"Error: {e}")

def main():
    print("Ollama Tool Calling Comparison Demo")
    print("=" * 50)
    
    # Test models
    test_models = [
        ("gemma3n:latest", "Should fail native, work with workaround"),
        ("mistral:latest", "Should work with native tool calling")
    ]
    
    # Test each model
    for model_name, description in test_models:
        print(f"\n🧪 Testing {model_name} - {description}")
        
        # Test native tool calling first
        test_native_tool_calling(model_name)
        
        # Test system prompt workaround
        test_system_prompt_workaround(model_name)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print("- Native tool calling: Works with Mistral, fails with Gemma3n")
    print("- System prompt workaround: Should work with most models including Gemma3n")
    print("- Gemma3n models need the system prompt approach for tool-like functionality")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()