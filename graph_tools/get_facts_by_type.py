def run(driver, person_id: str = None, fact_type: str = None) -> str:
    """Retrieve facts filtered by person and/or type."""
    with driver.session() as session:
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