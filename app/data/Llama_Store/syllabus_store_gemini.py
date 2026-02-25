# app/data/Llama_Store/syllabus_store_gemini.py

import os
from llama_index.core import SimpleDirectoryReader
from llama_index.embeddings.gemini import GeminiEmbedding

class SyllabusStoreGemini:
    """
    Data Layer: Syllabus vectorization using Google Gemini API (Cloud).
    Requires internet connection and API tokens.
    """

    def __init__(self, syllabus_dir="storage/temarios"):
        self.syllabus_dir = syllabus_dir
        self.syllabus_embedding = None
        
        # 1. Fetch the secret key from the .env file
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API Key Error: GEMINI_API_KEY is missing in the environment.")

        # 2. Initialize the cloud-based mathematical brain
        self.embed_model = GeminiEmbedding(model_name="models/embedding-001", api_key=api_key)

    def load_and_vectorize_syllabus(self):
        """
        Reads the PDF and converts it to a master mathematical vector.
        """
        if not os.path.exists(self.syllabus_dir):
            os.makedirs(self.syllabus_dir)
            raise FileNotFoundError(f"Directory created at '{self.syllabus_dir}'. Please add the PDF.")

        # 3. Read the PDF document automatically
        documents = SimpleDirectoryReader(self.syllabus_dir).load_data()
        
        if not documents:
            raise ValueError("Empty Directory: No syllabus (PDF) found to index.")

        # 4. Join all text pages into a single large string
        syllabus_text = " ".join([doc.text for doc in documents])
        
        # 5. Send text to Gemini to get the vector numbers
        self.syllabus_embedding = self.embed_model.get_text_embedding(syllabus_text)
        return True

    def get_text_embedding(self, presentation_text):
        """
        Converts the presentation text into a numerical vector for comparison.
        """
        if not presentation_text:
             raise ValueError("The presentation text is empty.")
             
        return self.embed_model.get_text_embedding(presentation_text)