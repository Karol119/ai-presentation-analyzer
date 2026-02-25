# app/core/logic/metrics/cosine_similarity.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class TextSimilarityMetric:
    def __init__(self):
        # TfidfVectorizer converts a collection of raw documents to a matrix of TF-IDF features.
        self.vectorizer = TfidfVectorizer()

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculates the cosine similarity between two strings of text.
        Returns a float between 0.0 (completely different) and 1.0 (identical).
        """
        # If either text is empty, they aren't similar
        if not text1.strip() or not text2.strip():
            return 0.0

        try:
            # Vectorize the texts and compute the matrix
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            
            # Calculate cosine similarity between the two vectors
            similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            
            return float(similarity_score[0][0])
        except ValueError:
            # Handles cases where texts only contain stop words or invalid vocabulary
            return 0.0