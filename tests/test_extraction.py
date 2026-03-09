# tests/test_extraction.py
import time
import sys
import os
import json

# ⏱️ Iniciar medición de tiempo
inicio = time.time()

# Add the root directory to the system path to allow absolute imports from 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.controller.presentation_controller import PresentationController

def run_test():
    # Initialize the controller
    controller = PresentationController()
    
    # Path to your specific PPTX file
    test_file_path = r"C:\Users\kgonz\Desktop\TT\Presentaciones\Curso_Redes_Computador.pptx"
    
    try:
        print("=== Starting Presentation Processing Test ===")
        extracted_data = controller.process_new_presentation(test_file_path)
        
        print("\n=== Extraction Results ===")
        # Print the results nicely formatted as JSON
        print(json.dumps(extracted_data, indent=4, ensure_ascii=False))
        print("\n=== Test Completed Successfully ===")
        
    except Exception as e:
        print(f"\n[Error] Test failed: {e}")

if __name__ == "__main__":
    run_test()
    
    
# ⏱️ Finalizar medición
fin = time.time()
print(f"\nTiempo de ejecución: {fin - inicio:.4f} segundos")