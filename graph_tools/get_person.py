import json
from typing import Dict, Any

def get_person(driver, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
    with driver.session() as session:
        # Enhanced parameter handling with debugging
        print(f"DEBUG: Raw inputs - name={repr(name)}, person_id={repr(person_id)}, type(name)={type(name)}")
        
        if name is not None and name is not True and name is not False:
            name_str = str(name).strip()
            if name_str and name_str.lower() not in ['true', 'false', 'none']:
                base_query = "MATCH (p:Person) WHERE toLower(p.name) CONTAINS toLower($name)"
                params = {'name': name_str}
                search_term = name_str
                print(f"DEBUG: Searching with name='{name_str}'")
            else:
                return f"Please provide a valid name parameter. Got: {repr(name)}"
        elif person_id is not None and person_id is not True and person_id is not False:
            person_id_str = str(person_id).strip()
            if person_id_str and person_id_str.lower() not in ['true', 'false', 'none']:
                base_query = "MATCH (p:Person) WHERE p.name = $name"  
                params = {'name': person_id_str}
                search_term = person_id_str
                print(f"DEBUG: Searching with exact name='{person_id_str}'")
            else:
                return f"Please provide a valid person_id parameter. Got: {repr(person_id)}"
        else:
            return f"Please provide either a name or person_id parameter. Got name={repr(name)}, person_id={repr(person_id)}"
        
        # Debug: Print the actual query and parameters
        final_query = f"{base_query} RETURN p ORDER BY p.name"
        print(f"DEBUG: Query = {final_query}")
        print(f"DEBUG: Params = {params}")
        
        # Test with simple query first
        simple_result = session.run(final_query, **params)
        simple_records = list(simple_result)
        print(f"DEBUG: Found {len(simple_records)} records")
        
        if include_relationships:
            query = f"""
            {base_query}
            OPTIONAL MATCH (p)-[r]->(related)
            OPTIONAL MATCH (p)<-[r2]-(related2)
            WITH p, 
                 collect(DISTINCT {{
                     node: related, 
                     relationship: type(r), 
                     direction: 'outgoing'
                 }}) + collect(DISTINCT {{
                     node: related2, 
                     relationship: type(r2), 
                     direction: 'incoming'
                 }}) as all_relationships
            RETURN p, all_relationships
            ORDER BY p.name
            """
        else:
            query = f"""
            {base_query}
            RETURN p
            ORDER BY p.name
            """
        
        result = session.run(query, **params)
        people = []
        
        for record in result:
            person_node = record['p']
            
            # Extract all properties from the person node
            person_info = {
                'name': person_node.get('name', ''),
                'properties': {}
            }
            
            # Add all properties except name (since it's already at the top level)
            for key, value in person_node.items():
                if key != 'name':
                    person_info['properties'][key] = value
            
            if include_relationships:
                relationships = record.get('all_relationships', [])
                connected_people = []
                facts = []
                entities = []
                other_connections = []
                
                for rel_info in relationships:
                    if rel_info['node'] is None:
                        continue
                        
                    related_node = rel_info['node']
                    relationship_type = rel_info['relationship']
                    direction = rel_info['direction']
                    
                    # Check node labels to categorize relationships
                    node_labels = list(related_node.labels)
                    
                    if 'Person' in node_labels:
                        connected_people.append({
                            'name': related_node.get('name', 'Unknown'),
                            'relationship': relationship_type,
                            'direction': direction
                        })
                    elif 'Fact' in node_labels:
                        facts.append({
                            'id': related_node.get('id', ''),
                            'text': related_node.get('text', ''),
                            'type': related_node.get('type', ''),
                            'relationship': relationship_type
                        })
                    elif 'Entity' in node_labels:
                        entities.append({
                            'name': related_node.get('name', ''),
                            'type': related_node.get('type', ''),
                            'relationship': relationship_type
                        })
                    else:
                        # Handle any other types of connections
                        other_connections.append({
                            'labels': node_labels,
                            'properties': dict(related_node),
                            'relationship': relationship_type,
                            'direction': direction
                        })
                
                # Only add non-empty collections
                if connected_people:
                    person_info['connected_people'] = connected_people
                if facts:
                    person_info['facts'] = facts
                if entities:
                    person_info['entities'] = entities
                if other_connections:
                    person_info['other_connections'] = other_connections
            
            people.append(person_info)
        
        if people:
            return json.dumps({
                'found': len(people),
                'people': people
            }, indent=2, default=str)
        else:
            return json.dumps({
                'found': 0,
                'message': f"No person found matching the criteria",
                'searched_for': search_term
            }, indent=2)


def run(driver, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
    """
    Convenience function that returns a human-readable summary of what we know about a person.
    Perfect for queries like "what do you know about Marcus?"
    """
    result = get_person(driver, name=name, person_id=None, include_relationships=True)
    
    try:
        data = json.loads(result)
        
        if data['found'] == 0:
            return f"I don't have any information about '{name}' in the database."
        
        summaries = []
        for person in data['people']:
            summary_parts = [f"**{person['name']}**"]
            
            # Add properties
            if person.get('properties'):
                summary_parts.append("\n**Properties:**")
                for key, value in person['properties'].items():
                    if value:  # Only show non-empty values
                        summary_parts.append(f"- {key}: {value}")
            
            # Add connected people
            if person.get('connected_people'):
                summary_parts.append(f"\n**Connected to {len(person['connected_people'])} people:**")
                for connection in person['connected_people']:
                    summary_parts.append(f"- {connection['name']} ({connection['relationship']})")
            
            # Add facts
            if person.get('facts'):
                summary_parts.append(f"\n**Facts ({len(person['facts'])}):**")
                for fact in person['facts']:
                    if fact.get('text'):
                        summary_parts.append(f"- {fact['text']}")
            
            # Add entities
            if person.get('entities'):
                summary_parts.append(f"\n**Associated entities ({len(person['entities'])}):**")
                for entity in person['entities']:
                    summary_parts.append(f"- {entity['name']} ({entity.get('type', 'unknown type')})")
            
            summaries.append('\n'.join(summary_parts))
        
        return '\n\n' + '\n\n---\n\n'.join(summaries)
        
    except json.JSONDecodeError:
        return f"Error parsing person data: {result}"