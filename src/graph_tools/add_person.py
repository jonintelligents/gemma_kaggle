from datetime import datetime
from typing import Any, Dict
import json
from sentence_transformers import SentenceTransformer

 # Initialize the sentence transformer model for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2

def run(driver, name: str, properties: Dict[str, Any] = None) -> str:
    """Add or update a person node in the graph."""
    with driver.session() as session:
        # Prepare properties - flatten any nested dictionaries
        props = _flatten_properties(properties or {})
        props.update({
            'name': name,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        
        # Create the base query
        query = """
        MERGE (p:Person {name: $name})
        ON CREATE SET p = $props
        ON MATCH SET p += $props, p.updated_at = $updated_at
        RETURN p.name as name, p.created_at as created_at
        """
        
        result = session.run(query, name=name, props=props, updated_at=props['updated_at'])
        record = result.single()
        
        if record:
            return f"Person '{record['name']}' added/updated successfully"
        else:
            return f"Failed to add/update person '{name}'"
        
def _flatten_properties(properties: Dict[str, Any], prefix: str = "", separator: str = "_") -> Dict[str, Any]:
        """
        Flatten nested dictionaries into a single level with prefixed keys.
        
        Args:
            properties: Dictionary that may contain nested dictionaries
            prefix: Prefix to add to keys
            separator: Separator between prefix and key
            
        Returns:
            Flattened dictionary with all values as primitive types
        """
        flattened = {}
        
        for key, value in properties.items():
            # Create the new key with prefix if provided
            new_key = f"{prefix}{separator}{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                nested_flattened = _flatten_properties(value, new_key, separator)
                flattened.update(nested_flattened)
            elif isinstance(value, (list, tuple)):
                # Convert lists/tuples to strings or handle as needed
                if all(isinstance(item, (str, int, float, bool)) for item in value):
                    # If all items are primitive types, join them as a string
                    flattened[new_key] = ", ".join(str(item) for item in value)
                else:
                    # If list contains complex objects, convert to JSON string
                    flattened[new_key] = json.dumps(value, default=str)
            elif value is None:
                # Handle None values
                flattened[new_key] = ""
            elif isinstance(value, (str, int, float, bool)):
                # Primitive types - store as-is
                flattened[new_key] = value
            else:
                # Other types - convert to string representation
                flattened[new_key] = str(value)
        
        return flattened