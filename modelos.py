import os
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Buscando modelos compatibles con tu API Key...\n")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods and 'flash-lite' in m.name.lower():
        print(f"ID exacto para usar en el código: '{m.name.replace('models/', '')}'")