import os
import sys
import time
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# --- 1. LECTURA FORZADA DEL .ENV ---
ruta_actual = Path(__file__).resolve()
ruta_raiz = ruta_actual.parent.parent.parent.parent 
ruta_env = ruta_raiz / ".env"

# Forzamos lectura (override=True) para ignorar caché de consola
load_dotenv(dotenv_path=ruta_env, override=True)

# --- 2. CONFIGURACIÓN ---
ACTIVE_MODEL = os.getenv("ACTIVE_AI_MODEL", "qwen3:1.7b").lower().strip()
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api/generate")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- 3. AUTO-ENCENDIDO DE OLLAMA ---
def _ensure_ollama_is_running():
    """Verifica si Ollama está activo. Si no, lo enciende silenciosamente en segundo plano."""
    base_url = OLLAMA_URL.replace("/api/generate", "")
    
    try:
        # 1. Intentamos hacer un 'ping' rápido al servidor local de Ollama (1 segundo de espera)
        requests.get(base_url, timeout=1)
        # Si no da error, significa que Ollama ya estaba prendido. No hacemos nada.
        
    except requests.exceptions.ConnectionError:
        print("[AI PROVIDER] Ollama está apagado. Encendiendo el motor local automáticamente...")
        try:
            # 2. Configuramos el subproceso para que no abra ventanas emergentes en Windows
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            # 3. Encendemos el servidor de Ollama en segundo plano (equivalente a correr 'ollama serve')
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, # Ocultamos los textos de consola de Ollama
                stderr=subprocess.DEVNULL, # Ocultamos los errores de Ollama
                **kwargs
            )
            
            # 4. Le damos a la computadora 3 segundos para arrancar el motor antes de continuar
            time.sleep(3)
            print("[AI PROVIDER] Motor de Ollama inicializado con éxito.")
            
        except FileNotFoundError:
            print("[AI PROVIDER ERROR] No se pudo encender Ollama. ¿Asegúrate de que está instalado en tu PC?")

# --- 4. INICIALIZACIÓN DE LA IA ---
if ACTIVE_MODEL == "gemini":
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"\n[AI PROVIDER] Conectado a la NUBE: Google Gemini")
else:
    # Si NO es Gemini, encendemos Ollama automáticamente
    _ensure_ollama_is_running()
    print(f"\n[AI PROVIDER] Conectado a OLLAMA LOCAL. Modelo activo: '{ACTIVE_MODEL}'")


# --- 5. FUNCIONES DE EJECUCIÓN ---
def query_model(prompt: str, temperature: float = 0.0) -> str:
    """Enruta la petición al modelo configurado en el .env."""
    if ACTIVE_MODEL == "gemini":
        return _query_gemini(prompt, temperature)
    else:
        return _query_ollama(prompt, ACTIVE_MODEL, temperature)

def _query_ollama(prompt: str, model_name: str, temperature: float) -> str:
    try:
        formatted_prompt = f"[INST] {prompt} [/INST]"
        payload = {
            "model": model_name,
            "prompt": formatted_prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.HTTPError as e:
        print(f"[AI Provider] Error 404: ¿Estás seguro de que el modelo '{model_name}' está descargado en Ollama?")
        return ""
    except Exception as e:
        print(f"[AI Provider] Error general con Ollama ({model_name}): {e}")
        return ""

def _query_gemini(prompt: str, temperature: float) -> str:
    try:
        # Usamos gemini-pro para evitar el error 404 de versiones de librería antiguas
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature)
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AI Provider] Error con Gemini: {e}")
        return ""