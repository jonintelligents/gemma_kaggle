from AbstractToolManager import AbstractPersonToolManager
from typing import Any, Dict, List, Optional, Tuple
from EntityKeywordExtractor import EntityExtractor
from neo4j import GraphDatabase
import json
import uuid
from datetime import datetime
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging

#imports for convenience
from graph_tools import update_person_properties
from graph_tools import get_person_properties
from graph_tools import add_person
from graph_tools import get_all_people
from graph_tools import get_person
from graph_tools import delete_person
from graph_tools import add_person_fact
from graph_tools import search_facts
from graph_tools import delete_person_fact
from graph_tools import delete_all_facts_for_person
from graph_tools import get_facts_by_type
from graph_tools import update_fact_type

class GraphPersonManager(AbstractPersonToolManager):
    """
    Neo4j-based implementation of the AbstractPersonToolManager with vector search capabilities.
    
    Graph Structure:
    - Person nodes: Core individuals in the network
    - Entity nodes: Places, organizations, interests, etc. extracted from facts
    - Fact nodes: Individual pieces of information about people (now with vector embeddings)
    - Relationships: Connect people to entities, facts, and other people
    
    Enhanced Features:
    - Creates direct relationships between people mentioned in facts
    - Connects people to existing entities in the graph
    - Avoids duplicate relationships
    - Vector search using sentence transformers for semantic similarity
    - Full-text search on fact content
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        super().__init__()
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.extractor = EntityExtractor()
        
        # Initialize the sentence transformer model for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self._create_constraints()
        self._create_vector_index()
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def clear_all_data(self) -> str:
        """
        Clear all data from the graph database.
        WARNING: This will delete ALL nodes and relationships in the database!
        
        Returns:
            Status message indicating success or failure
        """
        try:
            with self.driver.session() as session:
                # Delete all nodes and relationships
                delete_query = """
                MATCH (n)
                DETACH DELETE n
                """
                
                result = session.run(delete_query)
                
                # Get count of remaining nodes to verify deletion
                count_query = "MATCH (n) RETURN COUNT(n) as node_count"
                count_result = session.run(count_query)
                remaining_nodes = count_result.single()['node_count']
                
                if remaining_nodes == 0:
                    self.logger.info("Successfully cleared all data from the graph database")
                    return "✅ Successfully cleared all data from the graph database"
                else:
                    self.logger.warning(f"Warning: {remaining_nodes} nodes still remain in the database")
                    return f"⚠️ Warning: {remaining_nodes} nodes still remain in the database"
                    
        except Exception as e:
            error_msg = f"❌ Error clearing database: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

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
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE FULLTEXT INDEX fact_text_fulltext IF NOT EXISTS FOR (f:Fact) ON (f.text)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    # Index might already exist
                    pass

    def _create_vector_index(self):
        """Create vector index for fact embeddings."""
        with self.driver.session() as session:
            try:
                # Create vector index for fact embeddings
                vector_index_query = f"""
                CREATE VECTOR INDEX fact_embeddings IF NOT EXISTS
                FOR (f:Fact) ON (f.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {self.embedding_dimension},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
                """
                session.run(vector_index_query)
                self.logger.info("Vector index created/verified for fact embeddings")
            except Exception as e:
                self.logger.warning(f"Could not create vector index: {e}")
                # Neo4j might not support vector indexes in this version

    def _get_text_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for given text."""
        try:
            embedding = self.embedding_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return [0.0] * self.embedding_dimension
        
    def update_person_properties(self, person_id: str, properties: Dict[str, Any]) -> str:
        """Update properties for an existing person."""
        return update_person_properties.run(self.driver, person_id, properties)

    def get_person_properties(self, person_id: str) -> str:
        """Get all properties for a specific person."""
        return get_person_properties.run(self.driver, person_id)
    def add_person(self, name: str, properties: Dict[str, Any] = None) -> str:
        """Add or update a person node in the graph."""
        return add_person.run(self.driver, name, properties)
    
    def get_all_people(self, include_relationships: bool = True) -> str:
        return get_all_people.run(self.driver, include_relationships)
    
    def get_person(self, name: str = None, person_id: str = None, include_relationships: bool = True) -> str:
        """Retrieve specific person(s) from the graph."""
        return get_person.run(self.driver, name, person_id, include_relationships)
    
    def delete_person(self, person_id: str = None, name: str = None) -> str:
        """Delete a person and all their relationships from the graph."""
        return delete_person.run(self.driver, person_id, name)
    
    def add_person_fact(self, person_id: str, fact_text: str, fact_type: str = "general") -> str:
        """Add a fact node with embedding, extract entities, and create inter-person relationships."""
        return add_person_fact.run(self.driver, person_id, fact_text, fact_type)

    def search_facts_vector(self, query_text: str, top_k: int = 5, similarity_threshold: float = 0.3) -> str:
        """
        Search for facts using vector similarity.
        
        Args:
            query_text: Text to search for
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            JSON string with search results
        """
        return search_facts.vector(self.driver, query_text, top_k, similarity_threshold)

    def delete_person_fact(self, person_id: str, fact_number: int) -> str:
        """Delete a specific fact by its position number."""
        return delete_person_fact.run(self.driver, person_id, fact_number)
    
    def delete_all_facts_for_person(self, person_id: str) -> str:
        """Delete all facts for a person while keeping the person node."""
        return delete_all_facts_for_person.run(self.driver, person_id)
    
    def get_facts_by_type(self, person_id: str = None, fact_type: str = None) -> str:
        """Retrieve facts filtered by person and/or type."""
        return get_facts_by_type.run(self.driver, person_id, fact_type)
    
    def update_fact_type(self, person_id: str, fact_number: int, new_fact_type: str) -> str:
        """Update the type of a specific fact."""
        return update_fact_type.run(self.driver, fact_number, new_fact_type)
    
    def search(self, query: str) -> str:
        return search_facts.run(self.driver, query)

    def search_facts_text(self, query: str, person_name: str = None) -> str:
        """
        Search for facts using full-text search.
        
        Args:v
            query: Text to search for
            person_name: Optional person name to filter results
            
        Returns:
            JSON string with search results
        """

        return search_facts.text(self.driver, query, person_name)

    def search_facts_hybrid(self, query_text: str, top_k: int = 10, 
                           vector_weight: float = 0.7, text_weight: float = 0.3,
                           similarity_threshold: float = 0.2) -> str:
        """
        Hybrid search combining vector similarity and text search.
        
        Args:
            query_text: Text to search for
            top_k: Number of top results to return
            vector_weight: Weight for vector similarity scores (0-1)
            text_weight: Weight for text search scores (0-1)
            similarity_threshold: Minimum vector similarity score
            
        Returns:
            JSON string with hybrid search results
        """
        return search_facts.text_vector_hybrid(self.driver, query_text, top_k, vector_weight,
                                text_weight, similarity_threshold)

    def rebuild_all_embeddings(self) -> str:
        """
        Rebuild embeddings for all existing facts in the database.
        Useful when adding vector search to existing data.
        """
        with self.driver.session() as session:
            # Get all facts without embeddings
            query = """
            MATCH (f:Fact)
            WHERE f.embedding IS NULL OR size(f.embedding) = 0
            RETURN f.id as fact_id, f.text as fact_text
            """
            
            result = session.run(query)
            facts_to_update = list(result)
            
            if not facts_to_update:
                return "No facts need embedding updates"
            
            updated_count = 0
            failed_count = 0
            
            for record in facts_to_update:
                fact_id = record['fact_id']
                fact_text = record['fact_text']
                
                try:
                    # Generate embedding
                    embedding = self._get_text_embedding(fact_text)
                    
                    # Update the fact with embedding
                    update_query = """
                    MATCH (f:Fact {id: $fact_id})
                    SET f.embedding = $embedding, f.embedding_updated_at = $updated_at
                    RETURN f.id
                    """
                    
                    update_result = session.run(update_query, 
                                              fact_id=fact_id,
                                              embedding=embedding,
                                              updated_at=datetime.now().isoformat())
                    
                    if update_result.single():
                        updated_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to update embedding for fact {fact_id}: {e}")
                    failed_count += 1
            
            return f"Embedding rebuild complete. Updated: {updated_count}, Failed: {failed_count}"

    def get_graph_statistics(self) -> str:
        """Get statistics about the knowledge graph."""
        with self.driver.session() as session:
            stats_query = """
            MATCH (p:Person) 
            OPTIONAL MATCH (p)-[:HAS_FACT]->(f:Fact)
            OPTIONAL MATCH (p)-[:CONNECTED_TO]->(e:Entity)
            OPTIONAL MATCH (p)-[:RELATED_TO]->(other:Person)
            WITH 
                count(DISTINCT p) as person_count,
                count(DISTINCT f) as fact_count,
                count(DISTINCT e) as entity_count,
                count(DISTINCT other) as connected_people_count
            
            // Get embedding statistics
            OPTIONAL MATCH (f2:Fact)
            WHERE f2.embedding IS NOT NULL AND size(f2.embedding) > 0
            
            RETURN 
                person_count,
                fact_count,
                entity_count,
                connected_people_count,
                count(f2) as facts_with_embeddings
            """
            
            result = session.run(stats_query)
            record = result.single()
            
            if record:
                embedding_percentage = 0
                if record['fact_count'] > 0:
                    embedding_percentage = (record['facts_with_embeddings'] / record['fact_count']) * 100
                
                return f"""Graph Statistics:
    - People: {record['person_count']}
    - Facts: {record['fact_count']}
    - Facts with embeddings: {record['facts_with_embeddings']} ({embedding_percentage:.1f}%)
    - Entities: {record['entity_count']}
    - Inter-person connections: {record['connected_people_count']}"""
            else:
                return "No statistics available"

    def get_people_facts_simple(self) -> str:
        """Retrieve all people with just their names and fact texts in a simplified format."""
        with self.driver.session() as session:
            query = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:HAS_FACT]->(f:Fact)
            WITH p, collect(f.text) as fact_texts
            RETURN p.name as name, fact_texts
            ORDER BY p.name
            """
            
            result = session.run(query)
            people_facts = {}
            
            for record in result:
                name = record['name']
                fact_texts = record['fact_texts']
                
                # Filter out None values (from people with no facts)
                filtered_facts = [fact for fact in fact_texts if fact is not None]
                
                people_facts[name] = filtered_facts
            
            if people_facts:
                total_people = len(people_facts)
                total_facts = sum(len(facts) for facts in people_facts.values())
                summary = f"Retrieved {total_people} people with {total_facts} total facts."
                
                return f"{summary}\n\nPeople facts: {json.dumps(people_facts, indent=2, ensure_ascii=False)}"
            else:
                return "No people found in the database"

    def extract_people_facts_from_full_data(self) -> str:
        """Extract simplified people facts from the full get_all_people data."""
        # Get the full data first
        full_data_result = self.get_all_people(include_relationships=True)
        
        try:
            # Extract JSON part from the result string
            json_start = full_data_result.find('People data: ') + len('People data: ')
            json_data = full_data_result[json_start:]
            
            # Parse the JSON
            people_data = json.loads(json_data)
            
            # Extract just names and fact texts
            people_facts = {}
            for person in people_data:
                name = person['name']
                facts = person.get('facts', [])
                fact_texts = [fact['text'] for fact in facts if fact.get('text')]
                people_facts[name] = fact_texts
            
            total_people = len(people_facts)
            total_facts = sum(len(facts) for facts in people_facts.values())
            summary = f"Extracted {total_people} people with {total_facts} total facts."
            
            return f"{summary}\n\nPeople facts: {json.dumps(people_facts, indent=2, ensure_ascii=False)}"
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return f"Error processing data: {str(e)}"
        
    def convert_json_to_formatted_string(self, people_facts_json: dict) -> str:
        """
        Convert a JSON dictionary of people facts to formatted string.
        
        Args:
            people_facts_json: Dictionary with format {"Name": ["fact1", "fact2", ...]}
        
        Returns:
            String with each person on a new line in format "Name: fact1, fact2, fact3"
        """
        formatted_lines = []
        
        for name, facts in people_facts_json.items():
            # Join facts with commas
            facts_string = ", ".join(facts)
            
            # Format as "Name: facts"
            formatted_line = f"{name}: {facts_string}"
            formatted_lines.append(formatted_line)
        
        return "\n".join(formatted_lines)


if __name__ == "__main__":
    """
    Main method to demonstrate GraphPersonManager usage with search capabilities.
    """
    # Initialize the GraphPersonManager
    graph_manager = GraphPersonManager(
        uri="bolt://localhost:7687",
        user="neo4j", 
        password="password"  # Replace with your actual password
    )
    
    try:
        print("=" * 80)
        print("ENHANCED KNOWLEDGE GRAPH WITH VECTOR SEARCH")
        print("=" * 80)
        
        # Clear all existing data first
        print("\n" + "=" * 50)
        print("CLEARING EXISTING DATA")
        print("=" * 50)
        
        print(graph_manager.clear_all_data())
        
        # Verify database is empty
        print("\nVerifying database is clean:")
        print(graph_manager.get_graph_statistics())
        
        # Add some sample data for testing
        print("\n" + "=" * 50)
        print("ADDING SAMPLE DATA")
        print("=" * 50)
        
        # Add people
        print(graph_manager.add_person("Alice Johnson", {"age": 30, "location": "New York"}))
        print(graph_manager.add_person("Bob Smith", {"age": 25, "location": "California"}))
        print(graph_manager.add_person("Carol Davis", {"age": 35, "location": "Texas"}))
        
        # Add facts with different types
        print(graph_manager.add_person_fact("Alice Johnson", "Alice works as a software engineer at Google", "work"))
        print(graph_manager.add_person_fact("Alice Johnson", "Alice loves hiking in the mountains", "hobby"))
        print(graph_manager.add_person_fact("Alice Johnson", "Alice is married to Bob Smith", "relationship"))
        
        print(graph_manager.add_person_fact("Bob Smith", "Bob is a data scientist specializing in machine learning", "work"))
        print(graph_manager.add_person_fact("Bob Smith", "Bob enjoys playing guitar and composing music", "hobby"))
        print(graph_manager.add_person_fact("Bob Smith", "Bob and Alice went to college together", "relationship"))
        
        print(graph_manager.add_person_fact("Carol Davis", "Carol is a marketing manager at a tech startup", "work"))
        print(graph_manager.add_person_fact("Carol Davis", "Carol practices yoga and meditation daily", "hobby"))
        print(graph_manager.add_person_fact("Carol Davis", "Carol volunteers at the local animal shelter", "volunteer"))
        
        print("\n" + "=" * 50)
        print("GRAPH STATISTICS AFTER ADDING DATA")
        print("=" * 50)
        
        print(graph_manager.get_graph_statistics())
        
        print("\n" + "=" * 50)
        print("REBUILDING EMBEDDINGS FOR EXISTING FACTS")
        print("=" * 50)
        
        print(graph_manager.rebuild_all_embeddings())
        
        print("\n" + "=" * 50)
        print("UPDATED GRAPH STATISTICS")
        print("=" * 50)
        
        print(graph_manager.get_graph_statistics())
        
        print("\n" + "=" * 50)
        print("TESTING VECTOR SEARCH")
        print("=" * 50)
        
        # Test vector searches
        print("🔍 Vector Search: 'programming and technology'")
        print(graph_manager.search_facts_vector("programming and technology", top_k=3))
        
        print("\n🔍 Vector Search: 'music and creative activities'")
        print(graph_manager.search_facts_vector("music and creative activities", top_k=3))
        
        print("\n🔍 Vector Search: 'physical fitness and exercise'")
        print(graph_manager.search_facts_vector("physical fitness and exercise", top_k=3))
        
        print("\n" + "=" * 50)
        print("TESTING TEXT SEARCH")
        print("=" * 50)
        
        # Test text searches
        print("🔍 Text Search: 'Google'")
        print(graph_manager.search_facts_text("Google"))
        
        print("\n🔍 Text Search: 'music' (for Bob Smith)")
        print(graph_manager.search_facts_text("music", person_name="Bob Smith"))
        
        print("\n🔍 Text Search: 'married'")
        print(graph_manager.search_facts_text("married"))
        
        print("\n" + "=" * 50)
        print("TESTING HYBRID SEARCH")
        print("=" * 50)
        
        # Test hybrid searches
        print("🔍 Hybrid Search: 'work and career'")
        print(graph_manager.search_facts_hybrid("work and career", top_k=5))
        
        print("\n🔍 Hybrid Search: 'relationships and connections'")
        print(graph_manager.search_facts_hybrid("relationships and connections", top_k=5))
        
        print("\n🔍 Hybrid Search: 'hobbies and interests'")
        print(graph_manager.search_facts_hybrid("hobbies and interests", top_k=5))
        
        print("\n" + "=" * 50)
        print("TESTING SEARCH WITH DIFFERENT PARAMETERS")
        print("=" * 50)
        
        # Test with different similarity thresholds
        print("🔍 Vector Search with high threshold (0.5): 'software development'")
        print(graph_manager.search_facts_vector("software development", top_k=5, similarity_threshold=0.5))
        
        print("\n🔍 Vector Search with low threshold (0.1): 'software development'")
        print(graph_manager.search_facts_vector("software development", top_k=5, similarity_threshold=0.1))
        
        # Test hybrid search with different weights
        print("\n🔍 Hybrid Search (text-heavy): 'Google engineer'")
        print(graph_manager.search_facts_hybrid("Google engineer", top_k=3, vector_weight=0.3, text_weight=0.7))
        
        print("\n🔍 Hybrid Search (vector-heavy): 'creative pursuits'")
        print(graph_manager.search_facts_hybrid("creative pursuits", top_k=3, vector_weight=0.8, text_weight=0.2))
        
        print("\n" + "=" * 50)
        print("PEOPLE SUMMARY")
        print("=" * 50)
        
        # Show all people and their facts
        print(graph_manager.get_people_facts_simple())

    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        print("Make sure Neo4j is running and connection parameters are correct.")
        print("Also ensure you have installed required packages:")
        print("pip install sentence-transformers scikit-learn")
        
    finally:
        # Always close the database connection
        print("\n🔌 Closing database connection...")
        graph_manager.close()
        print("✅ Connection closed successfully.")