import os
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# --- LECTURA DE CONFIGURACIÓN ---
ACTIVE_MODEL = os.getenv("ACTIVE_AI_MODEL", "mistral").lower()
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api/generate")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Si el modelo activo es Gemini, inicializamos su SDK
if ACTIVE_MODEL == "gemini":
    genai.configure(api_key=GEMINI_API_KEY)

def query_model(prompt: str, temperature: float = 0.0) -> str:
    """
    Punto de entrada único. Enruta la petición al modelo configurado en el .env.
    Cualquier métrica que necesite IA llamará a esta función.
    """
    if ACTIVE_MODEL == "gemini":
        return _query_gemini(prompt, temperature)
    else:
        # Si no es Gemini, asumimos que es un modelo local en Ollama (Mistral/Llama)
        return _query_ollama(prompt, ACTIVE_MODEL, temperature)

def _query_ollama(prompt: str, model_name: str, temperature: float) -> str:
    """Ejecuta la petición contra un modelo local en Ollama."""
    try:
        # Formato optimizado para modelos instruccionales locales
        formatted_prompt = f"[INST] {prompt} [/INST]"
        
        payload = {
            "model": model_name,
            "prompt": formatted_prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"[AI Provider] Error con Ollama ({model_name}): {e}")
        return ""

def _query_gemini(prompt: str, temperature: float) -> str:
    """Ejecuta la petición contra la API de Google Gemini en la nube."""
    try:
        # Usamos gemini-1.5-flash por ser extremadamente rápido y excelente para clasificación
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AI Provider] Error con Gemini: {e}")
        return ""