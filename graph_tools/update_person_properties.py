
from AbstractToolManager import AbstractPersonToolManager
from typing import Any, Dict, List, Optional, Tuple
from EntityKeywordExtractor import EntityExtractor
from neo4j import GraphDatabase
import json
import uuid
from datetime import datetime
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging

def run(driver, person_id: str, properties: Dict[str, Any]) -> str:
    """Update properties for an existing person."""
    with driver.session() as session:
        # Check if person exists
        person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
        if not person_check.single():
            return f"Error: Person '{person_id}' not found"
        
        # Flatten the properties
        flattened_props = _flatten_properties(properties)
        flattened_props['updated_at'] = datetime.now().isoformat()
        
        query = """
        MATCH (p:Person {name: $person_id})
        SET p += $props
        RETURN p.name as name, keys(p) as properties
        """
        
        result = session.run(query, person_id=person_id, props=flattened_props)
        record = result.single()
        
        if record:
            return f"Updated properties for person '{record['name']}'. Properties: {record['properties']}"
        else:
            return f"Failed to update properties for person '{person_id}'"
        
def _flatten_properties(self, properties: Dict[str, Any], prefix: str = "", separator: str = "_") -> Dict[str, Any]:
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
                nested_flattened = self._flatten_properties(value, new_key, separator)
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