import os
import re
from typing import Dict, List, Set

class PromptManager:
    """
    A class to manage prompt templates stored as markdown files.
    
    Supports f-string style templating with variable substitution and validation.
    """
    
    def __init__(self, prompts_dir: str = "./prompts"):
        """
        Initialize the PromptManager with a directory containing markdown prompt files.
        
        Args:
            prompts_dir (str): Directory path containing .md prompt files
        """
        self.prompts_dir = prompts_dir
        self.prompts = {}
        self._template_vars = {}  # Cache for template variables
        self.load_prompts()
    
    def load_prompts(self) -> None:
        """Load all markdown files from the prompts directory into the prompts dictionary."""
        if not os.path.exists(self.prompts_dir):
            raise FileNotFoundError(f"Prompts directory '{self.prompts_dir}' does not exist")
        
        if not os.path.isdir(self.prompts_dir):
            raise NotADirectoryError(f"'{self.prompts_dir}' is not a directory")
        
        self.prompts.clear()
        self._template_vars.clear()
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.md'):
                prompt_name = filename[:-3]  # Remove .md extension
                filepath = os.path.join(self.prompts_dir, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        content = file.read()
                        self.prompts[prompt_name] = content
                        # Cache template variables for this prompt
                        self._template_vars[prompt_name] = self._extract_template_vars(content)
                except Exception as e:
                    raise IOError(f"Error reading file '{filepath}': {e}")
    
    def _extract_template_vars(self, template: str) -> Set[str]:
        """
        Extract variable names from f-string style template.
        
        Args:
            template (str): Template string with {variable} placeholders
            
        Returns:
            Set[str]: Set of variable names found in the template
        """
        # Find all {variable} patterns, excluding {{ and }} (literal braces)
        pattern = r'\{([^{}]+)\}'
        matches = re.findall(pattern, template)
        
        variables = set()
        for match in matches:
            # Handle simple variable names (no complex expressions)
            var_name = match.strip()
            # Only accept simple variable names (letters, numbers, underscores)
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                variables.add(var_name)
        
        return variables
    
    def get_prompt(self, name: str, variables: Dict[str, str] = None) -> str:
        """
        Get a prompt by name and optionally substitute template variables.
        
        Args:
            name (str): Name of the prompt (filename without .md)
            variables (Dict[str, str], optional): Dictionary of variable substitutions
            
        Returns:
            str: The prompt content with variables substituted if provided
            
        Raises:
            KeyError: If prompt name doesn't exist
            ValueError: If required variables are missing or extra variables provided
        """
        if name not in self.prompts:
            available = list(self.prompts.keys())
            raise KeyError(f"Prompt '{name}' not found. Available prompts: {available}")
        
        template = self.prompts[name]
        required_vars = self._template_vars[name]
        
        # If no variables needed and none provided, return as-is
        if not required_vars and not variables:
            return template
        
        # If variables are needed but none provided
        if required_vars and not variables:
            raise ValueError(f"Prompt '{name}' requires variables: {sorted(required_vars)}")
        
        # If no variables needed but some provided
        if not required_vars and variables:
            raise ValueError(f"Prompt '{name}' doesn't accept variables, but got: {sorted(variables.keys())}")
        
        # Validate provided variables
        if variables:
            provided_vars = set(variables.keys())
            missing_vars = required_vars - provided_vars
            extra_vars = provided_vars - required_vars
            
            if missing_vars:
                raise ValueError(f"Missing required variables for prompt '{name}': {sorted(missing_vars)}")
            
            if extra_vars:
                raise ValueError(f"Extra variables provided for prompt '{name}': {sorted(extra_vars)}")
        
        # Substitute variables using format()
        try:
            return template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Template substitution failed for prompt '{name}': {e}")
        except Exception as e:
            raise ValueError(f"Error formatting prompt '{name}': {e}")
    
    def get_prompt_variables(self, name: str) -> List[str]:
        """
        Get the list of variables required by a specific prompt.
        
        Args:
            name (str): Name of the prompt
            
        Returns:
            List[str]: Sorted list of variable names required by the prompt
            
        Raises:
            KeyError: If prompt name doesn't exist
        """
        if name not in self.prompts:
            available = list(self.prompts.keys())
            raise KeyError(f"Prompt '{name}' not found. Available prompts: {available}")
        
        return sorted(self._template_vars[name])
    
    def list_prompts(self) -> List[str]:
        """
        Get a list of all available prompt names.
        
        Returns:
            List[str]: Sorted list of prompt names
        """
        return sorted(self.prompts.keys())
    
    def has_prompt(self, name: str) -> bool:
        """
        Check if a prompt exists.
        
        Args:
            name (str): Name of the prompt
            
        Returns:
            bool: True if prompt exists, False otherwise
        """
        return name in self.prompts
    
    def get_raw_prompt(self, name: str) -> str:
        """
        Get the raw prompt content without any variable substitution.
        
        Args:
            name (str): Name of the prompt
            
        Returns:
            str: Raw prompt content
            
        Raises:
            KeyError: If prompt name doesn't exist
        """
        if name not in self.prompts:
            available = list(self.prompts.keys())
            raise KeyError(f"Prompt '{name}' not found. Available prompts: {available}")
        
        return self.prompts[name]
    
    def reload(self) -> None:
        """Reload all prompts from the directory."""
        self.load_prompts()
    
    def __repr__(self) -> str:
        """String representation of the PromptManager."""
        return f"PromptManager(prompts_dir='{self.prompts_dir}', prompts={len(self.prompts)})"
    
    def __len__(self) -> int:
        """Return the number of loaded prompts."""
        return len(self.prompts)


# Note: For comprehensive testing and examples, see PromptManagerTests.py