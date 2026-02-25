# app/data/presentation_repository.py
import os
import shutil
import json

class PresentationRepository:
    def __init__(self):
        self.storage_path = os.path.join(os.getcwd(), "storage", "presentaciones")
        os.makedirs(self.storage_path, exist_ok=True)

    def is_presentation_registered(self, folder_name: str) -> bool:
        """Checks if a folder for this presentation already exists."""
        folder_path = os.path.join(self.storage_path, folder_name)
        return os.path.exists(folder_path)

    def get_all_registered_presentations(self) -> dict:
        """
        Iterates through all presentation folders and reads their vectorization.json.
        Returns a dictionary: { "folder_name": "combined_titles" }
        """
        registry = {}
        for folder_name in os.listdir(self.storage_path):
            folder_path = os.path.join(self.storage_path, folder_name)
            
            # Check if it's a directory
            if os.path.isdir(folder_path):
                json_path = os.path.join(folder_path, "vectorization.json")
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Extract the combined titles for similarity comparison
                        registry[folder_name] = data.get("combined_titles", "")
                        
        return registry

    def save_presentation_data(self, source_path: str, filename: str, extracted_data: list, combined_titles: str) -> str:
        """
        Creates a dedicated folder, copies the PPTX, and saves the JSON data.
        """
        # Remove the .pptx extension to use as folder name
        folder_name = os.path.splitext(filename)[0]
        presentation_folder = os.path.join(self.storage_path, folder_name)
        
        # 1. Create the dedicated folder
        os.makedirs(presentation_folder, exist_ok=True)
        
        # 2. Copy the PPTX into the folder
        destination_path = os.path.join(presentation_folder, filename)
        shutil.copy2(source_path, destination_path)
        
        # 3. Save the JSON file with the data and titles
        json_path = os.path.join(presentation_folder, "vectorization.json")
        json_data = {
            "filename": filename,
            "combined_titles": combined_titles,
            "extracted_data": extracted_data
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
            
        return presentation_folder