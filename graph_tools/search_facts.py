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
from collections import defaultdict

logger = logging.getLogger(__name__)

 # Initialize the sentence transformer model for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2

def run(driver, search_string: str, top_k: int = 10, 
        include_facts: bool = True, min_fact_matches: int = 1) -> str:
    """
    Main search method that queries the entire database to find people that match the search string.
    Uses hybrid search across all facts and re-ranks results by person relevance.
    
    Args:
        search_string: Text to search for
        top_k: Number of top people to return
        include_facts: Whether to include matching facts in results
        min_fact_matches: Minimum number of fact matches required for a person to be included
        
    Returns:
        JSON string with ranked people and their matching facts
    """
    try:
        # Use hybrid search to get all matching facts
        hybrid_results_str = text_vector_hybrid(
            driver, search_string, 
            top_k=50,  # Get more facts to ensure we capture all relevant people
            vector_weight=0.6, 
            text_weight=0.4,
            similarity_threshold=0.15
        )
        
        # Parse hybrid search results
        hybrid_data = json.loads(hybrid_results_str.replace("Hybrid search results: ", ""))
        matching_facts = hybrid_data.get('results', [])
        
        if not matching_facts:
            return f"No people found matching search string: '{search_string}'"
        
        # Group facts by person and calculate person-level scores
        person_scores = defaultdict(lambda: {
            'facts': [],
            'total_hybrid_score': 0.0,
            'max_hybrid_score': 0.0,
            'avg_hybrid_score': 0.0,
            'fact_count': 0,
            'vector_score_sum': 0.0,
            'text_score_sum': 0.0
        })
        
        for fact in matching_facts:
            person_name = fact['person_name']
            person_data = person_scores[person_name]
            
            person_data['facts'].append(fact)
            person_data['total_hybrid_score'] += fact['hybrid_score']
            person_data['max_hybrid_score'] = max(person_data['max_hybrid_score'], fact['hybrid_score'])
            person_data['fact_count'] += 1
            person_data['vector_score_sum'] += fact.get('vector_score', 0.0)
            person_data['text_score_sum'] += fact.get('text_score', 0.0)
        
        # Calculate final person scores and filter by minimum fact matches
        ranked_people = []
        for person_name, data in person_scores.items():
            if data['fact_count'] < min_fact_matches:
                continue
                
            data['avg_hybrid_score'] = data['total_hybrid_score'] / data['fact_count']
            data['avg_vector_score'] = data['vector_score_sum'] / data['fact_count']
            data['avg_text_score'] = data['text_score_sum'] / data['fact_count']
            
            # Calculate final person relevance score (weighted combination)
            person_relevance_score = (
                0.4 * data['max_hybrid_score'] +           # Best single match
                0.3 * data['avg_hybrid_score'] +           # Average quality
                0.2 * min(data['fact_count'] / 5.0, 1.0) + # Quantity bonus (capped)
                0.1 * data['total_hybrid_score']           # Total relevance
            )
            
            person_result = {
                'person_name': person_name,
                'relevance_score': person_relevance_score,
                'matching_facts_count': data['fact_count'],
                'max_fact_score': data['max_hybrid_score'],
                'avg_fact_score': data['avg_hybrid_score'],
                'avg_vector_score': data['avg_vector_score'],
                'avg_text_score': data['avg_text_score']
            }
            
            # Include facts if requested
            if include_facts:
                # Sort facts by hybrid score and include top ones
                sorted_facts = sorted(data['facts'], 
                                    key=lambda x: x['hybrid_score'], 
                                    reverse=True)
                person_result['matching_facts'] = sorted_facts[:5]  # Top 5 facts per person
            
            ranked_people.append(person_result)
        
        # Sort people by relevance score
        ranked_people.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_people = ranked_people[:top_k]
        
        # Prepare final results in readable format
        readable_results = []
        for person in top_people:
            person_result = {
                'name': person['person_name'],
                'relevance_score': round(person['relevance_score'], 3),
                'matching_facts_count': person['matching_facts_count']
            }
            
            if include_facts and 'matching_facts' in person:
                person_result['facts'] = []
                for fact in person['matching_facts']:
                    fact_info = {
                        'text': fact['fact_text'],
                        'type': fact.get('fact_type', 'general'),
                        'score': round(fact['hybrid_score'], 3),
                        'created': fact.get('created_at', 'unknown')
                    }
                    person_result['facts'].append(fact_info)
            
            readable_results.append(person_result)
        
        search_summary = {
            'search_query': search_string,
            'results_summary': {
                'total_people_found': len(ranked_people),
                'people_returned': len(top_people),
                'total_facts_analyzed': len(matching_facts)
            },
            'people': readable_results
        }
        
        return format_results_as_text(json.dumps(search_summary, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"Error in run method: {e}")
        return f"Error searching for people: {str(e)}"

def format_results_as_text(json_results: str) -> str:
    """
    Converts JSON search results to readable text format.
    
    Args:
        json_results: JSON string from the run() method
        
    Returns:
        Formatted text string with person names and their facts
    """
    try:
        # Parse the JSON results
        data = json.loads(json_results)
        
        # Start building the text output
        text_output = ["**** RESULTS ****\n"]
        
        # Add summary information
        summary = data.get('results_summary', {})
        search_query = data.get('search_query', 'Unknown')
        
        text_output.append(f"Search Query: {search_query}")
        text_output.append(f"People Found: {summary.get('people_returned', 0)} of {summary.get('total_people_found', 0)}")
        text_output.append(f"Total Facts Analyzed: {summary.get('total_facts_analyzed', 0)}")
        text_output.append("\n" + "="*50 + "\n")
        
        # Format each person and their facts
        people = data.get('people', [])
        
        if not people:
            text_output.append("No matching people found.")
        else:
            for i, person in enumerate(people, 1):
                name = person.get('name', 'Unknown')
                relevance_score = person.get('relevance_score', 0)
                facts_count = person.get('matching_facts_count', 0)
                
                # Person header with ranking and score
                text_output.append(f"{i}. {name}")
                text_output.append(f"   (Relevance: {relevance_score}, Facts: {facts_count})")
                
                # Add facts if they exist
                facts = person.get('facts', [])
                if facts:
                    for fact in facts:
                        fact_text = fact.get('text', 'No text available')
                        fact_type = fact.get('type', 'general')
                        fact_score = fact.get('score', 0)
                        
                        # Format: tab + fact text + (type, score)
                        text_output.append(f"\t{fact_text}")
                        text_output.append(f"\t  [{fact_type.upper()}, score: {fact_score}]")
                else:
                    text_output.append("\tNo specific facts available")
                
                # Add separator between people (except for the last one)
                if i < len(people):
                    text_output.append("\n" + "-"*30 + "\n")
        
        return "\n".join(text_output)
        
    except json.JSONDecodeError as e:
        return f"**** RESULTS ****\n\nError: Invalid JSON format - {str(e)}"
    except Exception as e:
        return f"**** RESULTS ****\n\nError formatting results: {str(e)}"

def run_and_format_text(driver, search_string: str, top_k: int = 10, 
                       include_facts: bool = True, min_fact_matches: int = 1) -> str:
    """
    Convenience method that runs the search and returns formatted text results.
    
    Args:
        search_string: Text to search for
        top_k: Number of top people to return
        include_facts: Whether to include matching facts in results
        min_fact_matches: Minimum number of fact matches required
        
    Returns:
        Formatted text string with search results
    """
    json_results = run(driver, search_string, top_k, include_facts, min_fact_matches)
    return format_results_as_text(json_results)

def vector(driver, query_text: str, top_k: int = 5, similarity_threshold: float = 0.3) -> str:
    """
    Search for facts using vector similarity.
    
    Args:
        query_text: Text to search for
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity score (0-1)
        
    Returns:
        JSON string with search results
    """
    try:
        # Generate embedding for query text
        query_embedding = _get_text_embedding(query_text)
        
        with driver.session() as session:
            # First, get all facts with embeddings
            get_facts_query = """
            MATCH (p:Person)-[:HAS_FACT]->(f:Fact)
            WHERE f.embedding IS NOT NULL
            RETURN p.name as person_name, f.id as fact_id, f.text as fact_text, 
                    f.type as fact_type, f.embedding as embedding, f.created_at as created_at
            """
            
            result = session.run(get_facts_query)
            facts = list(result)
            
            if not facts:
                return "No facts with embeddings found in the database"
            
            # Calculate similarities
            similarities = []
            for record in facts:
                fact_embedding = record['embedding']
                if fact_embedding:
                    # Calculate cosine similarity
                    similarity = cosine_similarity(
                        [query_embedding], 
                        [fact_embedding]
                    )[0][0]
                    
                    if similarity >= similarity_threshold:
                        similarities.append({
                            'person_name': record['person_name'],
                            'fact_id': record['fact_id'],
                            'fact_text': record['fact_text'],
                            'fact_type': record['fact_type'],
                            'created_at': record['created_at'],
                            'similarity_score': float(similarity)
                        })
            
            # Sort by similarity score (descending) and take top_k
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            top_results = similarities[:top_k]
            
            search_summary = {
                'query': query_text,
                'total_facts_searched': len(facts),
                'facts_above_threshold': len(similarities),
                'top_results_returned': len(top_results),
                'similarity_threshold': similarity_threshold,
                'results': top_results
            }
            
            return f"Vector search results: {json.dumps(search_summary, indent=2, default=str)}"
            
    except Exception as e:
        return f"Error performing vector search: {str(e)}"
    
def _get_text_embedding(text: str) -> List[float]:
    """Generate embedding vector for given text."""
    try:
        embedding = embedding_model.encode([text])[0]
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return [0.0] * embedding_dimension

def text(driver, query_text: str, person_name: str = None) -> str:
    """
    Search for facts using full-text search.
    
    Args:
        query_text: Text to search for
        person_name: Optional person name to filter results
        
    Returns:
        JSON string with search results
    """

    with driver.session() as session:
        try:
            if person_name:
                # Search within specific person's facts
                query = """
                CALL db.index.fulltext.queryNodes('fact_text_fulltext', $query_text)
                YIELD node, score
                MATCH (p:Person {name: $person_name})-[:HAS_FACT]->(node)
                RETURN p.name as person_name, node.id as fact_id, node.text as fact_text,
                        node.type as fact_type, node.created_at as created_at, score
                ORDER BY score DESC
                """
                
                result = session.run(query, query_text=query_text, person_name=person_name)
            else:
                # Search across all facts
                query = """
                CALL db.index.fulltext.queryNodes('fact_text_fulltext', $query_text)
                YIELD node, score
                MATCH (p:Person)-[:HAS_FACT]->(node)
                RETURN p.name as person_name, node.id as fact_id, node.text as fact_text,
                        node.type as fact_type, node.created_at as created_at, score
                ORDER BY score DESC
                """
                
                result = session.run(query, query_text=query_text)
            
            facts = []
            for record in result:
                facts.append({
                    'person_name': record['person_name'],
                    'fact_id': record['fact_id'],
                    'fact_text': record['fact_text'],
                    'fact_type': record['fact_type'],
                    'created_at': record['created_at'],
                    'relevance_score': float(record['score'])
                })
            
            search_summary = {
                'query': query_text,
                'person_filter': person_name,
                'total_results': len(facts),
                'results': facts
            }
            
            return f"Text search results: {json.dumps(search_summary, indent=2, default=str)}"
            
        except Exception as e:
            # Fallback to simple CONTAINS search if fulltext index not available
            logger.warning(f"Fulltext search failed, using fallback: {e}")
            return _search_facts_text_fallback(driver, query_text, person_name)

def _search_facts_text_fallback(driver, query_text: str, person_name: str = None) -> str:
    """
    Fallback text search using CONTAINS when fulltext index is not available.
    """
    with driver.session() as session:
        if person_name:
            query = """
            MATCH (p:Person {name: $person_name})-[:HAS_FACT]->(f:Fact)
            WHERE f.text CONTAINS $query_text
            RETURN p.name as person_name, f.id as fact_id, f.text as fact_text,
                    f.type as fact_type, f.created_at as created_at
            ORDER BY f.created_at DESC
            """
            result = session.run(query, query_text=query_text, person_name=person_name)
        else:
            query = """
            MATCH (p:Person)-[:HAS_FACT]->(f:Fact)
            WHERE f.text CONTAINS $query_text
            RETURN p.name as person_name, f.id as fact_id, f.text as fact_text,
                    f.type as fact_type, f.created_at as created_at
            ORDER BY f.created_at DESC
            """
            result = session.run(query, query_text=query_text)
        
        facts = []
        for record in result:
            facts.append({
                'person_name': record['person_name'],
                'fact_id': record['fact_id'],
                'fact_text': record['fact_text'],
                'fact_type': record['fact_type'],
                'created_at': record['created_at']
            })
        
        search_summary = {
            'query': query_text,
            'person_filter': person_name,
            'total_results': len(facts),
            'search_method': 'fallback_contains',
            'results': facts
        }
        
        return f"Text search results (fallback): {json.dumps(search_summary, indent=2, default=str)}"

def text_vector_hybrid(driver, query_text: str, top_k: int = 10, 
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
    try:
        # Get vector search results
        vector_results_str = vector(driver, query_text, top_k * 2, similarity_threshold)
        vector_data = json.loads(vector_results_str.replace("Vector search results: ", ""))
        
        # Get text search results
        text_results_str = text(driver, query_text)
        text_data = json.loads(text_results_str.replace("Text search results: ", "").replace("Text search results (fallback): ", ""))
        
        # Create lookup dictionaries
        vector_scores = {r['fact_id']: r['similarity_score'] for r in vector_data.get('results', [])}
        text_scores = {r['fact_id']: r.get('relevance_score', 1.0) for r in text_data.get('results', [])}
        
        # Combine all unique facts
        all_facts = {}
        
        # Add vector results
        for fact in vector_data.get('results', []):
            all_facts[fact['fact_id']] = fact
        
        # Add text results
        for fact in text_data.get('results', []):
            if fact['fact_id'] not in all_facts:
                all_facts[fact['fact_id']] = fact
        
        # Calculate hybrid scores
        hybrid_results = []
        for fact_id, fact in all_facts.items():
            vector_score = vector_scores.get(fact_id, 0.0)
            text_score = min(text_scores.get(fact_id, 0.0), 1.0)  # Normalize text scores
            
            hybrid_score = (vector_weight * vector_score) + (text_weight * text_score)
            
            fact['hybrid_score'] = hybrid_score
            fact['vector_score'] = vector_score
            fact['text_score'] = text_score
            hybrid_results.append(fact)
        
        # Sort by hybrid score and take top_k
        hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        top_results = hybrid_results[:top_k]
        
        search_summary = {
            'query': query_text,
            'search_type': 'hybrid',
            'vector_weight': vector_weight,
            'text_weight': text_weight,
            'similarity_threshold': similarity_threshold,
            'total_unique_facts': len(all_facts),
            'top_results_returned': len(top_results),
            'results': top_results
        }
        
        return f"Hybrid search results: {json.dumps(search_summary, indent=2, default=str)}"
        
    except Exception as e:
        return f"Error performing hybrid search: {str(e)}"