def run(driver, person_id: str, fact_number: int) -> str:
    """Delete a specific fact by its position number."""
    with driver.session() as session:
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
