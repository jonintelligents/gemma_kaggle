#!/usr/bin/env python3
"""
Test suite for PromptManager class.

This file demonstrates all test cases and usage scenarios for the PromptManager.
"""

import os
import tempfile
import shutil
from PromptManager import PromptManager


def test_basic_functionality():
    """Test basic loading and retrieval functionality."""
    print("=" * 60)
    print("TEST: Basic Functionality")
    print("=" * 60)
    
    # Create temporary directory with sample prompts
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Sample prompt files
        prompts = {
            "greeting.md": "Hello {name}! Welcome to {platform}.",
            "email.md": """Subject: {subject}

Dear {recipient},

{body}

Best regards,
{sender}""",
            "simple.md": "This is a simple prompt with no variables.",
            "complex.md": "User {user_id} from {country} wants to {action} on {date}."
        }
        
        # Write sample files
        for filename, content in prompts.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Initialize PromptManager
        pm = PromptManager(temp_dir)
        
        print(f"PromptManager: {pm}")
        print(f"Number of prompts loaded: {len(pm)}")
        print("Loaded prompts:", pm.list_prompts())
        print()
        
        # Test getting variables for each prompt
        for prompt_name in pm.list_prompts():
            variables = pm.get_prompt_variables(prompt_name)
            print(f"Variables for '{prompt_name}': {variables}")
        print()
        
        # Test simple prompt (no variables)
        simple = pm.get_prompt("simple")
        print("Simple prompt result:")
        print(f"'{simple}'")
        print()
        
        # Test prompt with variables
        greeting = pm.get_prompt("greeting", {"name": "Alice", "platform": "ChatBot"})
        print("Greeting prompt result:")
        print(f"'{greeting}'")
        print()
        
        # Test complex prompt
        complex_prompt = pm.get_prompt("complex", {
            "user_id": "12345",
            "country": "USA",
            "action": "purchase",
            "date": "2024-12-25"
        })
        print("Complex prompt result:")
        print(f"'{complex_prompt}'")
        print()
        
        # Test email prompt
        email = pm.get_prompt("email", {
            "subject": "Project Update",
            "recipient": "John Doe",
            "body": "The project is progressing well. We expect to complete it by next week.",
            "sender": "Jane Smith"
        })
        print("Email prompt result:")
        print(email)
        print()
        
    finally:
        shutil.rmtree(temp_dir)


def test_error_cases():
    """Test various error conditions and edge cases."""
    print("=" * 60)
    print("TEST: Error Cases")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create test prompts
        prompts = {
            "greeting.md": "Hello {name}! Welcome to {platform}.",
            "simple.md": "This is a simple prompt with no variables."
        }
        
        for filename, content in prompts.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        pm = PromptManager(temp_dir)
        
        # Test 1: Non-existent prompt
        print("Test 1: Non-existent prompt")
        try:
            pm.get_prompt("nonexistent")
        except KeyError as e:
            print(f"✓ Expected KeyError: {e}")
        print()
        
        # Test 2: Missing required variables
        print("Test 2: Missing required variables")
        try:
            pm.get_prompt("greeting", {"name": "Bob"})  # Missing 'platform'
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")
        print()
        
        # Test 3: Extra variables provided
        print("Test 3: Extra variables provided")
        try:
            pm.get_prompt("simple", {"extra": "value"})  # Simple has no variables
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")
        print()
        
        # Test 4: Variables needed but none provided
        print("Test 4: Variables needed but none provided")
        try:
            pm.get_prompt("greeting")  # No variables provided
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")
        print()
        
        # Test 5: Extra and missing variables
        print("Test 5: Extra variables (should mention extra ones)")
        try:
            pm.get_prompt("greeting", {
                "name": "Alice", 
                "platform": "Test",
                "extra1": "value1",
                "extra2": "value2"
            })
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")
        print()
        
        # Test 6: Get variables for non-existent prompt
        print("Test 6: Get variables for non-existent prompt")
        try:
            pm.get_prompt_variables("nonexistent")
        except KeyError as e:
            print(f"✓ Expected KeyError: {e}")
        print()
        
    finally:
        shutil.rmtree(temp_dir)


def test_directory_errors():
    """Test directory-related error conditions."""
    print("=" * 60)
    print("TEST: Directory Error Cases")
    print("=" * 60)
    
    # Test 1: Non-existent directory
    print("Test 1: Non-existent directory")
    try:
        pm = PromptManager("/path/that/does/not/exist")
    except FileNotFoundError as e:
        print(f"✓ Expected FileNotFoundError: {e}")
    print()
    
    # Test 2: Path is a file, not directory
    print("Test 2: Path is a file, not directory")
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        temp_file.close()
        pm = PromptManager(temp_file.name)
    except NotADirectoryError as e:
        print(f"✓ Expected NotADirectoryError: {e}")
    finally:
        os.unlink(temp_file.name)
    print()


def test_utility_methods():
    """Test utility and helper methods."""
    print("=" * 60)
    print("TEST: Utility Methods")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create test prompts
        prompts = {
            "greeting.md": "Hello {name}!",
            "simple.md": "No variables here."
        }
        
        for filename, content in prompts.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        pm = PromptManager(temp_dir)
        
        # Test has_prompt
        print("Test has_prompt method:")
        print(f"Has 'greeting': {pm.has_prompt('greeting')}")
        print(f"Has 'nonexistent': {pm.has_prompt('nonexistent')}")
        print()
        
        # Test get_raw_prompt
        print("Test get_raw_prompt method:")
        raw_greeting = pm.get_raw_prompt("greeting")
        print(f"Raw greeting: '{raw_greeting}'")
        print()
        
        # Test reload functionality
        print("Test reload functionality:")
        # Add a new prompt file
        with open(os.path.join(temp_dir, "new_prompt.md"), 'w') as f:
            f.write("This is a new prompt with {variable}.")
        
        print(f"Before reload: {pm.list_prompts()}")
        pm.reload()
        print(f"After reload: {pm.list_prompts()}")
        print(f"Variables in new prompt: {pm.get_prompt_variables('new_prompt')}")
        print()
        
    finally:
        shutil.rmtree(temp_dir)


def test_edge_cases():
    """Test edge cases and special scenarios."""
    print("=" * 60)
    print("TEST: Edge Cases")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Edge case prompts
        prompts = {
            "empty.md": "",
            "whitespace.md": "   \n\t  ",
            "special_chars.md": "Hello {user_name}! Your balance is ${amount}.",
            "multiple_same_var.md": "{name} and {name} are both named {name}.",
            "mixed_braces.md": "Use {{literal_braces}} but replace {variable}.",
            "unicode.md": "Hello {name}! 你好 {chinese_name}! 🎉 {emoji_var}",
            "multiline.md": """Line 1 with {var1}
Line 2 with {var2}
Line 3 with {var1} again""",
        }
        
        for filename, content in prompts.items():
            with open(os.path.join(temp_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content)
        
        pm = PromptManager(temp_dir)
        
        # Test empty prompt
        print("Test 1: Empty prompt")
        empty_result = pm.get_prompt("empty")
        print(f"Empty prompt result: '{empty_result}'")
        print(f"Variables needed: {pm.get_prompt_variables('empty')}")
        print()
        
        # Test whitespace prompt
        print("Test 2: Whitespace prompt")
        ws_result = pm.get_prompt("whitespace")
        print(f"Whitespace prompt result: '{repr(ws_result)}'")
        print()
        
        # Test special characters
        print("Test 3: Special characters")
        special_result = pm.get_prompt("special_chars", {
            "user_name": "Alice",
            "amount": "100.50"
        })
        print(f"Special chars result: '{special_result}'")
        print()
        
        # Test multiple same variable
        print("Test 4: Multiple same variable")
        multiple_result = pm.get_prompt("multiple_same_var", {"name": "Bob"})
        print(f"Multiple same var result: '{multiple_result}'")
        print(f"Variables needed: {pm.get_prompt_variables('multiple_same_var')}")
        print()
        
        # Test literal braces
        print("Test 5: Mixed braces (literal and template)")
        mixed_result = pm.get_prompt("mixed_braces", {"variable": "replaced_value"})
        print(f"Mixed braces result: '{mixed_result}'")
        print(f"Variables needed: {pm.get_prompt_variables('mixed_braces')}")
        print()
        
        # Test unicode
        print("Test 6: Unicode characters")
        unicode_result = pm.get_prompt("unicode", {
            "name": "Alice", 
            "chinese_name": "爱丽丝",
            "emoji_var": "🚀"
        })
        print(f"Unicode result: '{unicode_result}'")
        print()
        
        # Test multiline
        print("Test 7: Multiline template")
        multiline_result = pm.get_prompt("multiline", {"var1": "VALUE1", "var2": "VALUE2"})
        print("Multiline result:")
        print(multiline_result)
        print(f"Variables needed: {pm.get_prompt_variables('multiline')}")
        print()
        
    finally:
        shutil.rmtree(temp_dir)


def test_realistic_scenarios():
    """Test realistic usage scenarios."""
    print("=" * 60)
    print("TEST: Realistic Scenarios")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Realistic prompt templates
        prompts = {
            "chatbot_system.md": """You are a helpful assistant named {bot_name}.
Your role is to {role}.
Please respond in a {tone} manner.
Current context: {context}""",
            
            "code_review.md": """Please review the following {language} code:

```{language}
{code}
```

Focus on:
- {focus_area_1}
- {focus_area_2}
- {focus_area_3}

Provide feedback for: {developer_name}""",
            
            "email_template.md": """From: {sender_email}
To: {recipient_email}
Subject: {subject}

Dear {recipient_name},

{opening_line}

{main_content}

{closing_line}

Best regards,
{sender_name}
{sender_title}
{company}""",
        }
        
        for filename, content in prompts.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        pm = PromptManager(temp_dir)
        
        # Scenario 1: Chatbot system prompt
        print("Scenario 1: Chatbot System Prompt")
        print("Variables needed:", pm.get_prompt_variables("chatbot_system"))
        
        chatbot_prompt = pm.get_prompt("chatbot_system", {
            "bot_name": "CodeHelper",
            "role": "assist with programming questions",
            "tone": "professional and encouraging",
            "context": "User is learning Python"
        })
        print("Generated prompt:")
        print(chatbot_prompt)
        print()
        
        # Scenario 2: Code review prompt
        print("Scenario 2: Code Review Prompt")
        print("Variables needed:", pm.get_prompt_variables("code_review"))
        
        code_review_prompt = pm.get_prompt("code_review", {
            "language": "Python",
            "code": "def hello():\n    print('Hello World')",
            "focus_area_1": "Code style and PEP 8 compliance",
            "focus_area_2": "Error handling",
            "focus_area_3": "Documentation",
            "developer_name": "Junior Developer"
        })
        print("Generated prompt:")
        print(code_review_prompt)
        print()
        
        # Scenario 3: Email template
        print("Scenario 3: Email Template")
        print("Variables needed:", pm.get_prompt_variables("email_template"))
        
        email_prompt = pm.get_prompt("email_template", {
            "sender_email": "jane.doe@company.com",
            "recipient_email": "client@example.com",
            "subject": "Project Proposal",
            "recipient_name": "Mr. Johnson",
            "opening_line": "I hope this email finds you well.",
            "main_content": "I am writing to present our proposal for the upcoming project. We believe our solution will meet all your requirements while staying within budget.",
            "closing_line": "Please let me know if you have any questions or would like to schedule a meeting.",
            "sender_name": "Jane Doe",
            "sender_title": "Project Manager",
            "company": "TechSolutions Inc."
        })
        print("Generated email:")
        print(email_prompt)
        print()
        
    finally:
        shutil.rmtree(temp_dir)


def run_all_tests():
    """Run all test suites."""
    print("PROMPT MANAGER TEST SUITE")
    print("=" * 60)
    print()
    
    test_functions = [
        test_basic_functionality,
        test_error_cases,
        test_directory_errors,
        test_utility_methods,
        test_edge_cases,
        test_realistic_scenarios
    ]
    
    for test_func in test_functions:
        try:
            test_func()
        except Exception as e:
            print(f"ERROR in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()