import spacy
import json
from typing import Dict, Any, List, Set
from collections import Counter
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EntityExtractor:
    """
    A class for extracting named entities and key terms from text using spaCy.
    
    Usage:
        extractor = EntityExtractor()
        result = extractor.extract("Barack Obama was born in Honolulu.")
    """
    
    def __init__(self, model_name: str = "en_core_web_lg"):
        """
        Initialize the entity extractor with a spaCy model.
        
        Args:
            model_name (str): Name of the spaCy model to load
        """
        self.model_name = model_name
        self.nlp = self._load_spacy_model()
        
    def _load_spacy_model(self):
        """Load the spaCy language model."""
        try:
            nlp = spacy.load(self.model_name)
            logging.info(f"SpaCy model '{self.model_name}' loaded successfully.")
            return nlp
        except OSError:
            error_msg = f"SpaCy model '{self.model_name}' not found. Please run: python -m spacy download {self.model_name}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
    
    def extract(self, text: str, extract_key_terms: bool = True, max_key_terms: int = 10) -> Dict[str, Any]:
        """
        Extract named entities and optionally key terms from text.
        
        Args:
            text (str): The text to analyze
            extract_key_terms (bool): Whether to extract key terms
            max_key_terms (int): Maximum number of key terms to return
            
        Returns:
            Dict containing:
                - entities: List of named entities with text, label, and description
                - entity_count: Number of entities found
                - unique_labels: Set of entity types found
                - key_terms: List of important terms (if extract_key_terms=True)
        """
        if not text or not text.strip():
            return {
                "entities": [],
                "entity_count": 0,
                "unique_labels": [],
                "key_terms": []
            }
        
        # Extract entities
        entities = self._extract_named_entities(text)
        
        # Extract key terms
        key_terms = []
        if extract_key_terms:
            key_terms = self._extract_key_terms(text, max_terms=max_key_terms)
        
        # Get unique labels
        unique_labels = list(set(entity['label'] for entity in entities))
        
        return {
            "entities": entities,
            "entity_count": len(entities),
            "unique_labels": unique_labels,
            "key_terms": key_terms
        }
    
    def _extract_named_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract named entities from text using spaCy."""
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "description": spacy.explain(ent.label_),
                "start": ent.start_char,
                "end": ent.end_char
            })
        
        return entities
    
    def _extract_key_terms(self, text: str, max_terms: int = 10) -> List[Dict[str, Any]]:
        """
        Extract key terms from text using multiple scoring methods.
        
        Args:
            text (str): Input text
            max_terms (int): Maximum number of terms to return
            
        Returns:
            List of key terms with scores and metadata
        """
        doc = self.nlp(text)
        
        # Collect candidate terms
        candidates = []
        
        # Get individual tokens that could be key terms
        for token in doc:
            if self._is_key_term_candidate(token):
                candidates.append({
                    "text": token.lemma_.lower(),
                    "original": token.text,
                    "pos": token.pos_,
                    "is_entity": token.ent_type_ != "",
                    "entity_type": token.ent_type_ if token.ent_type_ else None
                })
        
        # Get noun phrases as potential key terms
        for chunk in doc.noun_chunks:
            if len(chunk.text.strip()) > 2 and chunk.root.pos_ != "PRON":
                # Check if this noun phrase contains entities
                has_entity = any(token.ent_type_ != "" for token in chunk)
                candidates.append({
                    "text": chunk.text.lower().strip(),
                    "original": chunk.text.strip(),
                    "pos": "NOUN_PHRASE",
                    "is_entity": has_entity,
                    "entity_type": None
                })
        
        # Score and rank candidates
        scored_terms = self._score_key_terms(candidates, doc)
        
        # Remove duplicates and sort by score
        unique_terms = {}
        for term in scored_terms:
            key = term["text"]
            if key not in unique_terms or term["score"] > unique_terms[key]["score"]:
                unique_terms[key] = term
        
        # Sort by score and return top terms
        top_terms = sorted(unique_terms.values(), key=lambda x: x["score"], reverse=True)
        return top_terms[:max_terms]
    
    def _is_key_term_candidate(self, token) -> bool:
        """Check if a token could be a key term."""
        # Skip if it's punctuation, space, or stop word
        if token.is_punct or token.is_space or token.is_stop:
            return False
        
        # Skip very short words
        if len(token.text) < 3:
            return False
        
        # Include nouns, proper nouns, adjectives, and verbs
        if token.pos_ in ["NOUN", "PROPN", "ADJ", "VERB"]:
            return True
        
        # Include named entities even if they don't match POS criteria
        if token.ent_type_:
            return True
        
        return False
    
    def _score_key_terms(self, candidates: List[Dict], doc) -> List[Dict[str, Any]]:
        """Score key term candidates using multiple factors."""
        # Count frequency of each term
        term_freq = Counter(candidate["text"] for candidate in candidates)
        total_candidates = len(candidates)
        
        scored_terms = []
        
        for candidate in candidates:
            score = 0
            term_text = candidate["text"]
            
            # Frequency score (normalized)
            freq = term_freq[term_text]
            freq_score = freq / total_candidates if total_candidates > 0 else 0
            score += freq_score * 3
            
            # POS-based scoring
            if candidate["pos"] == "PROPN":
                score += 2  # Proper nouns are often important
            elif candidate["pos"] == "NOUN":
                score += 1.5
            elif candidate["pos"] == "NOUN_PHRASE":
                score += 1.8  # Noun phrases are often key concepts
            elif candidate["pos"] == "ADJ":
                score += 0.8
            elif candidate["pos"] == "VERB":
                score += 1
            
            # Entity bonus
            if candidate["is_entity"]:
                score += 2
            
            # Length bonus for multi-word terms
            word_count = len(term_text.split())
            if word_count > 1:
                score += word_count * 0.5
            
            # Capitalization bonus (for original text)
            if candidate["original"][0].isupper():
                score += 0.5
            
            scored_terms.append({
                "text": candidate["original"],
                "lemma": term_text,
                "pos": candidate["pos"],
                "score": round(score, 3),
                "frequency": freq,
                "is_entity": candidate["is_entity"],
                "entity_type": candidate["entity_type"]
            })
        
        return scored_terms
    
    def extract_simple(self, text: str) -> List[Dict[str, str]]:
        """
        Simple extraction that returns just the entities list.
        
        Args:
            text (str): The text to analyze
            
        Returns:
            List of entities with text and label
        """
        if not text or not text.strip():
            return []
        
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_
            })
        
        return entities


# Example usage and testing
if __name__ == "__main__":
    # Initialize the extractor
    extractor = EntityExtractor()
    
    # Test phrases
    test_phrases = [
        "Barack Obama was born in Honolulu.",
        "Apple Inc. was founded by Steve Jobs and Steve Wozniak in 1976.",
        "The quick brown fox jumps over the lazy dog.",
        "Elon Musk works at Tesla and develops innovative electric vehicles.",
        "The Eiffel Tower is located in Paris.",
        "New York is a big city with many tall buildings.",
        "Ellen is 70 years old and from Washington D.C.",
        "Machine learning algorithms can analyze large datasets to identify patterns and make predictions about future trends."
    ]
    
    print("=== Named Entity and Key Term Extractor Test ===\n")
    
    for i, phrase in enumerate(test_phrases, 1):
        print(f"Test {i}: '{phrase}'")
        result = extractor.extract(phrase)
        
        # Pretty print the JSON result
        print(json.dumps(result, indent=2))
        print("-" * 60)
        
    # Example of simple extraction
    print("\n=== Simple Extraction Example ===")
    simple_result = extractor.extract_simple("Barack Obama visited Paris last year.")
    print(json.dumps(simple_result, indent=2))
    
    # Example focusing on key terms
    print("\n=== Key Terms Only Example ===")
    tech_text = "Artificial intelligence and machine learning are transforming healthcare by enabling predictive analytics and personalized treatment recommendations."
    key_terms_result = extractor.extract(tech_text, extract_key_terms=True, max_key_terms=8)
    print(f"Text: '{tech_text}'")
    print("Key Terms Found:")
    for term in key_terms_result['key_terms']:
        print(f"  - {term['text']} (score: {term['score']}, pos: {term['pos']})")