from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging
import inspect

class AbstractPersonToolManager(ABC):
    """
    Abstract base class for person-related tools with fact management and categorization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._available_tools = self._get_available_tools()
    
    def _get_available_tools(self) -> List[str]:
        """Get list of all available tool names based on abstract methods."""
        abstract_methods = []
        for cls in inspect.getmro(self.__class__):
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
                    if name not in abstract_methods:
                        abstract_methods.append(name)
        return abstract_methods
    
    def get_available_tools(self) -> List[str]:
        """Return list of available tool names."""
        return self._available_tools.copy()
    
    def get_available_tools_detailed(self) -> str:
        """Use reflection to inspect all tool methods and return their details."""
        tool_details = []
        tool_details.append("=" * 80)
        tool_details.append("AVAILABLE PERSON TOOLS INSPECTION")
        tool_details.append("=" * 80)
        
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
                sig = inspect.signature(method)
                docstring = inspect.getdoc(method) or "No description available"
                
                tool_details.append(f"\nTOOL: {tool_name}")
                tool_details.append("-" * 50)
                
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
                
                tool_details.append(f"Description: {docstring}")
                
            except Exception as e:
                tool_details.append(f"\nTOOL: {tool_name}")
                tool_details.append(f"Error inspecting tool: {e}")
        
        tool_details.append("\n" + "=" * 80)
        return '\n'.join(tool_details)
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for calling any tool. Routes to appropriate method."""
        if tool_name not in self._available_tools:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": self._available_tools
            }
        
        try:
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
    def add_person(self, name: str, properties: Dict[str, Any] = None) -> str:
        """
        Add or update person with comprehensive personal/professional information (UPSERT).
        
        **NAME HANDLING:**
        - If name is unknown, create descriptive identifier: "UNKNOWN - [brief description]"
        - Examples: "UNKNOWN - barista at Starbucks", "UNKNOWN - person from gym class"
        
        **TIMESTAMP REQUIREMENT:**
        - Always include "date_updated" in properties with current timestamp
        - Format: "YYYY-MM-DD HH:MM:SS" or ISO format
        
        **IMPORTANT: Only include properties with actual values. Do NOT include:**
        - Empty dictionaries: {}
        - Null/None values
        - Empty strings or empty lists
        
        Expected properties (only include if you have actual values):
        - System: date_updated (REQUIRED - current timestamp)
        - Contact: email, mobile_phone, home_phone, work_phone, address, work_address, city, state, country, postal_code
        - Personal: age, birthday, gender, marital_status, personality_traits, interests, languages, education_level
        - Relationship: relationship ("mom", "dad", "coworker", "friend", etc.), relationship_status, closeness_level  
        - Professional: job_title, company, industry, department, seniority_level, work_location, linkedin
        - Social: preferred_contact, social_media, communication_frequency, time_zone
        - Context: how_we_met, met_date, last_contact, importance_level, notes
        
        Examples:
        add_person("John Smith", {"job_title": "Engineer", "company": "Google", "date_updated": "2024-01-15 14:30:00"})
        add_person("UNKNOWN - coffee shop regular", {"relationship": "acquaintance", "date_updated": "2024-01-15 14:30:00"})
        add_person("Jessica", {"relationship": "friend", "city": "Seattle", "date_updated": "2024-01-15 14:30:00"})
        
        **CRITICAL: MUST be followed by add_person_fact calls for EVERY piece of information:**
        1. FIRST fact: relationship type (e.g., "friend", "mom", "coworker")
        2. Separate facts for each detail mentioned (location, interests, background, etc.)
        """
        pass
    
    @abstractmethod
    def get_all_people(self, include_relationships: bool = True) -> str:
        """
        Retrieve all people from database with optional relationships.
        Use for network overviews, contact lists, or relationship analysis.
        
        Examples:
        get_all_people()  # Full network with relationships
        get_all_people(include_relationships=False)  # Names only
        """
        pass
    
    @abstractmethod
    def get_person(self, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
        """
        Find specific person(s) by name with partial matching.
        Use before adding facts or for contact verification.
        
        Run when asked:
        What information do you have on <person name>?
        Give me information on <person name>?
        What do you know about <person name>?
        Who is <person name>?

        Examples:
        get_person(name="Smith")  # Find anyone with "Smith" in name
        get_person(name="Sarah", include_relationships=True)  # Full Sarah profile
        """
        pass
    
    @abstractmethod
    def delete_person(self, person_id: str = None, name: str = None) -> str:
        """
        Permanently delete person and all relationships/facts.
        Cannot be undone. Consider alternatives like delete_all_facts_for_person.
        
        Examples:
        delete_person(name="John Smith")  # Remove John completely
        delete_person(person_id="12345")  # Remove by ID
        """
        pass
    
    # === PERSON FACT MANAGEMENT TOOLS ===
    
    @abstractmethod
    def add_person_fact(self, person_id: str, fact_text: str, fact_type: str = "general") -> str:
        """
        Add categorized fact to person (stored as fact_1, fact_2, etc. up to fact_10).
        
        Fact types: "relationship", "personal", "professional", "interest", "contact", 
        "background", "preference", "skill", "health", "general"
        
        CRITICAL: Always store relationship type as FIRST fact when adding new person.
        Extract and store ALL mentioned information as separate facts.
        
        Examples:
        - "my mom Sarah" → fact_text="mother", fact_type="relationship" (FIRST)
        - "likes hiking" → fact_text="likes hiking", fact_type="interest"
        - "works at Google" → fact_text="works at Google", fact_type="professional"
        """
        pass
    
    @abstractmethod
    def delete_person_fact(self, person_id: str, fact_number: int) -> str:
        """
        Delete specific fact (1-10) from person while preserving other information.
        Use for outdated info, corrections, or selective cleanup.
        
        Examples:
        delete_person_fact("Sarah", 3)  # Remove Sarah's 3rd fact
        delete_person_fact("John Smith", 1)  # Remove John's 1st fact
        """
        pass
    
    @abstractmethod
    def delete_all_facts_for_person(self, person_id: str) -> str:
        """
        Clear all facts (fact_1 through fact_10) while keeping person in network.
        Preserves person entry but removes all stored details.
        
        Examples:
        delete_all_facts_for_person("Sarah")  # Clear all Sarah's facts
        delete_all_facts_for_person("Mike Johnson")  # Fresh start for Mike
        """
        pass
    
    @abstractmethod
    def get_facts_by_type(self, person_id: str = None, fact_type: str = None) -> str:
        """
        Retrieve facts filtered by type and/or person.
        
        Examples:
        get_facts_by_type(fact_type="personal")  # All birthdays/personal info
        get_facts_by_type(person_id="John", fact_type="interest")  # John's interests
        get_facts_by_type(fact_type="relationship")  # All relationships
        get_facts_by_type(person_id="Sarah")  # All Sarah's facts
        """
        pass
    
    @abstractmethod
    def update_fact_type(self, person_id: str, fact_number: int, new_fact_type: str) -> str:
        """
        Update fact category without changing text content.
        Use for recategorization, error correction, or better organization.
        
        Examples:
        update_fact_type("Sarah", 3, "skill")  # Change fact 3 to skill type
        update_fact_type("John", 2, "professional")  # Recategorize as professional
        """
        pass

    @abstractmethod
    def search(self, query: str) -> str:
        """
        Search for people in the database based on various criteria.
        
        This function can handle different types of queries and finds people based on interests or facts:
        - Direct name searches: "Marcus", "Sarah"
        - Descriptive queries: "who is the person that works at Google?"
        - Interest-based queries: "who likes pizza?", "who enjoys hiking?"
        - Location-based queries: "where do people like to go?", "who visits museums?"
        - Any text that might match person names, properties, facts, or relationships
        
        The search will look through:
        - Person names (fuzzy matching)
        - Person properties 
        - Connected facts and entities
        - Relationship information
        
        Args:
            driver: Neo4j driver instance
            query: Search string or phrase - can be a name or descriptive query
            
        Returns:
            JSON string with found people and their information
        """
        pass