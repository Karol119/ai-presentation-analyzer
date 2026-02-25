# app/core/controller/presentation_controller.py
import os
from app.data.presentation_repository import PresentationRepository
from app.core.logic.text_extractor import TextExtractor
from app.core.logic.metrics.cosine_similarity import TextSimilarityMetric

class PresentationController:
    def __init__(self):
        self.repository = PresentationRepository()
        self.extractor = TextExtractor()
        self.similarity_metric = TextSimilarityMetric()
        self.SIMILARITY_THRESHOLD = 0.85 

    def process_new_presentation(self, original_file_path: str) -> list[dict]:
        if not os.path.exists(original_file_path):
            raise FileNotFoundError(f"Original file not found at: {original_file_path}")

        filename = os.path.basename(original_file_path)
        folder_name = os.path.splitext(filename)[0] # Extract name without .pptx

        # EXCEPTION 1: Check if the folder already exists
        if self.repository.is_presentation_registered(folder_name):
            raise FileExistsError(f"Exception: A presentation named '{filename}' already exists.")

        # Extract text to check for redundancy BEFORE saving
        print(f"[System] Analyzing content for potential redundancy...")
        temp_data = self.extractor.extract_from_pptx(original_file_path)
        
        # Combine all titles into a single document string
        new_presentation_titles = " ".join([slide["title"] for slide in temp_data if slide["title"] != "(No title defined)"])
        
        # EXCEPTION 2: Check for semantic redundancy (Cosine Similarity)
        existing_presentations = self.repository.get_all_registered_presentations()
        
        for saved_folder, saved_titles in existing_presentations.items():
            similarity = self.similarity_metric.calculate_similarity(new_presentation_titles, saved_titles)
            
            if similarity >= self.SIMILARITY_THRESHOLD:
                raise ValueError(f"Exception: Redundant data. The content is {similarity*100:.2f}% similar to an existing presentation in folder '{saved_folder}'.")

        # If it passes both exceptions, save the file and its JSON in the new folder
        saved_folder_path = self.repository.save_presentation_data(
            source_path=original_file_path, 
            filename=filename, 
            extracted_data=temp_data, 
            combined_titles=new_presentation_titles
        )
        print(f"[System] Presentation successfully saved at: {saved_folder_path}")
        
        return temp_data