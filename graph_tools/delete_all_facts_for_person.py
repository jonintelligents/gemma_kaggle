def run(driver, person_id: str) -> str:
        """Delete all facts for a person while keeping the person node."""
        with driver.session() as session:
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