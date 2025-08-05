import json

def run(driver, include_relationships: bool = True) -> str:
    """Retrieve all people from the graph with their complete information."""
    with driver.session() as session:
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