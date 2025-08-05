from datetime import datetime

def run(driver, person_id: str, fact_number: int, new_fact_type: str) -> str:
    """Update the type of a specific fact."""
    with driver.session() as session:
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
