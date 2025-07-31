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

class GraphPersonManager(AbstractPersonToolManager):
    """
    Neo4j-based implementation of the AbstractPersonToolManager with vector search capabilities.
    
    Graph Structure:
    - Person nodes: Core individuals in the network
    - Entity nodes: Places, organizations, interests, etc. extracted from facts
    - Fact nodes: Individual pieces of information about people (now with vector embeddings)
    - Relationships: Connect people to entities, facts, and other people
    
    Enhanced Features:
    - Creates direct relationships between people mentioned in facts
    - Connects people to existing entities in the graph
    - Avoids duplicate relationships
    - Vector search using sentence transformers for semantic similarity
    - Full-text search on fact content
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        super().__init__()
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.extractor = EntityExtractor()
        
        # Initialize the sentence transformer model for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self._create_constraints()
        self._create_vector_index()
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def _create_constraints(self):
        """Create unique constraints and indexes for better performance."""
        with self.driver.session() as session:
            # Create unique constraints
            constraints = [
                "CREATE CONSTRAINT person_name_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
                "CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE",
                "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    # Constraint might already exist
                    pass
            
            # Create indexes for better search performance
            indexes = [
                "CREATE INDEX person_name_index IF NOT EXISTS FOR (p:Person) ON (p.name)",
                "CREATE INDEX fact_type_index IF NOT EXISTS FOR (f:Fact) ON (f.type)",
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE FULLTEXT INDEX fact_text_fulltext IF NOT EXISTS FOR (f:Fact) ON (f.text)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    # Index might already exist
                    pass

    def _create_vector_index(self):
        """Create vector index for fact embeddings."""
        with self.driver.session() as session:
            try:
                # Create vector index for fact embeddings
                vector_index_query = f"""
                CREATE VECTOR INDEX fact_embeddings IF NOT EXISTS
                FOR (f:Fact) ON (f.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {self.embedding_dimension},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
                """
                session.run(vector_index_query)
                self.logger.info("Vector index created/verified for fact embeddings")
            except Exception as e:
                self.logger.warning(f"Could not create vector index: {e}")
                # Neo4j might not support vector indexes in this version

    def _get_text_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for given text."""
        try:
            embedding = self.embedding_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return [0.0] * self.embedding_dimension

    def update_person_properties(self, person_id: str, properties: Dict[str, Any]) -> str:
        """Update properties for an existing person."""
        with self.driver.session() as session:
            # Check if person exists
            person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
            if not person_check.single():
                return f"Error: Person '{person_id}' not found"
            
            # Flatten the properties
            flattened_props = self._flatten_properties(properties)
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

    def get_person_properties(self, person_id: str) -> str:
        """Get all properties for a specific person."""
        with self.driver.session() as session:
            query = """
            MATCH (p:Person {name: $person_id})
            RETURN properties(p) as props
            """
            
            result = session.run(query, person_id=person_id)
            record = result.single()
            
            if record:
                props = dict(record['props'])
                return f"Properties for person '{person_id}': {json.dumps(props, indent=2, default=str)}"
            else:
                return f"Person '{person_id}' not found"
    
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
    
    def add_person(self, name: str, properties: Dict[str, Any] = None) -> str:
        """Add or update a person node in the graph."""
        with self.driver.session() as session:
            # Prepare properties - flatten any nested dictionaries
            props = self._flatten_properties(properties or {})
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
    
    def get_all_people(self, include_relationships: bool = True) -> str:
        """Retrieve all people from the graph with their complete information."""
        with self.driver.session() as session:
            if include_relationships:
                query = """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[:HAS_FACT]->(f:Fact)
                OPTIONAL MATCH (p)-[:CONNECTED_TO]->(e:Entity)
                OPTIONAL MATCH (p)-[:RELATED_TO]->(other:Person)
                WITH p, 
                    collect(DISTINCT {
                        id: f.id, 
                        text: f.text, 
                        type: f.type, 
                        created_at: f.created_at
                    }) as facts,
                    collect(DISTINCT {
                        name: e.name, 
                        type: e.type, 
                        created_at: e.created_at
                    }) as entities,
                    collect(DISTINCT {
                        name: other.name, 
                        relationship_type: 'RELATED_TO'
                    }) as related_people
                RETURN p.name as name,
                    properties(p) as person_properties,
                    facts,
                    entities,
                    related_people
                ORDER BY p.name
                """
            else:
                query = """
                MATCH (p:Person)
                RETURN p.name as name,
                    properties(p) as person_properties
                ORDER BY p.name
                """
            
            result = session.run(query)
            people = []
            
            for record in result:
                # Get all person properties
                person_properties = dict(record['person_properties'])
                
                person_info = {
                    'name': record['name'],
                    'properties': person_properties
                }
                
                if include_relationships:
                    # Filter out empty facts and include all fact details
                    # Note: Need to filter out facts where text is None (empty OPTIONAL MATCH results)
                    raw_facts = record.get('facts', [])
                    facts = [f for f in raw_facts if f.get('text') is not None and f.get('id') is not None]
                    person_info['facts'] = facts
                    
                    # Filter out empty entities and include all entity details
                    raw_entities = record.get('entities', [])
                    entities = [e for e in raw_entities if e.get('name') is not None]
                    person_info['entities'] = entities
                    
                    # Filter out empty related people
                    raw_related = record.get('related_people', [])
                    related_people = [r for r in raw_related if r.get('name') is not None]
                    person_info['related_people'] = related_people
                    
                    # Add summary counts for quick reference
                    person_info['summary_counts'] = {
                        'total_facts': len(facts),
                        'total_entities': len(entities),
                        'total_connections': len(related_people)
                    }
                
                people.append(person_info)
            
            if people:
                if include_relationships:
                    total_facts = sum(person.get('summary_counts', {}).get('total_facts', 0) for person in people)
                    total_entities = sum(person.get('summary_counts', {}).get('total_entities', 0) for person in people)
                    total_connections = sum(person.get('summary_counts', {}).get('total_connections', 0) for person in people)
                    
                    summary = f"Retrieved {len(people)} people with {total_facts} total facts, {total_entities} total entities, and {total_connections} total connections."
                else:
                    summary = f"Retrieved {len(people)} people."
                
                return f"{summary}\n\nPeople data: {json.dumps(people, indent=2, default=str)}"
            else:
                return "No people found in the database"
    
    def get_person(self, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
        """Retrieve specific person(s) from the graph."""
        with self.driver.session() as session:
            if name:
                # Support partial name matching
                base_query = "MATCH (p:Person) WHERE p.name CONTAINS $name"
                params = {'name': name}
            elif person_id:
                base_query = "MATCH (p:Person) WHERE p.name = $person_id"
                params = {'person_id': person_id}
            else:
                return self.get_all_people(include_relationships)
            
            if include_relationships:
                query = f"""
                {base_query}
                OPTIONAL MATCH (p)-[r:HAS_FACT]->(f:Fact)
                OPTIONAL MATCH (p)-[er:CONNECTED_TO]->(e:Entity)
                OPTIONAL MATCH (p)-[pr:RELATED_TO]->(other:Person)
                RETURN p.name as name, 
                       p.summary as summary,
                       collect(DISTINCT {{id: f.id, text: f.text, type: f.type}}) as facts,
                       collect(DISTINCT {{name: e.name, type: e.type}}) as entities,
                       collect(DISTINCT {{name: other.name, relationship: pr.relationship_type}}) as related_people
                ORDER BY p.name
                """
            else:
                query = f"""
                {base_query}
                RETURN p.name as name, p.summary as summary
                ORDER BY p.name
                """
            
            result = session.run(query, **params)
            people = []
            
            for record in result:
                person_info = {
                    'name': record['name'],
                    'summary': record.get('summary', '')
                }
                
                if include_relationships:
                    # Filter out empty facts and entities
                    facts = [f for f in record.get('facts', []) if f.get('text')]
                    entities = [e for e in record.get('entities', []) if e.get('name')]
                    related_people = [r for r in record.get('related_people', []) if r.get('name')]
                    
                    if facts:
                        person_info['facts'] = facts
                    if entities:
                        person_info['entities'] = entities
                    if related_people:
                        person_info['related_people'] = related_people
                
                people.append(person_info)
            
            if people:
                return f"Found {len(people)} person(s): {json.dumps(people, indent=2)}"
            else:
                return f"No person found matching the criteria"
    
    def delete_person(self, person_id: str = None, name: str = None) -> str:
        """Delete a person and all their relationships from the graph."""
        identifier = person_id or name
        if not identifier:
            return "Error: Must provide either person_id or name"
        
        with self.driver.session() as session:
            query = """
            MATCH (p:Person {name: $identifier})
            OPTIONAL MATCH (p)-[r]-()
            DELETE r, p
            RETURN count(p) as deleted_count
            """
            
            result = session.run(query, identifier=identifier)
            record = result.single()
            
            if record and record['deleted_count'] > 0:
                return f"Successfully deleted person '{identifier}' and all relationships"
            else:
                return f"Person '{identifier}' not found"
    
    def _extract_person_names_from_fact(self, fact_text: str, current_person: str) -> List[str]:
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
    
    def _determine_relationship_type(self, fact_text: str) -> str:
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
    
    def add_person_fact(self, person_id: str, fact_text: str, fact_type: str = "general") -> str:
        """Add a fact node with embedding, extract entities, and create inter-person relationships."""
        with self.driver.session() as session:
            # First check if person exists
            person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
            if not person_check.single():
                return f"Error: Person '{person_id}' not found"
            
            # Generate embedding for the fact text
            embedding = self._get_text_embedding(fact_text)
            
            # Extract entities from the fact text
            extraction_result = self.extractor.extract(fact_text, extract_key_terms=False)
            
            # Extract potential person names from the fact
            potential_person_names = self._extract_person_names_from_fact(fact_text, person_id)
            
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
                    relationship_type = self._determine_relationship_type(fact_text)
                    
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

    def search_facts_vector(self, query_text: str, top_k: int = 5, similarity_threshold: float = 0.3) -> str:
        """
        Search for facts using vector similarity.
        
        Args:
            query_text: Text to search for
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            JSON string with search results
        """
        try:
            # Generate embedding for query text
            query_embedding = self._get_text_embedding(query_text)
            
            with self.driver.session() as session:
                # First, get all facts with embeddings
                get_facts_query = """
                MATCH (p:Person)-[:HAS_FACT]->(f:Fact)
                WHERE f.embedding IS NOT NULL
                RETURN p.name as person_name, f.id as fact_id, f.text as fact_text, 
                       f.type as fact_type, f.embedding as embedding, f.created_at as created_at
                """
                
                result = session.run(get_facts_query)
                facts = list(result)
                
                if not facts:
                    return "No facts with embeddings found in the database"
                
                # Calculate similarities
                similarities = []
                for record in facts:
                    fact_embedding = record['embedding']
                    if fact_embedding:
                        # Calculate cosine similarity
                        similarity = cosine_similarity(
                            [query_embedding], 
                            [fact_embedding]
                        )[0][0]
                        
                        if similarity >= similarity_threshold:
                            similarities.append({
                                'person_name': record['person_name'],
                                'fact_id': record['fact_id'],
                                'fact_text': record['fact_text'],
                                'fact_type': record['fact_type'],
                                'created_at': record['created_at'],
                                'similarity_score': float(similarity)
                            })
                
                # Sort by similarity score (descending) and take top_k
                similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
                top_results = similarities[:top_k]
                
                search_summary = {
                    'query': query_text,
                    'total_facts_searched': len(facts),
                    'facts_above_threshold': len(similarities),
                    'top_results_returned': len(top_results),
                    'similarity_threshold': similarity_threshold,
                    'results': top_results
                }
                
                return f"Vector search results: {json.dumps(search_summary, indent=2, default=str)}"
                
        except Exception as e:
            return f"Error performing vector search: {str(e)}"

    def search_facts_text(self, query_text: str, person_name: str = None) -> str:
        """
        Search for facts using full-text search.
        
        Args:
            query_text: Text to search for
            person_name: Optional person name to filter results
            
        Returns:
            JSON string with search results
        """
        with self.driver.session() as session:
            try:
                if person_name:
                    # Search within specific person's facts
                    query = """
                    CALL db.index.fulltext.queryNodes('fact_text_fulltext', $query_text)
                    YIELD node, score
                    MATCH (p:Person {name: $person_name})-[:HAS_FACT]->(node)
                    RETURN p.name as person_name, node.id as fact_id, node.text as fact_text,
                           node.type as fact_type, node.created_at as created_at, score
                    ORDER BY score DESC
                    """
                    
                    result = session.run(query, query_text=query_text, person_name=person_name)
                else:
                    # Search across all facts
                    query = """
                    CALL db.index.fulltext.queryNodes('fact_text_fulltext', $query_text)
                    YIELD node, score
                    MATCH (p:Person)-[:HAS_FACT]->(node)
                    RETURN p.name as person_name, node.id as fact_id, node.text as fact_text,
                           node.type as fact_type, node.created_at as created_at, score
                    ORDER BY score DESC
                    """
                    
                    result = session.run(query, query_text=query_text)
                
                facts = []
                for record in result:
                    facts.append({
                        'person_name': record['person_name'],
                        'fact_id': record['fact_id'],
                        'fact_text': record['fact_text'],
                        'fact_type': record['fact_type'],
                        'created_at': record['created_at'],
                        'relevance_score': float(record['score'])
                    })
                
                search_summary = {
                    'query': query_text,
                    'person_filter': person_name,
                    'total_results': len(facts),
                    'results': facts
                }
                
                return f"Text search results: {json.dumps(search_summary, indent=2, default=str)}"
                
            except Exception as e:
                # Fallback to simple CONTAINS search if fulltext index not available
                self.logger.warning(f"Fulltext search failed, using fallback: {e}")
                return self._search_facts_text_fallback(query_text, person_name)

    def _search_facts_text_fallback(self, query_text: str, person_name: str = None) -> str:
        """
        Fallback text search using CONTAINS when fulltext index is not available.
        """
        with self.driver.session() as session:
            if person_name:
                query = """
                MATCH (p:Person {name: $person_name})-[:HAS_FACT]->(f:Fact)
                WHERE f.text CONTAINS $query_text
                RETURN p.name as person_name, f.id as fact_id, f.text as fact_text,
                       f.type as fact_type, f.created_at as created_at
                ORDER BY f.created_at DESC
                """
                result = session.run(query, query_text=query_text, person_name=person_name)
            else:
                query = """
                MATCH (p:Person)-[:HAS_FACT]->(f:Fact)
                WHERE f.text CONTAINS $query_text
                RETURN p.name as person_name, f.id as fact_id, f.text as fact_text,
                       f.type as fact_type, f.created_at as created_at
                ORDER BY f.created_at DESC
                """
                result = session.run(query, query_text=query_text)
            
            facts = []
            for record in result:
                facts.append({
                    'person_name': record['person_name'],
                    'fact_id': record['fact_id'],
                    'fact_text': record['fact_text'],
                    'fact_type': record['fact_type'],
                    'created_at': record['created_at']
                })
            
            search_summary = {
                'query': query_text,
                'person_filter': person_name,
                'total_results': len(facts),
                'search_method': 'fallback_contains',
                'results': facts
            }
            
            return f"Text search results (fallback): {json.dumps(search_summary, indent=2, default=str)}"

    def search_facts_hybrid(self, query_text: str, top_k: int = 10, 
                           vector_weight: float = 0.7, text_weight: float = 0.3,
                           similarity_threshold: float = 0.2) -> str:
        """
        Hybrid search combining vector similarity and text search.
        
        Args:
            query_text: Text to search for
            top_k: Number of top results to return
            vector_weight: Weight for vector similarity scores (0-1)
            text_weight: Weight for text search scores (0-1)
            similarity_threshold: Minimum vector similarity score
            
        Returns:
            JSON string with hybrid search results
        """
        try:
            # Get vector search results
            vector_results_str = self.search_facts_vector(query_text, top_k * 2, similarity_threshold)
            vector_data = json.loads(vector_results_str.replace("Vector search results: ", ""))
            
            # Get text search results
            text_results_str = self.search_facts_text(query_text)
            text_data = json.loads(text_results_str.replace("Text search results: ", "").replace("Text search results (fallback): ", ""))
            
            # Create lookup dictionaries
            vector_scores = {r['fact_id']: r['similarity_score'] for r in vector_data.get('results', [])}
            text_scores = {r['fact_id']: r.get('relevance_score', 1.0) for r in text_data.get('results', [])}
            
            # Combine all unique facts
            all_facts = {}
            
            # Add vector results
            for fact in vector_data.get('results', []):
                all_facts[fact['fact_id']] = fact
            
            # Add text results
            for fact in text_data.get('results', []):
                if fact['fact_id'] not in all_facts:
                    all_facts[fact['fact_id']] = fact
            
            # Calculate hybrid scores
            hybrid_results = []
            for fact_id, fact in all_facts.items():
                vector_score = vector_scores.get(fact_id, 0.0)
                text_score = min(text_scores.get(fact_id, 0.0), 1.0)  # Normalize text scores
                
                hybrid_score = (vector_weight * vector_score) + (text_weight * text_score)
                
                fact['hybrid_score'] = hybrid_score
                fact['vector_score'] = vector_score
                fact['text_score'] = text_score
                hybrid_results.append(fact)
            
            # Sort by hybrid score and take top_k
            hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
            top_results = hybrid_results[:top_k]
            
            search_summary = {
                'query': query_text,
                'search_type': 'hybrid',
                'vector_weight': vector_weight,
                'text_weight': text_weight,
                'similarity_threshold': similarity_threshold,
                'total_unique_facts': len(all_facts),
                'top_results_returned': len(top_results),
                'results': top_results
            }
            
            return f"Hybrid search results: {json.dumps(search_summary, indent=2, default=str)}"
            
        except Exception as e:
            return f"Error performing hybrid search: {str(e)}"

    def rebuild_all_embeddings(self) -> str:
        """
        Rebuild embeddings for all existing facts in the database.
        Useful when adding vector search to existing data.
        """
        with self.driver.session() as session:
            # Get all facts without embeddings
            query = """
            MATCH (f:Fact)
            WHERE f.embedding IS NULL OR size(f.embedding) = 0
            RETURN f.id as fact_id, f.text as fact_text
            """
            
            result = session.run(query)
            facts_to_update = list(result)
            
            if not facts_to_update:
                return "No facts need embedding updates"
            
            updated_count = 0
            failed_count = 0
            
            for record in facts_to_update:
                fact_id = record['fact_id']
                fact_text = record['fact_text']
                
                try:
                    # Generate embedding
                    embedding = self._get_text_embedding(fact_text)
                    
                    # Update the fact with embedding
                    update_query = """
                    MATCH (f:Fact {id: $fact_id})
                    SET f.embedding = $embedding, f.embedding_updated_at = $updated_at
                    RETURN f.id
                    """
                    
                    update_result = session.run(update_query, 
                                              fact_id=fact_id,
                                              embedding=embedding,
                                              updated_at=datetime.now().isoformat())
                    
                    if update_result.single():
                        updated_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to update embedding for fact {fact_id}: {e}")
                    failed_count += 1
            
            return f"Embedding rebuild complete. Updated: {updated_count}, Failed: {failed_count}"

    def delete_person_fact(self, person_id: str, fact_number: int) -> str:
        """Delete a specific fact by its position number."""
        with self.driver.session() as session:
            # Get facts ordered by creation date to determine fact_number
            get_facts_query = """
            MATCH (p:Person {name: $person_id})-[:HAS_FACT]->(f:Fact)
            RETURN f.id as fact_id, f.text as fact_text
            ORDER BY f.created_at
            """
            
            facts_result = session.run(get_facts_query, person_id=person_id)
            facts = list(facts_result)
            
            if fact_number < 1 or fact_number > len(facts):
                return f"Error: Fact number {fact_number} not found for person '{person_id}'. Available facts: 1-{len(facts)}"
            
            # Get the fact to delete (fact_number is 1-indexed)
            fact_to_delete = facts[fact_number - 1]
            fact_id = fact_to_delete['fact_id']
            
            # Delete the fact and its relationships
            delete_query = """
            MATCH (f:Fact {id: $fact_id})
            OPTIONAL MATCH (f)-[r]-()
            DELETE r, f
            RETURN count(f) as deleted_count
            """
            
            result = session.run(delete_query, fact_id=fact_id)
            record = result.single()
            
            if record and record['deleted_count'] > 0:
                return f"Deleted fact {fact_number} from person '{person_id}': {fact_to_delete['fact_text']}"
            else:
                return f"Failed to delete fact {fact_number} from person '{person_id}'"
    
    def delete_all_facts_for_person(self, person_id: str) -> str:
        """Delete all facts for a person while keeping the person node."""
        with self.driver.session() as session:
            query = """
            MATCH (p:Person {name: $person_id})-[:HAS_FACT]->(f:Fact)
            OPTIONAL MATCH (f)-[r]-()
            DELETE r, f
            RETURN count(f) as deleted_count
            """
            
            result = session.run(query, person_id=person_id)
            record = result.single()
            
            if record:
                count = record['deleted_count']
                return f"Deleted {count} facts from person '{person_id}'"
            else:
                return f"No facts found for person '{person_id}'"
    
    def get_facts_by_type(self, person_id: str = None, fact_type: str = None) -> str:
        """Retrieve facts filtered by person and/or type."""
        with self.driver.session() as session:
            # Build query based on parameters
            where_clauses = []
            params = {}
            
            if person_id:
                where_clauses.append("p.name = $person_id")
                params['person_id'] = person_id
            
            if fact_type:
                where_clauses.append("f.type = $fact_type")
                params['fact_type'] = fact_type
            
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            query = f"""
            MATCH (p:Person)-[:HAS_FACT]->(f:Fact)
            {where_clause}
            RETURN p.name as person_name, 
                   f.text as fact_text, 
                   f.type as fact_type,
                   f.created_at as created_at
            ORDER BY p.name, f.created_at
            """
            
            result = session.run(query, **params)
            facts = []
            
            for record in result:
                facts.append({
                    'person': record['person_name'],
                    'fact': record['fact_text'],
                    'type': record['fact_type'],
                    'created_at': record['created_at']
                })
            
            if facts:
                person_str = f" for person '{person_id}'" if person_id else " for all people"
                type_str = f" of type '{fact_type}'" if fact_type else " of all types"
                return f"Found {len(facts)} facts{type_str}{person_str}: {json.dumps(facts, indent=2)}"
            else:
                return "No facts found matching the criteria"
    
    def update_fact_type(self, person_id: str, fact_number: int, new_fact_type: str) -> str:
        """Update the type of a specific fact."""
        with self.driver.session() as session:
            # Get facts ordered by creation date to determine fact_number
            get_facts_query = """
            MATCH (p:Person {name: $person_id})-[:HAS_FACT]->(f:Fact)
            RETURN f.id as fact_id, f.text as fact_text, f.type as old_type
            ORDER BY f.created_at
            """
            
            facts_result = session.run(get_facts_query, person_id=person_id)
            facts = list(facts_result)
            
            if fact_number < 1 or fact_number > len(facts):
                return f"Error: Fact number {fact_number} not found for person '{person_id}'. Available facts: 1-{len(facts)}"
            
            # Get the fact to update (fact_number is 1-indexed)
            fact_to_update = facts[fact_number - 1]
            fact_id = fact_to_update['fact_id']
            old_type = fact_to_update['old_type']
            
            # Update the fact type
            update_query = """
            MATCH (f:Fact {id: $fact_id})
            SET f.type = $new_fact_type, f.updated_at = $updated_at
            RETURN f.text as fact_text
            """
            
            result = session.run(update_query, 
                               fact_id=fact_id,
                               new_fact_type=new_fact_type,
                               updated_at=datetime.now().isoformat())
            
            record = result.single()
            if record:
                return f"Updated fact {fact_number} type from '{old_type}' to '{new_fact_type}' for person '{person_id}': {record['fact_text']}"
            else:
                return f"Failed to update fact {fact_number} for person '{person_id}'"
    
    def get_graph_statistics(self) -> str:
        """Get statistics about the knowledge graph."""
        with self.driver.session() as session:
            stats_query = """
            MATCH (p:Person) 
            OPTIONAL MATCH (p)-[:HAS_FACT]->(f:Fact)
            OPTIONAL MATCH (p)-[:CONNECTED_TO]->(e:Entity)
            OPTIONAL MATCH (p)-[:RELATED_TO]->(other:Person)
            WITH 
                count(DISTINCT p) as person_count,
                count(DISTINCT f) as fact_count,
                count(DISTINCT e) as entity_count,
                count(DISTINCT other) as connected_people_count
            
            // Get embedding statistics
            OPTIONAL MATCH (f2:Fact)
            WHERE f2.embedding IS NOT NULL AND size(f2.embedding) > 0
            
            RETURN 
                person_count,
                fact_count,
                entity_count,
                connected_people_count,
                count(f2) as facts_with_embeddings
            """
            
            result = session.run(stats_query)
            record = result.single()
            
            if record:
                embedding_percentage = 0
                if record['fact_count'] > 0:
                    embedding_percentage = (record['facts_with_embeddings'] / record['fact_count']) * 100
                
                return f"""Graph Statistics:
    - People: {record['person_count']}
    - Facts: {record['fact_count']}
    - Facts with embeddings: {record['facts_with_embeddings']} ({embedding_percentage:.1f}%)
    - Entities: {record['entity_count']}
    - Inter-person connections: {record['connected_people_count']}"""
            else:
                return "No statistics available"

    def get_people_facts_simple(self) -> str:
        """Retrieve all people with just their names and fact texts in a simplified format."""
        with self.driver.session() as session:
            query = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:HAS_FACT]->(f:Fact)
            WITH p, collect(f.text) as fact_texts
            RETURN p.name as name, fact_texts
            ORDER BY p.name
            """
            
            result = session.run(query)
            people_facts = {}
            
            for record in result:
                name = record['name']
                fact_texts = record['fact_texts']
                
                # Filter out None values (from people with no facts)
                filtered_facts = [fact for fact in fact_texts if fact is not None]
                
                people_facts[name] = filtered_facts
            
            if people_facts:
                total_people = len(people_facts)
                total_facts = sum(len(facts) for facts in people_facts.values())
                summary = f"Retrieved {total_people} people with {total_facts} total facts."
                
                return f"{summary}\n\nPeople facts: {json.dumps(people_facts, indent=2, ensure_ascii=False)}"
            else:
                return "No people found in the database"

    def extract_people_facts_from_full_data(self) -> str:
        """Extract simplified people facts from the full get_all_people data."""
        # Get the full data first
        full_data_result = self.get_all_people(include_relationships=True)
        
        try:
            # Extract JSON part from the result string
            json_start = full_data_result.find('People data: ') + len('People data: ')
            json_data = full_data_result[json_start:]
            
            # Parse the JSON
            people_data = json.loads(json_data)
            
            # Extract just names and fact texts
            people_facts = {}
            for person in people_data:
                name = person['name']
                facts = person.get('facts', [])
                fact_texts = [fact['text'] for fact in facts if fact.get('text')]
                people_facts[name] = fact_texts
            
            total_people = len(people_facts)
            total_facts = sum(len(facts) for facts in people_facts.values())
            summary = f"Extracted {total_people} people with {total_facts} total facts."
            
            return f"{summary}\n\nPeople facts: {json.dumps(people_facts, indent=2, ensure_ascii=False)}"
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return f"Error processing data: {str(e)}"
        
    def convert_json_to_formatted_string(self, people_facts_json: dict) -> str:
        """
        Convert a JSON dictionary of people facts to formatted string.
        
        Args:
            people_facts_json: Dictionary with format {"Name": ["fact1", "fact2", ...]}
        
        Returns:
            String with each person on a new line in format "Name: fact1, fact2, fact3"
        """
        formatted_lines = []
        
        for name, facts in people_facts_json.items():
            # Join facts with commas
            facts_string = ", ".join(facts)
            
            # Format as "Name: facts"
            formatted_line = f"{name}: {facts_string}"
            formatted_lines.append(formatted_line)
        
        return "\n".join(formatted_lines)


if __name__ == "__main__":
    """
    Main method to demonstrate GraphPersonManager usage with search capabilities.
    """
    # Initialize the GraphPersonManager
    graph_manager = GraphPersonManager(
        uri="bolt://localhost:7687",
        user="neo4j", 
        password="password"  # Replace with your actual password
    )
    
    try:
        print("=" * 80)
        print("ENHANCED KNOWLEDGE GRAPH WITH VECTOR SEARCH")
        print("=" * 80)
        
        # Add some sample data for testing
        print("\n" + "=" * 50)
        print("ADDING SAMPLE DATA")
        print("=" * 50)
        
        # Add people
        print(graph_manager.add_person("Alice Johnson", {"age": 30, "location": "New York"}))
        print(graph_manager.add_person("Bob Smith", {"age": 25, "location": "California"}))
        print(graph_manager.add_person("Carol Davis", {"age": 35, "location": "Texas"}))
        
        # Add facts with different types
        print(graph_manager.add_person_fact("Alice Johnson", "Alice works as a software engineer at Google", "work"))
        print(graph_manager.add_person_fact("Alice Johnson", "Alice loves hiking in the mountains", "hobby"))
        print(graph_manager.add_person_fact("Alice Johnson", "Alice is married to Bob Smith", "relationship"))
        
        print(graph_manager.add_person_fact("Bob Smith", "Bob is a data scientist specializing in machine learning", "work"))
        print(graph_manager.add_person_fact("Bob Smith", "Bob enjoys playing guitar and composing music", "hobby"))
        print(graph_manager.add_person_fact("Bob Smith", "Bob and Alice went to college together", "relationship"))
        
        print(graph_manager.add_person_fact("Carol Davis", "Carol is a marketing manager at a tech startup", "work"))
        print(graph_manager.add_person_fact("Carol Davis", "Carol practices yoga and meditation daily", "hobby"))
        print(graph_manager.add_person_fact("Carol Davis", "Carol volunteers at the local animal shelter", "volunteer"))
        
        print("\n" + "=" * 50)
        print("GRAPH STATISTICS")
        print("=" * 50)
        
        print(graph_manager.get_graph_statistics())
        
        print("\n" + "=" * 50)
        print("REBUILDING EMBEDDINGS FOR EXISTING FACTS")
        print("=" * 50)
        
        print(graph_manager.rebuild_all_embeddings())
        
        print("\n" + "=" * 50)
        print("UPDATED GRAPH STATISTICS")
        print("=" * 50)
        
        print(graph_manager.get_graph_statistics())
        
        print("\n" + "=" * 50)
        print("TESTING VECTOR SEARCH")
        print("=" * 50)
        
        # Test vector searches
        print("🔍 Vector Search: 'programming and technology'")
        print(graph_manager.search_facts_vector("programming and technology", top_k=3))
        
        print("\n🔍 Vector Search: 'music and creative activities'")
        print(graph_manager.search_facts_vector("music and creative activities", top_k=3))
        
        print("\n🔍 Vector Search: 'physical fitness and exercise'")
        print(graph_manager.search_facts_vector("physical fitness and exercise", top_k=3))
        
        print("\n" + "=" * 50)
        print("TESTING TEXT SEARCH")
        print("=" * 50)
        
        # Test text searches
        print("🔍 Text Search: 'Google'")
        print(graph_manager.search_facts_text("Google"))
        
        print("\n🔍 Text Search: 'music' (for Bob Smith)")
        print(graph_manager.search_facts_text("music", person_name="Bob Smith"))
        
        print("\n🔍 Text Search: 'married'")
        print(graph_manager.search_facts_text("married"))
        
        print("\n" + "=" * 50)
        print("TESTING HYBRID SEARCH")
        print("=" * 50)
        
        # Test hybrid searches
        print("🔍 Hybrid Search: 'work and career'")
        print(graph_manager.search_facts_hybrid("work and career", top_k=5))
        
        print("\n🔍 Hybrid Search: 'relationships and connections'")
        print(graph_manager.search_facts_hybrid("relationships and connections", top_k=5))
        
        print("\n🔍 Hybrid Search: 'hobbies and interests'")
        print(graph_manager.search_facts_hybrid("hobbies and interests", top_k=5))
        
        print("\n" + "=" * 50)
        print("TESTING SEARCH WITH DIFFERENT PARAMETERS")
        print("=" * 50)
        
        # Test with different similarity thresholds
        print("🔍 Vector Search with high threshold (0.5): 'software development'")
        print(graph_manager.search_facts_vector("software development", top_k=5, similarity_threshold=0.5))
        
        print("\n🔍 Vector Search with low threshold (0.1): 'software development'")
        print(graph_manager.search_facts_vector("software development", top_k=5, similarity_threshold=0.1))
        
        # Test hybrid search with different weights
        print("\n🔍 Hybrid Search (text-heavy): 'Google engineer'")
        print(graph_manager.search_facts_hybrid("Google engineer", top_k=3, vector_weight=0.3, text_weight=0.7))
        
        print("\n🔍 Hybrid Search (vector-heavy): 'creative pursuits'")
        print(graph_manager.search_facts_hybrid("creative pursuits", top_k=3, vector_weight=0.8, text_weight=0.2))
        
        print("\n" + "=" * 50)
        print("PEOPLE SUMMARY")
        print("=" * 50)
        
        # Show all people and their facts
        print(graph_manager.get_people_facts_simple())

    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        print("Make sure Neo4j is running and connection parameters are correct.")
        print("Also ensure you have installed required packages:")
        print("pip install sentence-transformers scikit-learn")
        
    finally:
        # Always close the database connection
        print("\n🔌 Closing database connection...")
        graph_manager.close()
        print("✅ Connection closed successfully.")