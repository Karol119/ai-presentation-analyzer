import os
import re
import sys
import time
import socket
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


def verify_ai_connection():
    """Verifica la conectividad ANTES de empezar a procesar la presentación."""
    if ACTIVE_MODEL == "gemini":
        try:
            # Intentamos conectar al DNS de Google (8.8.8.8) por el puerto 53. 
            # Timeout de 3 segundos para no hacer esperar al usuario.
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except OSError as e:
            raise RuntimeError("SIN CONEXIÓN A INTERNET: El modelo en la nube (Gemini) requiere conexión a la red. Verifica tu Wi-Fi e intenta de nuevo.") from e
    else:
        # Si es Ollama (Local), usamos tu función que ya existía para encenderlo
        try:
            _ensure_ollama_is_running()
        except Exception as e:
            raise RuntimeError(f"ERROR CON OLLAMA LOCAL: No se pudo encender el motor. {str(e)}") from e
        
        
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
    except requests.exceptions.ConnectionError as e:
        # ERROR CRÍTICO: Ollama apagado
        raise RuntimeError("OLLAMA ESTÁ APAGADO. Por favor abre la aplicación de Ollama en tu PC y vuelve a intentar.") from e
    except requests.exceptions.HTTPError as e:
        # ERROR CRÍTICO: Modelo no encontrado
        raise RuntimeError(f"ERROR: ¿Estás seguro de que el modelo '{model_name}' está instalado en Ollama?") from e
    except Exception as e:
        raise RuntimeError(f"Error inesperado con Ollama: {e}") from e

def _query_gemini(prompt: str, temperature: float) -> str:
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature)
        )
        return response.text.strip()
    except Exception as e:
        error_str = str(e)
        
        if "Quota" in error_str or "429" in error_str or "exhausted" in error_str.lower():
            # 1. Extraemos los segundos exactos de espera que pide Google
            wait_match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str)
            tiempo_espera = f"{round(float(wait_match.group(1)))} segundos" if wait_match else "1 minuto"
            
            # 2. Identificamos qué cuota específica se agotó
            tipo_cuota = "Límite general de uso"
            if "TokensPerMinute" in error_str or "TPM" in error_str:
                tipo_cuota = "Tokens por Minuto (Se renueva en un minuto)"
            elif "PerDay" in error_str:
                tipo_cuota = "Peticiones Diarias (Se renueva a la medianoche)"
            elif "PerMinute" in error_str:
                tipo_cuota = "Peticiones por Minuto (Se renueva en un minuto)"

            # Lanzamos el error con la información exacta
            raise RuntimeError(
                f"LÍMITE DE CUOTA GEMINI: Se agotó tu cuota de '{tipo_cuota}'. "
                f"Google solicita esperar exactamente {tiempo_espera} antes de reintentar."
            ) from e
            
        elif "503" in error_str or "unavailable" in error_str.lower():
            raise RuntimeError("ERROR DE SERVIDOR: Gemini no está disponible temporalmente.") from e
        elif "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
            raise RuntimeError("CLAVE INVÁLIDA: La API Key de Gemini es incorrecta. Revisa tu archivo .env.") from e
        else:
            raise RuntimeError(f"Error crítico con la IA de Google: {error_str}") from e