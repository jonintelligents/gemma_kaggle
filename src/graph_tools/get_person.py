import json

def run(driver, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
    """Retrieve specific person(s) from the graph."""
    with driver.session() as session:
        if name:
            # Support partial name matching
            base_query = "MATCH (p:Person) WHERE p.name CONTAINS $name"
            params = {'name': name}
        elif person_id:
            base_query = "MATCH (p:Person) WHERE p.name = $person_id"
            params = {'person_id': person_id}
        else:
            #return self.get_all_people(include_relationships)
            return None
        
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