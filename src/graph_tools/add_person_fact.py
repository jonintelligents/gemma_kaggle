import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from EntityKeywordExtractor import EntityExtractor
from sentence_transformers import SentenceTransformer
import logging
import re

 # Initialize the sentence transformer model for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2
logger = logging.getLogger(__name__)

extractor = EntityExtractor()

def run(driver, person_id: str, fact_text: str, fact_type: str = "general") -> str:
    """Add a fact node with embedding, extract entities, and create inter-person relationships."""
    with driver.session() as session:
        # First check if person exists
        person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
        if not person_check.single():
            return f"Error: Person '{person_id}' not found"
        
        # Generate embedding for the fact text
        embedding = _get_text_embedding(fact_text)
        
        # Extract entities from the fact text
        extraction_result = extractor.extract(fact_text, extract_key_terms=False)
        
        # Extract potential person names from the fact
        potential_person_names = _extract_person_names_from_fact(fact_text, person_id)
        
        # Generate unique fact ID
        fact_id = str(uuid.uuid4())
        
        # Create fact node with embedding
        fact_query = """
        MATCH (p:Person {name: $person_id})
        CREATE (f:Fact {
            id: $fact_id,
            text: $fact_text,
            type: $fact_type,
            embedding: $embedding,
            created_at: $created_at
        })
        CREATE (p)-[:HAS_FACT]->(f)
        RETURN f.id as fact_id
        """
        
        session.run(fact_query, 
                    person_id=person_id,
                    fact_id=fact_id,
                    fact_text=fact_text,
                    fact_type=fact_type,
                    embedding=embedding,
                    created_at=datetime.now().isoformat())
        
        # Track what was created/connected
        entities_connected = []
        people_connected = []
        
        # Handle entity extraction and connection to existing entities
        if extraction_result and 'entities' in extraction_result:
            for entity_info in extraction_result['entities']:
                entity_name = entity_info.get('text', '').strip()
                entity_type = entity_info.get('label', 'UNKNOWN')
                
                if entity_name:
                    # Check if entity already exists
                    existing_entity_query = """
                    MATCH (e:Entity {name: $entity_name, type: $entity_type})
                    RETURN e
                    """
                    existing_entity = session.run(existing_entity_query, 
                                                entity_name=entity_name, 
                                                entity_type=entity_type).single()
                    
                    if existing_entity:
                        # Connect to existing entity (only if not already connected)
                        connect_query = """
                        MATCH (p:Person {name: $person_id})
                        MATCH (e:Entity {name: $entity_name, type: $entity_type})
                        MERGE (p)-[:CONNECTED_TO {via_fact: $fact_id}]->(e)
                        RETURN e.name as entity_name, e.type as entity_type
                        """
                        result = session.run(connect_query,
                                            person_id=person_id,
                                            entity_name=entity_name,
                                            entity_type=entity_type,
                                            fact_id=fact_id)
                        
                        if result.single():
                            entities_connected.append(f"{entity_name} ({entity_type}) [existing]")
                    else:
                        # Create new entity and connect
                        create_entity_query = """
                        MATCH (p:Person {name: $person_id})
                        CREATE (e:Entity {name: $entity_name, type: $entity_type, created_at: $created_at})
                        CREATE (p)-[:CONNECTED_TO {via_fact: $fact_id}]->(e)
                        RETURN e.name as entity_name, e.type as entity_type
                        """
                        
                        result = session.run(create_entity_query,
                                            person_id=person_id,
                                            entity_name=entity_name,
                                            entity_type=entity_type,
                                            fact_id=fact_id,
                                            created_at=datetime.now().isoformat())
                        
                        if result.single():
                            entities_connected.append(f"{entity_name} ({entity_type}) [new]")
        
        # Handle inter-person relationships
        for potential_name in potential_person_names:
            # Check if this person exists in the graph
            person_exists_query = """
            MATCH (other:Person {name: $potential_name})
            RETURN other.name as name
            """
            
            existing_person = session.run(person_exists_query, potential_name=potential_name).single()
            
            if existing_person:
                # Determine relationship type
                relationship_type = _determine_relationship_type(fact_text)
                
                # Create bidirectional relationship (only if not already exists)
                create_relationship_query = """
                MATCH (p1:Person {name: $person_id})
                MATCH (p2:Person {name: $other_person})
                MERGE (p1)-[:RELATED_TO {
                    relationship_type: $relationship_type,
                    via_fact: $fact_id,
                    created_at: $created_at
                }]->(p2)
                MERGE (p2)-[:RELATED_TO {
                    relationship_type: $relationship_type,
                    via_fact: $fact_id,
                    created_at: $created_at
                }]->(p1)
                RETURN p2.name as connected_person
                """
                
                result = session.run(create_relationship_query,
                                    person_id=person_id,
                                    other_person=potential_name,
                                    relationship_type=relationship_type,
                                    fact_id=fact_id,
                                    created_at=datetime.now().isoformat())
                
                if result.single():
                    people_connected.append(f"{potential_name} ({relationship_type})")
        
        # Format response
        response = f"Added {fact_type} fact to person '{person_id}': {fact_text}"
        
        if entities_connected:
            response += f"\nConnected to entities: {', '.join(entities_connected)}"
        
        if people_connected:
            response += f"\nConnected to people: {', '.join(people_connected)}"
        
        return response

def _get_text_embedding(text: str) -> List[float]:
    """Generate embedding vector for given text."""
    try:
        embedding = embedding_model.encode([text])[0]
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return [0.0] * embedding_dimension
    
def _determine_relationship_type(fact_text: str) -> str:
    """
    Determine the type of relationship based on fact text.
    """
    fact_lower = fact_text.lower()
    
    # Family relationships
    if any(word in fact_lower for word in ['married', 'husband', 'wife', 'spouse']):
        return 'SPOUSE'
    elif any(word in fact_lower for word in ['brother', 'sister', 'sibling']):
        return 'SIBLING'
    elif any(word in fact_lower for word in ['parent', 'father', 'mother', 'dad', 'mom']):
        return 'PARENT'
    elif any(word in fact_lower for word in ['son', 'daughter', 'child']):
        return 'CHILD'
    elif any(word in fact_lower for word in ['cousin', 'uncle', 'aunt', 'nephew', 'niece']):
        return 'FAMILY'
    
    # Professional relationships
    elif any(word in fact_lower for word in ['colleague', 'coworker', 'works with']):
        return 'COLLEAGUE'
    elif any(word in fact_lower for word in ['boss', 'manager', 'supervisor']):
        return 'PROFESSIONAL'
    
    # Social relationships
    elif any(word in fact_lower for word in ['friend', 'buddy']):
        return 'FRIEND'
    elif any(word in fact_lower for word in ['dating', 'girlfriend', 'boyfriend']):
        return 'ROMANTIC'
    
    # Default
    else:
        return 'RELATED'
    
def _extract_person_names_from_fact(fact_text: str, current_person: str) -> List[str]:
    """
    Extract potential person names from fact text.
    This is a simple implementation - you may want to enhance with NLP.
    """
    # Common relationship indicators that suggest person names
    relationship_patterns = [
        r'\b(?:married to|husband|wife|spouse|partner)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:friend|brother|sister|sibling|cousin|uncle|aunt|nephew|niece)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:works with|colleague|boss|manager)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:son|daughter|child|parent|father|mother|dad|mom)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|are)\s+(?:my|his|her)\s+(?:friend|brother|sister|spouse|husband|wife)',
        r'with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'and\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+are\s+(?:married|dating|friends|siblings)'
    ]
    
    potential_names = []
    for pattern in relationship_patterns:
        matches = re.findall(pattern, fact_text, re.IGNORECASE)
        for match in matches:
            name = match.strip()
            # Avoid matching the current person and common non-names
            if (name.lower() != current_person.lower() and 
                len(name.split()) <= 3 and  # Reasonable name length
                not any(word.lower() in ['the', 'and', 'or', 'with', 'in', 'at', 'on'] for word in name.split())):
                potential_names.append(name)
    
    return list(set(potential_names))  # Remove duplicates