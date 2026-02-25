# app/core/logic/text_extractor.py
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

class TextExtractor:
    def extract_from_pptx(self, file_path: str) -> list[dict]:
        """
        Reads a PPTX file and extracts text separated by title and content.
        Also detects if there are images in the slide.
        Returns a list of dictionaries containing slide information.
        """
        extracted_data = []
        
        try:
            prs = Presentation(file_path)

            for i, slide in enumerate(prs.slides):
                slide_info = {
                    "slide_number": i + 1,
                    "title": "(No title defined)",
                    "content": [],
                    "images": []  # New list to store image names
                }
                
                # 1. Extract title
                if slide.shapes.title:
                    slide_info["title"] = slide.shapes.title.text.strip()

                # 2. Extract content and check for images
                for shape in slide.shapes:
                    # Skip the title shape as it is already extracted
                    if shape == slide.shapes.title:
                        continue
                        
                    # Check if the shape has text
                    if hasattr(shape, "text") and shape.text.strip():
                        clean_text = shape.text.replace('\n', ' ').strip()
                        slide_info["content"].append(clean_text)
                        
                    # Check if the shape is a picture/image
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        # shape.name holds the internal name (e.g., "Picture 1" or "logo.png")
                        slide_info["images"].append(shape.name)
                
                # 3. Handle slides that only have images (no text)
                if not slide_info["content"] and slide_info["images"]:
                    image_names = ", ".join(slide_info["images"])
                    slide_info["content"].append(f"[Slide contains only images: {image_names}]")
                
                extracted_data.append(slide_info)
                
        except Exception as e:
            print(f"Error extracting data from {file_path}: {e}")
            
        return extracted_data