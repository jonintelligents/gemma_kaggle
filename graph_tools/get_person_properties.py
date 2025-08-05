import json

def run(driver, person_id: str) -> str:
    """Get all properties for a specific person."""
    with driver.session() as session:
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