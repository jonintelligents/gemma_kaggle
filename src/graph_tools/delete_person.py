def run(driver, person_id: str = None, name: str = None) -> str:
    """Delete a person and all their relationships from the graph."""
    identifier = person_id or name
    if not identifier:
        return "Error: Must provide either person_id or name"
    
    with driver.session() as session:
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