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

logger = logging.getLogger(__name__)

from sentence_transformers import SentenceTransformer

 # Initialize the sentence transformer model for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2

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
