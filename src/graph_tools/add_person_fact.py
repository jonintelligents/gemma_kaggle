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
        # First check if person exists, if not create them
        person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
        if not person_check.single():
            # Create the person if they don't exist
            session.run("""
                CREATE (p:Person {
                    name: $person_id,
                    created_at: $created_at
                })
            """, person_id=person_id, created_at=datetime.now().isoformat())
            logger.info(f"Created new person: {person_id}")
        
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
        
        # Handle inter-person relationships - ENHANCED VERSION
        for potential_name in potential_person_names:
            # ENHANCED: Find ALL existing persons with this name (to handle multiple nodes with same name)
            existing_persons_query = """
            MATCH (other:Person {name: $potential_name})
            RETURN other.name as name, id(other) as node_id
            """
            
            existing_persons = session.run(existing_persons_query, potential_name=potential_name).data()
            
            if not existing_persons:
                # Create the new person if none exist
                session.run("""
                    CREATE (p:Person {
                        name: $potential_name,
                        created_at: $created_at
                    })
                """, potential_name=potential_name, created_at=datetime.now().isoformat())
                logger.info(f"Created new person from relationship: {potential_name}")
                
                # Add to list for relationship creation
                existing_persons = [{'name': potential_name, 'node_id': None}]
            
            # Determine relationship type
            relationship_type = _determine_relationship_type(fact_text, potential_name)
            
            # ENHANCED: Create relationships with ALL existing persons with this name
            connections_made = 0
            for person_record in existing_persons:
                # Create bidirectional relationship (MERGE prevents duplicates)
                create_relationship_query = """
                MATCH (p1:Person {name: $person_id})
                MATCH (p2:Person {name: $other_person})
                MERGE (p1)-[r1:RELATED_TO {relationship_type: $relationship_type}]->(p2)
                ON CREATE SET r1.via_fact = $fact_id, r1.created_at = $created_at
                ON MATCH SET r1.last_confirmed = $created_at
                MERGE (p2)-[r2:RELATED_TO {relationship_type: $relationship_type}]->(p1)
                ON CREATE SET r2.via_fact = $fact_id, r2.created_at = $created_at
                ON MATCH SET r2.last_confirmed = $created_at
                RETURN p2.name as connected_person
                """
                
                result = session.run(create_relationship_query,
                                    person_id=person_id,
                                    other_person=potential_name,
                                    relationship_type=relationship_type,
                                    fact_id=fact_id,
                                    created_at=datetime.now().isoformat())
                
                if result.single():
                    connections_made += 1
            
            # Report connections made
            if connections_made > 0:
                status = "[existing]" if len(existing_persons) > 0 and existing_persons[0]['node_id'] is not None else "[new]"
                connection_info = f"{potential_name} ({relationship_type}) {status}"
                if connections_made > 1:
                    connection_info += f" [{connections_made} nodes]"
                people_connected.append(connection_info)
        
        # SPECIAL HANDLING: If fact is just a relationship type (like "best friend") 
        # and no person names were extracted, look for recent similar facts
        if (not potential_person_names and 
            fact_type == "relationship" and 
            any(rel_word in fact_text.lower() for rel_word in ['friend', 'colleague', 'married', 'spouse', 'sibling', 'brother', 'sister'])):
            
            # Look for other people who have the same relationship fact added recently (within last minute)
            similar_facts_query = """
            MATCH (other:Person)-[:HAS_FACT]->(f:Fact)
            WHERE f.text = $fact_text 
            AND f.type = $fact_type
            AND other.name <> $person_id
            AND datetime(f.created_at) >= datetime($recent_time)
            RETURN other.name as other_person, f.created_at as fact_time
            ORDER BY f.created_at DESC
            LIMIT 5
            """
            
            recent_time = datetime.now().replace(second=0, microsecond=0).isoformat()  # Last minute
            
            similar_facts = session.run(similar_facts_query,
                                      fact_text=fact_text,
                                      fact_type=fact_type,
                                      person_id=person_id,
                                      recent_time=recent_time).data()
            
            # Connect to people with matching relationship facts
            for fact_record in similar_facts:
                other_person = fact_record['other_person']
                relationship_type = _determine_relationship_type(fact_text)
                
                # ENHANCED: Find all persons with this name and connect to all of them
                all_matching_persons_query = """
                MATCH (other:Person {name: $other_person})
                RETURN other.name as name, id(other) as node_id
                """
                
                all_matching = session.run(all_matching_persons_query, other_person=other_person).data()
                
                connections_made = 0
                for person_match in all_matching:
                    # Create bidirectional relationship
                    auto_relationship_query = """
                    MATCH (p1:Person {name: $person_id})
                    MATCH (p2:Person {name: $other_person})
                    WHERE id(p2) = $target_node_id
                    MERGE (p1)-[r1:RELATED_TO {relationship_type: $relationship_type}]->(p2)
                    ON CREATE SET r1.via_fact = $fact_id, r1.created_at = $created_at, r1.auto_detected = true
                    ON MATCH SET r1.last_confirmed = $created_at
                    MERGE (p2)-[r2:RELATED_TO {relationship_type: $relationship_type}]->(p1)
                    ON CREATE SET r2.via_fact = $fact_id, r2.created_at = $created_at, r2.auto_detected = true
                    ON MATCH SET r2.last_confirmed = $created_at
                    RETURN p2.name as connected_person
                    """
                    
                    result = session.run(auto_relationship_query,
                                        person_id=person_id,
                                        other_person=other_person,
                                        target_node_id=person_match['node_id'],
                                        relationship_type=relationship_type,
                                        fact_id=fact_id,
                                        created_at=datetime.now().isoformat())
                    
                    if result.single():
                        connections_made += 1
                
                if connections_made > 0:
                    connection_info = f"{other_person} ({relationship_type}) [auto-detected]"
                    if connections_made > 1:
                        connection_info += f" [{connections_made} nodes]"
                    people_connected.append(connection_info)
                    logger.info(f"Auto-detected relationship: {person_id} -> {other_person} ({relationship_type}) - {connections_made} connections")
        
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
    
def _determine_relationship_type(fact_text: str, other_person: str = None) -> str:
    """
    Determine the type of relationship based on fact text.
    Enhanced to look for context around the specific person name.
    """
    fact_lower = fact_text.lower()
    
    # If we have the other person's name, look for context around it
    if other_person:
        other_lower = other_person.lower()
        # Create patterns that look for relationship words near the person's name
        person_context_patterns = [
            f"married to {other_lower}",
            f"{other_lower} is my (?:husband|wife|spouse)",
            f"my (?:husband|wife|spouse) {other_lower}",
            f"friends with {other_lower}",
            f"{other_lower} is my friend",
            f"my friend {other_lower}",
            f"brother {other_lower}",
            f"sister {other_lower}",
            f"{other_lower} is my (?:brother|sister)",
            f"colleague {other_lower}",
            f"works with {other_lower}",
            f"{other_lower} (?:works|worked) with",
        ]
        
        for pattern in person_context_patterns:
            if re.search(pattern, fact_lower):
                if any(word in pattern for word in ['married', 'husband', 'wife', 'spouse']):
                    return 'SPOUSE'
                elif any(word in pattern for word in ['friend']):
                    return 'FRIEND'
                elif any(word in pattern for word in ['brother', 'sister']):
                    return 'SIBLING'
                elif any(word in pattern for word in ['colleague', 'works']):
                    return 'COLLEAGUE'
    
    # Fall back to general pattern matching
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
    Enhanced with more comprehensive patterns and smart relationship detection.
    """
    # Enhanced relationship patterns that suggest person names
    relationship_patterns = [
        # Direct relationship statements
        r'\b(?:married to|husband|wife|spouse|partner)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:friend|friends with|buddy)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:brother|sister|sibling|cousin|uncle|aunt|nephew|niece)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:works with|colleague|coworker|boss|manager)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\b(?:son|daughter|child|parent|father|mother|dad|mom)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        
        # Reverse patterns
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|are)\s+(?:my|his|her)\s+(?:friend|brother|sister|spouse|husband|wife|boss|colleague)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:and I|and me)\s+are\s+(?:friends|married|dating|siblings|colleagues)',
        
        # Context-based patterns
        r'\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\band\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:are|is|were|was)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|are|was|were)\s+(?:a\s+)?(?:friend|colleague|neighbor)',
        
        # Meeting/activity patterns
        r'\bmet\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\bsaw\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\bvisited\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\bcalled\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\btalked to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        
        # Simple name mentions in relational context
        r'(?:me and|I and)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:and I|and me)',
        
        # Pattern for "X and Y are [relationship]" format
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+and\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:are|were)\s+(?:best\s+)?(?:friends|buddies|colleagues|married|dating|siblings)',
    ]
    
    potential_names = []
    for pattern in relationship_patterns:
        matches = re.findall(pattern, fact_text)
        for match in matches:
            if isinstance(match, tuple):
                # Handle multiple groups in regex
                for name in match:
                    if name and name.strip():
                        potential_names.append(name.strip())
            else:
                name = match.strip()
                if name:
                    potential_names.append(name)
    
    # Filter and clean the names
    filtered_names = []
    for name in potential_names:
        # Enhanced filtering
        if (name.lower() != current_person.lower() and 
            len(name.split()) <= 3 and  # Reasonable name length
            len(name) > 1 and  # Not single characters
            not any(word.lower() in ['the', 'and', 'or', 'with', 'in', 'at', 'on', 'is', 'are', 'was', 'were', 'my', 'his', 'her'] for word in name.split()) and
            not name.lower() in ['today', 'yesterday', 'tomorrow', 'morning', 'evening', 'night', 'day']):  # Avoid time words
            filtered_names.append(name)
    
    return list(set(filtered_names))  # Remove duplicates