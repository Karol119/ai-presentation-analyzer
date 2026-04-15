# app/infrastructure/gemini/gemini_client.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configuración
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

# Usamos gemini-1.5-flash por ser rápido y económico (o gemini-1.5-pro)
MODEL_NAME = "gemini-1.5-flash"

def inicializar_gemini() -> bool:
    """Verifica que la API Key esté presente."""
    return bool(API_KEY)

def generar_respuesta_gemini(prompt: str, json_mode: bool = False) -> str:
    """
    Envía un prompt a Gemini y devuelve el texto de la respuesta.
    """
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Configuración de generación (opcional)
    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    try:
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        return response.text
    except Exception as e:
        print(f"Error al llamar a Gemini: {e}")
        return ""