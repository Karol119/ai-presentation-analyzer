# app/data/Llama_Store/syllabus_store_hf.py

import os
import json
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

class SyllabusStoreHF:
    """
    Data Layer: Syllabus vectorization using a Local HuggingFace Model and Structured JSON.
    """

    def __init__(self, json_path="storage/temarios/temario_comunicacion.json"):
        self.json_path = json_path
        # Aquí guardaremos el vector de CADA subtema
        self.syllabus_vectors = {} 
        self.syllabus_structure = {}
        
        # Inicializamos el cerebro matemático local
        self.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

    def load_and_vectorize_syllabus(self):
        """
        Lee el JSON estructurado y vectoriza tema por tema individualmente.
        """
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"No se encontró el archivo JSON en {self.json_path}")

        with open(self.json_path, 'r', encoding='utf-8') as file:
            self.syllabus_structure = json.load(file)

        # Recorremos cada unidad y cada subtema para crear su propio vector
        for unidad, temas in self.syllabus_structure.items():
            for id_tema, nombre_tema in temas.items():
                texto_a_vectorizar = f"{unidad} {id_tema} {nombre_tema}"
                # Generamos el vector y lo guardamos con su identificador único
                vector = self.embed_model.get_text_embedding(texto_a_vectorizar)
                self.syllabus_vectors[f"{unidad} - {id_tema}"] = {
                    "nombre": nombre_tema,
                    "vector": vector
                }
        
        return True

    def get_text_embedding(self, presentation_text):
        if not presentation_text:
             raise ValueError("El texto de la presentación está vacío.")
        return self.embed_model.get_text_embedding(presentation_text)