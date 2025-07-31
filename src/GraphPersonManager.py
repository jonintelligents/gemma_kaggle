from AbstractToolManager import AbstractPersonToolManager
from typing import Any, Dict, List, Optional
from EntityKeywordExtractor import EntityExtractor
from neo4j import GraphDatabase
import json
import uuid
from datetime import datetime
import re

class GraphPersonManager(AbstractPersonToolManager):
    """
    Neo4j-based implementation of the AbstractPersonToolManager.
    
    Graph Structure:
    - Person nodes: Core individuals in the network
    - Entity nodes: Places, organizations, interests, etc. extracted from facts
    - Fact nodes: Individual pieces of information about people
    - Relationships: Connect people to entities, facts, and other people
    
    Enhanced Features:
    - Creates direct relationships between people mentioned in facts
    - Connects people to existing entities in the graph
    - Avoids duplicate relationships
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        super().__init__()
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.extractor = EntityExtractor()
        self._create_constraints()
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

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
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    # Index might already exist
                    pass
    
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
    
    def get_all_people(self, include_relationships: bool = True) -> str:
        """Retrieve all people from the graph."""
        with self.driver.session() as session:
            if include_relationships:
                query = """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r]->(connected)
                RETURN p.name as name, 
                       p.summary as summary,
                       collect(DISTINCT {type: type(r), node: labels(connected)[0], name: connected.name}) as relationships
                ORDER BY p.name
                """
            else:
                query = """
                MATCH (p:Person)
                RETURN p.name as name, p.summary as summary
                ORDER BY p.name
                """
            
            result = session.run(query)
            people = []
            
            for record in result:
                person_info = {
                    'name': record['name'],
                    'summary': record.get('summary', '')
                }
                
                if include_relationships and 'relationships' in record:
                    person_info['relationships'] = [rel for rel in record['relationships'] if rel['name']]
                
                people.append(person_info)
            
            if people:
                return f"Retrieved {len(people)} people: {json.dumps(people, indent=2)}"
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
        """Add a fact node, extract entities, and create inter-person relationships."""
        with self.driver.session() as session:
            # First check if person exists
            person_check = session.run("MATCH (p:Person {name: $person_id}) RETURN p", person_id=person_id)
            if not person_check.single():
                return f"Error: Person '{person_id}' not found"
            
            # Extract entities from the fact text
            extraction_result = self.extractor.extract(fact_text, extract_key_terms=False)
            
            # Extract potential person names from the fact
            potential_person_names = self._extract_person_names_from_fact(fact_text, person_id)
            
            # Generate unique fact ID
            fact_id = str(uuid.uuid4())
            
            # Create fact node
            fact_query = """
            MATCH (p:Person {name: $person_id})
            CREATE (f:Fact {
                id: $fact_id,
                text: $fact_text,
                type: $fact_type,
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
            RETURN 
                count(DISTINCT p) as person_count,
                count(DISTINCT f) as fact_count,
                count(DISTINCT e) as entity_count,
                count(DISTINCT other) as connected_people_count
            """
            
            result = session.run(stats_query)
            record = result.single()
            
            if record:
                return f"""Graph Statistics:
- People: {record['person_count']}
- Facts: {record['fact_count']}
- Entities: {record['entity_count']}
- Inter-person connections: {record['connected_people_count']}"""
            else:
                return "No statistics available"
