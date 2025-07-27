from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging
import inspect

class AbstractPersonToolManager(ABC):
    """
    Abstract base class that defines person-related tools that need to be implemented.
    Focuses on person management and fact handling operations with categorization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._available_tools = self._get_available_tools()
    
    def _get_available_tools(self) -> List[str]:
        """Get list of all available tool names based on abstract methods."""
        abstract_methods = []
        # Check all methods in the class hierarchy
        for cls in inspect.getmro(self.__class__):
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
                    if name not in abstract_methods:
                        abstract_methods.append(name)
        return abstract_methods
    
    def get_available_tools(self) -> List[str]:
        """Return list of available tool names."""
        return self._available_tools.copy()
    
    def inspect_tools(self) -> str:
        """
        Use reflection to inspect all tool methods and return their details.
        Returns formatted string with tool names, parameters, and descriptions.
        """
        tool_details = []
        tool_details.append("=" * 80)
        tool_details.append("AVAILABLE PERSON TOOLS INSPECTION")
        tool_details.append("=" * 80)
        
        # Get abstract methods from the abstract base class
        abstract_tools = []
        for cls in inspect.getmro(self.__class__):
            if cls.__name__ == 'AbstractPersonToolManager':
                for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                    if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
                        abstract_tools.append((name, method))
                break
        
        if not abstract_tools:
            tool_details.append("No abstract tools found!")
            return '\n'.join(tool_details)
        
        for tool_name, method in sorted(abstract_tools, key=lambda x: x[0]):
            try:
                # Get method signature
                sig = inspect.signature(method)
                
                # Get docstring
                docstring = inspect.getdoc(method) or "No description available"
                
                # Format tool information
                tool_details.append(f"\nTOOL: {tool_name}")
                tool_details.append("-" * 50)
                
                # Parameters
                params = []
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    param_info = f"{param_name}"
                    if param.annotation != inspect.Parameter.empty:
                        param_info += f": {param.annotation}"
                    if param.default != inspect.Parameter.empty:
                        param_info += f" = {param.default}"
                    params.append(param_info)
                
                if params:
                    tool_details.append(f"Parameters: {', '.join(params)}")
                else:
                    tool_details.append("Parameters: None")
                
                # Description from docstring
                tool_details.append(f"Description: {docstring}")
                
                # Extract expected parameters from docstring if available
                if "Expected parameters:" in docstring:
                    lines = docstring.split('\n')
                    in_params_section = False
                    expected_params = []
                    for line in lines:
                        line = line.strip()
                        if "Expected parameters:" in line:
                            in_params_section = True
                            continue
                        if in_params_section and line.startswith('- '):
                            expected_params.append(line[2:])
                        elif in_params_section and line == "":
                            break
                    
                    if expected_params:
                        tool_details.append("Expected Parameters:")
                        for param in expected_params:
                            tool_details.append(f"  - {param}")
                
            except Exception as e:
                tool_details.append(f"\nTOOL: {tool_name}")
                tool_details.append(f"Error inspecting tool: {e}")
        
        tool_details.append("\n" + "=" * 80)
        return '\n'.join(tool_details)
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for calling any tool. Routes to appropriate method.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters for the tool
            
        Returns:
            Dict with success status and result/error
        """
        if tool_name not in self._available_tools:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": self._available_tools
            }
        
        try:
            # Route to the appropriate tool method
            method = getattr(self, tool_name)
            result = method(**parameters)
            
            return {
                "success": True,
                "tool_name": tool_name,
                "result": result,
                "parameters": parameters
            }
            
        except TypeError as e:
            self.logger.error(f"Error: Incorrect arguments for tool '{tool_name}'. Details: {e}")
            return {
                "success": False,
                "error": f"Incorrect arguments for tool '{tool_name}'. Details: {e}",
                "tool_name": tool_name,
                "parameters": parameters
            }
        except Exception as e:
            self.logger.error(f"Error calling {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "parameters": parameters
            }
    
    # === PERSON MANAGEMENT TOOLS ===
    
    @abstractmethod
    def add_person(self, name: str, summary: str = None, properties: Dict[str, Any] = None) -> str:
        """
        Adds a new person or updates existing person in the database (UPSERT).
        
        ## Purpose
        Add a new person or update an existing person (UPSERT functionality)
        
        ## Use When
        User wants to add someone new or update existing person information
        
        ## Expected parameters
        - name (str): Person name (used as unique identifier)
        - summary (str, optional): Optional summary description of the person
        - properties (Dict[str, Any], optional): Additional properties as a dictionary (email, phone, location, etc.)
        
        ## Example Usage from System Prompt
        
        ### Basic Addition
        ```
        User: "Add John Smith, he's a software engineer at Google"
        Assistant: I'll add John Smith to your network.
        [Calls add_person with name="John Smith", summary="Software engineer at Google"]
        ```
        
        ### Complex Relationship Example - Step 1
        ```
        User: "Add my sister Sarah who goes to UCLA and her birthday is March 15th"
        Process:
        1. add_person for Sarah  # <-- This method
        2. add_person_fact for Sarah with fact "sister"
        3. add_person_fact for Sarah with fact "attends UCLA"
        4. add_person_fact for Sarah with fact "birthday: March 15th"
        ```
        
        ### Multiple People Processing
        ```
        User: "Add my friend Jessica from college who lives in Seattle, and my neighbor Tom who has two kids and loves gardening"
        Process:
        1. add_person for Jessica  # <-- This method
        2. add_person_fact for Jessica with fact "friend"
        3. add_person_fact for Jessica with fact "from college"
        4. add_person_fact for Jessica with fact "lives in Seattle"
        5. add_person for Tom  # <-- This method again
        6. add_person_fact for Tom with fact "neighbor"
        7. add_person_fact for Tom with fact "has two kids"
        8. add_person_fact for Tom with fact "loves gardening"
        ```
        
        ## Information Extraction Patterns
        When users mention people, ALWAYS extract:
        - **Family Relationships**: "my mom Ellen" → create person "Ellen"
        - **Professional Relationships**: "my boss Janet" → create person "Janet"  
        - **Social Relationships**: "my friend Alex" → create person "Alex"
        
        ## Important Notes
        - **UPSERT Behavior**: Adding a person with an existing name will update that person
        - **Unique Names**: Each person is identified by their name as a unique key
        - **Always followed by facts**: This method should almost always be followed by add_person_fact calls to store relationship and other details
        """
        pass
    
    @abstractmethod
    def get_all_people(self, include_relationships: bool = True) -> str:
        """
        Retrieves all people from the database.
        
        ## Purpose
        Retrieve all people from the database
        
        ## Use When
        User wants to see everyone in their network or get a complete list
        
        ## Expected parameters
        - include_relationships (bool, optional): Whether to include related entities and relationships (default: True)
        
        ## Example Usage from System Prompt
        
        ### Getting Complete Network Overview
        ```
        User: "Show me everyone in my network"
        Assistant: Let me retrieve all the people in your network.
        [Calls get_all_people with include_relationships=True]
        ```
        
        ### Network Analysis
        ```
        User: "I want to see my entire contact database"
        Assistant: I'll get all your contacts with their relationship information.
        [Calls get_all_people with include_relationships=True]
        ```
        
        ### Simple List Without Details
        ```
        User: "Just give me a list of names, no details"
        Assistant: I'll get a simple list of all people.
        [Calls get_all_people with include_relationships=False]
        ```
        
        ## Use Cases
        - **Relationship Management**: Get overview of entire network for relationship analysis
        - **Network Maintenance**: Review all contacts to identify outdated information
        - **Relationship Insights**: Analyze patterns across all relationships
        - **Contact Export**: Prepare data for external use or backup
        """
        pass
    
    @abstractmethod
    def get_person(self, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
        """
        Retrieves a specific person or people matching criteria from the database.
        
        ## Purpose
        Retrieve a specific person or people matching criteria
        
        ## Use When
        User wants to find specific person(s) or search by name
        
        ## Expected parameters
        - name (str, optional): Person name (supports partial matching)
        - person_id (str, optional): Specific person ID
        - include_relationships (bool, optional): Whether to include related entities and relationships (default: True)
        
        ## Example Usage from System Prompt
        
        ### Finding Someone by Name
        ```
        User: "Do I have anyone named Smith?"
        Assistant: Let me search for people with "Smith" in their name.
        [Calls get_person with name="Smith"]
        ```
        
        ### Partial Name Search
        ```
        User: "Find everyone with 'John' in their name"
        Assistant: I'll search for people matching 'John'.
        [Calls get_person with name="John"]
        ```
        
        ### Getting Specific Person Details
        ```
        User: "Tell me about Sarah"
        Assistant: Let me get Sarah's information and relationships.
        [Calls get_person with name="Sarah", include_relationships=True]
        ```
        
        ### Quick Lookup Without Relationships
        ```
        User: "Is Mike in my contacts?"
        Assistant: Let me check if Mike is in your network.
        [Calls get_person with name="Mike", include_relationships=False]
        ```
        
        ## Search Features
        - **Partial Matching**: Supports finding people with partial name matches
        - **Flexible Identification**: Can search by name or person_id
        - **Relationship Context**: Option to include or exclude relationship information
        
        ## Common Use Cases
        - **Before Adding Facts**: Check if person exists before adding information
        - **Relationship Context**: Get full context before suggesting interactions
        - **Contact Verification**: Verify someone is in the network
        - **Information Lookup**: Quick access to stored information about someone
        """
        pass
    
    @abstractmethod
    def delete_person(self, person_id: str = None, name: str = None) -> str:
        """
        Deletes a person and all their relationships from the database.
        
        ## Purpose
        Delete a person and all their relationships from the database
        
        ## Use When
        User wants to permanently remove someone from their network
        
        ## Expected parameters
        - person_id (str, optional): Person ID to delete
        - name (str, optional): Person name to delete (must provide either person_id or name)
        
        ## Example Usage from System Prompt
        
        ### Remove Someone Completely
        ```
        User: "Remove John from my contacts completely"
        Assistant: I'll permanently delete John and all associated information.
        [Calls delete_person with name="John"]
        ```
        
        ### Clean Up Outdated Contacts
        ```
        User: "Delete that old contact for Mike Johnson"
        Assistant: I'll remove Mike Johnson from your network.
        [Calls delete_person with name="Mike Johnson"]
        ```
        
        ### Remove by ID
        ```
        User: "Delete person ID 12345"
        Assistant: I'll remove that person from your database.
        [Calls delete_person with person_id="12345"]
        ```
        
        ## Important Warnings
        - **Permanent Action**: All changes are permanent - deletions cannot be undone
        - **Complete Removal**: Deletes person AND all their relationships/facts
        - **Cascading Effect**: Removes all stored information about the person
        
        ## Use Cases
        - **Privacy Management**: Remove people who are no longer relevant
        - **Network Cleanup**: Remove outdated or incorrect entries
        - **Relationship Changes**: Remove people after relationship ends
        - **Data Management**: Clean up duplicate or test entries
        
        ## Alternative Actions
        Consider these alternatives before deletion:
        - **Update Information**: Use add_person to update instead of delete
        - **Remove Facts Only**: Use delete_all_facts_for_person to keep person but remove details
        - **Archive Strategy**: Add a fact marking person as "archived" instead of deleting
        """
        pass
    
    # === PERSON FACT MANAGEMENT TOOLS (WITH CATEGORIZATION) ===
    
    @abstractmethod
    def add_person_fact(self, person_id: str, fact_text: str, fact_type: str = "general") -> str:
        """
        Adds a categorized fact as a property to a person using upsert functionality.
        Facts are stored as fact_1, fact_2, etc. up to fact_10, each with associated type.
        
        ## Purpose
        Add a fact about a person (stored sequentially as fact_1, fact_2, etc.)
        
        ## Use When
        User wants to record specific information or facts about someone
        
        ## Expected parameters
        - person_id (str): Person ID or name to add fact to
        - fact_text (str): The fact text to add
        - fact_type (str): Category/type of the fact (default: "general")
          Common types: "personal", "professional", "contact", "preference", "relationship", "skill", "interest", "background", "health", "general"
        
        ## Example Usage from System Prompt
        
        ### Adding Multiple Facts
        ```
        User: "John Smith likes hiking and plays guitar"
        Assistant: I'll add those facts about John Smith.
        [Calls add_person_fact with person_id="John Smith", fact_text="likes hiking", fact_type="interest"]
        [Calls add_person_fact with person_id="John Smith", fact_text="plays guitar", fact_type="interest"]
        ```
        
        ### Relationship Information (HIGHEST PRIORITY)
        ```
        User: "Add my sister Sarah who goes to UCLA and her birthday is March 15th"
        Process:
        1. add_person for Sarah
        2. add_person_fact for Sarah with fact_text="sister", fact_type="relationship"  # <-- ALWAYS FIRST
        3. add_person_fact for Sarah with fact_text="attends UCLA", fact_type="professional"
        4. add_person_fact for Sarah with fact_text="birthday: March 15th", fact_type="personal"
        ```
        
        ### Information Extraction Patterns
        
        #### Family Relationships
        ```
        "my mom Ellen" → add_person_fact(person_id="Ellen", fact_text="mother", fact_type="relationship")
        "my dad Kenny" → add_person_fact(person_id="Kenny", fact_text="father", fact_type="relationship")
        "my wife Sarah" → add_person_fact(person_id="Sarah", fact_text="wife", fact_type="relationship")
        "my brother Mike" → add_person_fact(person_id="Mike", fact_text="brother", fact_type="relationship")
        ```
        
        #### Professional Information
        ```
        "my boss Janet" → add_person_fact(person_id="Janet", fact_text="boss", fact_type="relationship")
        "works at Google" → add_person_fact(person_id="Person", fact_text="works at Google", fact_type="professional")
        "my colleague Alex" → add_person_fact(person_id="Alex", fact_text="colleague", fact_type="relationship")
        ```
        
        #### Location and Education
        ```
        "goes to UCLA" → add_person_fact(person_id="Person", fact_text="attends UCLA", fact_type="professional")
        "lives in Seattle" → add_person_fact(person_id="Person", fact_text="lives in Seattle", fact_type="personal")
        "from Boston" → add_person_fact(person_id="Person", fact_text="from Boston", fact_type="background")
        ```
        
        #### Personal Details
        ```
        "birthday is March 15th" → add_person_fact(person_id="Person", fact_text="birthday: March 15th", fact_type="personal")
        "has two kids" → add_person_fact(person_id="Person", fact_text="has two children", fact_type="personal")
        "loves gardening" → add_person_fact(person_id="Person", fact_text="enjoys gardening", fact_type="interest")
        ```
        
        ## Fact Storage Best Practices from System Prompt
        
        ### What to Track
        - **Relationship type (HIGHEST PRIORITY - always store first)**
        - Personal interests, hobbies, and passions
        - Important dates (birthdays, anniversaries, milestones)
        - Family information and significant relationships
        - Professional details and career updates
        - Recent life events and changes
        - Communication preferences and patterns
        - Shared experiences and memories
        - Goals, challenges, and aspirations
        - Geographic location and travel
        - Health updates or concerns (when appropriate)
        
        ### Fact Categories To Use
        - **relationship**: Family, professional, social relationships
        - **personal**: Birthdays, family status, personal characteristics
        - **professional**: Job, education, career details
        - **interest**: Hobbies, activities, passions
        - **contact**: Phone, email, address information
        - **background**: Origin, history, past experiences
        - **preference**: Likes, dislikes, preferences
        - **skill**: Abilities, talents, expertise
        - **health**: Health-related information (when appropriate)
        - **general**: Other miscellaneous information
        
        ## Critical Rules
        - **MANDATORY EXTRACTION**: ALWAYS extract and store ALL mentioned information as separate facts
        - **RELATIONSHIP FIRST**: Always store relationship type as the first fact
        - **SEPARATE FACTS**: Each piece of information should be a separate fact
        - **LOGICAL ORDER**: Store facts in logical order (relationship first, then other details)
        """
        pass
    
    @abstractmethod
    def delete_person_fact(self, person_id: str, fact_number: int) -> str:
        """
        Deletes a specific fact and its type from a person.
        
        ## Purpose
        Delete a specific fact from a person
        
        ## Use When
        User wants to remove a specific piece of information about someone
        
        ## Expected parameters
        - person_id (str): Person ID or name
        - fact_number (int): Fact number to delete (1-10)
        
        ## Example Usage from System Prompt
        
        ### Removing Outdated Information
        ```
        User: "Remove that old job information for Sarah, it was fact number 3"
        Assistant: I'll remove fact 3 from Sarah's information.
        [Calls delete_person_fact with person_id="Sarah", fact_number=3]
        ```
        
        ### Correcting Mistakes
        ```
        User: "Delete the second fact about John, it was wrong"
        Assistant: I'll remove fact 2 from John's profile.
        [Calls delete_person_fact with person_id="John", fact_number=2]
        ```
        
        ### Selective Information Removal
        ```
        User: "I want to keep Mike in my contacts but remove his phone number which is stored as fact 5"
        Assistant: I'll remove just that specific fact while keeping Mike in your network.
        [Calls delete_person_fact with person_id="Mike", fact_number=5]
        ```
        
        ## Use Cases
        - **Information Updates**: Remove outdated information before adding new facts
        - **Privacy Management**: Remove sensitive information while keeping person
        - **Error Correction**: Remove incorrect information that was accidentally added
        - **Selective Cleanup**: Remove specific facts without affecting other information
        
        ## Important Notes
        - **Specific Targeting**: Only removes the specified fact number and its type
        - **Preserves Person**: Person remains in network with other facts intact
        - **Permanent Action**: Deletion cannot be undone
        - **Sequential Storage**: Facts are stored as fact_1, fact_2, etc. up to fact_10
        """
        pass
    
    @abstractmethod
    def delete_all_facts_for_person(self, person_id: str) -> str:
        """
        Deletes all facts and their types (fact_1 through fact_10, fact_type_1 through fact_type_10) from a person.
        
        ## Purpose
        Delete all facts from a person
        
        ## Use When
        User wants to clear all recorded facts about someone while keeping the person
        
        ## Expected parameters
        - person_id (str): Person ID or name to delete all facts from
        
        ## Example Usage from System Prompt
        
        ### Clear All Information
        ```
        User: "Remove all the old information I had about Sarah"
        Assistant: I'll clear all facts for Sarah while keeping her in your network.
        [Calls delete_all_facts_for_person with person_id="Sarah"]
        ```
        
        ### Fresh Start
        ```
        User: "Clear everything I know about Mike, I want to start over"
        Assistant: I'll remove all stored facts about Mike but keep him as a contact.
        [Calls delete_all_facts_for_person with person_id="Mike"]
        ```
        
        ### Information Reset
        ```
        User: "Delete all details for John Smith but don't remove him from my network"
        Assistant: I'll clear all facts while keeping John Smith as a contact.
        [Calls delete_all_facts_for_person with person_id="John Smith"]
        ```
        
        ## Use Cases
        - **Complete Information Reset**: Start fresh with someone's information
        - **Privacy Cleanup**: Remove all stored details while maintaining contact
        - **Relationship Changes**: Clear old information when relationship dynamics change
        - **Data Correction**: Remove all facts when there are multiple errors
        
        ## What Gets Removed
        - **All Facts**: fact_1 through fact_10 are cleared
        - **All Fact Types**: fact_type_1 through fact_type_10 are cleared
        - **Complete Reset**: All stored information about the person is removed
        
        ## What Remains
        - **Person Entry**: The person remains in the network
        - **Basic Information**: Name and core person record preserved
        - **Network Position**: Person's place in the network structure maintained
        
        ## Alternative to Full Deletion
        This is often preferable to `delete_person` when you want to:
        - Keep the person in your network but remove details
        - Maintain relationship structure while clearing facts
        - Prepare for fresh information entry
        """
        pass
    
    @abstractmethod
    def get_facts_by_type(self, person_id: str = None, fact_type: str = None) -> str:
        """
        Retrieves facts filtered by type, optionally for a specific person.
        
        ## Purpose
        Retrieve facts filtered by type, optionally for a specific person
        
        ## Use When
        User wants to find specific types of information across their network or for a specific person
        
        ## Expected parameters
        - person_id (str, optional): Person ID or name to filter by (if None, searches all people)
        - fact_type (str, optional): Type of facts to retrieve (if None, returns all facts with their types)
        
        ## Example Usage Scenarios
        
        ### Find All Professional Information
        ```
        User: "Show me all the professional information I have about people"
        Assistant: I'll get all professional facts across your network.
        [Calls get_facts_by_type with fact_type="professional"]
        ```
        
        ### Get Someone's Interests
        ```
        User: "What interests does Sarah have?"
        Assistant: Let me find all of Sarah's interests.
        [Calls get_facts_by_type with person_id="Sarah", fact_type="interest"]
        ```
        
        ### Find All Birthdays
        ```
        User: "Show me everyone's birthday information"
        Assistant: I'll get all personal facts that might include birthdays.
        [Calls get_facts_by_type with fact_type="personal"]
        ```
        
        ### Relationship Analysis
        ```
        User: "What family relationships do I have stored?"
        Assistant: Let me find all relationship facts in your network.
        [Calls get_facts_by_type with fact_type="relationship"]
        ```
        
        ### Complete Person Profile
        ```
        User: "Show me everything I know about John"
        Assistant: I'll get all facts for John with their categories.
        [Calls get_facts_by_type with person_id="John"]
        ```
        
        ## Fact Type Categories
        - **relationship**: Family, professional, social relationships
        - **personal**: Birthdays, family status, personal characteristics  
        - **professional**: Job, education, career details
        - **interest**: Hobbies, activities, passions
        - **contact**: Phone, email, address information
        - **background**: Origin, history, past experiences
        - **preference**: Likes, dislikes, preferences
        - **skill**: Abilities, talents, expertise
        - **health**: Health-related information (when appropriate)
        - **general**: Other miscellaneous information
        
        ## Use Cases
        - **Relationship Insights**: Analyze relationship patterns across network
        - **Interest Matching**: Find people with similar interests
        - **Professional Networking**: Identify professional connections
        - **Event Planning**: Find birthdays and important dates
        - **Information Audit**: Review what types of information you have
        - **Category Analysis**: Understand information distribution patterns
        """
        pass
    
    @abstractmethod
    def update_fact_type(self, person_id: str, fact_number: int, new_fact_type: str) -> str:
        """
        Updates the type/category of an existing fact without changing the fact text.
        
        ## Purpose
        Update the type/category of an existing fact without changing the fact text
        
        ## Use When
        User wants to recategorize information without changing the actual fact content
        
        ## Expected parameters
        - person_id (str): Person ID or name
        - fact_number (int): Fact number to update type for (1-10)
        - new_fact_type (str): New type/category for the fact
        
        ## Example Usage Scenarios
        
        ### Recategorizing Information
        ```
        User: "That hobby fact about Sarah should actually be categorized as a skill"
        Assistant: I'll update the category for that fact.
        [Calls update_fact_type with person_id="Sarah", fact_number=3, new_fact_type="skill"]
        ```
        
        ### Correcting Categorization
        ```
        User: "John's fact number 2 should be professional, not general"
        Assistant: I'll update that fact's category to professional.
        [Calls update_fact_type with person_id="John", fact_number=2, new_fact_type="professional"]
        ```
        
        ### Information Organization
        ```
        User: "Change Mike's contact information from general to contact type"
        Assistant: I'll recategorize that information appropriately.
        [Calls update_fact_type with person_id="Mike", fact_number=5, new_fact_type="contact"]
        ```
        
        ## Available Fact Types
        - **relationship**: Family, professional, social relationships
        - **personal**: Birthdays, family status, personal characteristics
        - **professional**: Job, education, career details
        - **interest**: Hobbies, activities, passions
        - **contact**: Phone, email, address information
        - **background**: Origin, history, past experiences
        - **preference**: Likes, dislikes, preferences
        - **skill**: Abilities, talents, expertise
        - **health**: Health-related information (when appropriate)
        - **general**: Other miscellaneous information
        
        ## Use Cases
        - **Information Organization**: Better categorize facts for easier retrieval
        - **System Maintenance**: Correct categorization mistakes
        - **Data Quality**: Improve information structure and searchability
        - **Analysis Preparation**: Ensure proper categorization for relationship insights
        
        ## What Changes
        - **Fact Type Only**: Only the category/type is updated
        - **Fact Text Preserved**: The actual information remains unchanged
        - **Better Organization**: Improves ability to filter and analyze information
        
        ## When to Use
        - **After Initial Entry**: Refine categorization after adding facts quickly
        - **System Evolution**: Update categories as your system understanding improves
        - **Error Correction**: Fix miscategorized information
        - **Organization Improvement**: Better structure your information for insights
        """
        pass