from AbstractToolManager import AbstractPersonToolManager
from typing import Any, Dict
from SVO import SVO
import pprint

class ExamplePersonToolManager(AbstractPersonToolManager):
    """
    Example concrete implementation of the AbstractPersonToolManager with fact categorization.
    This shows stubs for all required methods.
    """
    
    def __init__(self):
        super().__init__()
        # Example in-memory storage for demonstration
        self.people_data = {}
        self.extractor = SVO()
    
    def add_person(self, name: str, summary: str = None, properties: Dict[str, Any] = None) -> str:
        props_str = f" with properties: {properties}" if properties else ""
        summary_str = f" and summary: '{summary}'" if summary else ""
        return f"Person '{name}' added/updated{summary_str}{props_str}"
    
    def get_all_people(self, include_relationships: bool = True) -> str:
        rel_str = "with relationships" if include_relationships else "without relationships"
        return f"Retrieved all people {rel_str}"
    
    def get_person(self, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
        identifier = f"name: '{name}'" if name else f"id: '{person_id}'" if person_id else "all people"
        rel_str = "with relationships" if include_relationships else "without relationships"
        return f"Retrieved person(s) - {identifier} {rel_str}"
    
    def delete_person(self, person_id: str = None, name: str = None) -> str:
        identifier = f"id: '{person_id}'" if person_id else f"name: '{name}'"
        return f"Deleted person - {identifier}"
    
    def add_person_fact(self, person_id: str, fact_text: str, fact_type: str = "general") -> str:
        output = self.extractor.extract(str)
        pprint.pprint(output)

        return f"Added {fact_type} fact to person '{person_id}': {fact_text}"
    
    def delete_person_fact(self, person_id: str, fact_number: int) -> str:
        return f"Deleted fact {fact_number} and its type from person '{person_id}'"
    
    def delete_all_facts_for_person(self, person_id: str) -> str:
        return f"Deleted all facts and their types from person '{person_id}'"
    
    def get_facts_by_type(self, person_id: str = None, fact_type: str = None) -> str:
        person_str = f" for person '{person_id}'" if person_id else " for all people"
        type_str = f" of type '{fact_type}'" if fact_type else " of all types"
        return f"Retrieved facts{type_str}{person_str}"
    
    def update_fact_type(self, person_id: str, fact_number: int, new_fact_type: str) -> str:
        return f"Updated fact {fact_number} type to '{new_fact_type}' for person '{person_id}'"
    

# Example usage demonstrating the enhanced documentation
if __name__ == "__main__":
    # Create an instance of the concrete tool manager
    tool_manager = ExamplePersonToolManager()
    
    # List available tools
    print("Available tools:", tool_manager.get_available_tools())
    print()
    
    # Inspect all tools with enhanced documentation
    print(tool_manager.inspect_tools())
    
    # Test some tool calls based on system prompt examples
    print("\n" + "="*80)
    print("TESTING TOOL CALLS WITH SYSTEM PROMPT EXAMPLES")
    print("="*80)
    
    # Example 1: Basic person addition
    print("\n--- Example 1: Basic Addition ---")
    print("User: 'Add John Smith, he's a software engineer at Google'")
    result = tool_manager.call_tool('add_person', {
        'name': 'John Smith', 
        'summary': 'Software engineer at Google'
    })
    print("Result:", result['result'] if result['success'] else result['error'])
    
    # Example 2: Complex relationship processing
    print("\n--- Example 2: Complex Relationship Processing ---")
    print("User: 'Add my sister Sarah who goes to UCLA and her birthday is March 15th'")
    
    # Step 1: Add person
    result1 = tool_manager.call_tool('add_person', {'name': 'Sarah'})
    print("Step 1 - Add person:", result1['result'] if result1['success'] else result1['error'])
    
    # Step 2: Add relationship fact (HIGHEST PRIORITY)
    result2 = tool_manager.call_tool('add_person_fact', {
        'person_id': 'Sarah',
        'fact_text': 'sister',
        'fact_type': 'relationship'
    })
    print("Step 2 - Add relationship:", result2['result'] if result2['success'] else result2['error'])
    
    # Step 3: Add education fact
    result3 = tool_manager.call_tool('add_person_fact', {
        'person_id': 'Sarah',
        'fact_text': 'attends UCLA',
        'fact_type': 'professional'
    })
    print("Step 3 - Add education:", result3['result'] if result3['success'] else result3['error'])
    
    # Step 4: Add birthday fact
    result4 = tool_manager.call_tool('add_person_fact', {
        'person_id': 'Sarah',
        'fact_text': 'birthday: March 15th',
        'fact_type': 'personal'
    })
    print("Step 4 - Add birthday:", result4['result'] if result4['success'] else result4['error'])
    
    # Example 3: Multiple people processing
    print("\n--- Example 3: Multiple People Processing ---")
    print("User: 'Add my friend Jessica from college who lives in Seattle, and my neighbor Tom who has two kids and loves gardening'")
    
    # Jessica processing
    print("\n-- Processing Jessica --")
    result = tool_manager.call_tool('add_person', {'name': 'Jessica'})
    print("Add Jessica:", result['result'] if result['success'] else result['error'])
    
    facts_jessica = [
        ('friend', 'relationship'),
        ('from college', 'background'),
        ('lives in Seattle', 'personal')
    ]
    
    for fact_text, fact_type in facts_jessica:
        result = tool_manager.call_tool('add_person_fact', {
            'person_id': 'Jessica',
            'fact_text': fact_text,
            'fact_type': fact_type
        })
        print(f"Add fact '{fact_text}':", result['result'] if result['success'] else result['error'])
    
    # Tom processing
    print("\n-- Processing Tom --")
    result = tool_manager.call_tool('add_person', {'name': 'Tom'})
    print("Add Tom:", result['result'] if result['success'] else result['error'])
    
    facts_tom = [
        ('neighbor', 'relationship'),
        ('has two children', 'personal'),
        ('loves gardening', 'interest')
    ]
    
    for fact_text, fact_type in facts_tom:
        result = tool_manager.call_tool('add_person_fact', {
            'person_id': 'Tom',
            'fact_text': fact_text,
            'fact_type': fact_type
        })
        print(f"Add fact '{fact_text}':", result['result'] if result['success'] else result['error'])
    
    # Example 4: Search and retrieval
    print("\n--- Example 4: Search and Retrieval ---")
    print("User: 'Do I have anyone named Smith?'")
    result = tool_manager.call_tool('get_person', {'name': 'Smith'})
    print("Search result:", result['result'] if result['success'] else result['error'])
    
    # Example 5: Fact management
    print("\n--- Example 5: Fact Management ---")
    print("User: 'Show me all the professional information I have about people'")
    result = tool_manager.call_tool('get_facts_by_type', {'fact_type': 'professional'})
    print("Professional facts:", result['result'] if result['success'] else result['error'])
    
    print("User: 'What interests does Tom have?'")
    result = tool_manager.call_tool('get_facts_by_type', {
        'person_id': 'Tom',
        'fact_type': 'interest'
    })
    print("Tom's interests:", result['result'] if result['success'] else result['error'])
    
    # Example 6: Information cleanup
    print("\n--- Example 6: Information Cleanup ---")
    print("User: 'Remove all the old information I had about Sarah'")
    result = tool_manager.call_tool('delete_all_facts_for_person', {'person_id': 'Sarah'})
    print("Cleanup result:", result['result'] if result['success'] else result['error'])
    
    print("\n" + "="*80)
    print("ENHANCED DOCUMENTATION FEATURES DEMONSTRATED")
    print("="*80)
    print("✓ Comprehensive example usage from system prompt")
    print("✓ Step-by-step processing workflows")
    print("✓ Information extraction patterns")
    print("✓ Fact categorization best practices")
    print("✓ Use case scenarios and guidance")
    print("✓ Integration with relationship management principles")
    print("="*80)