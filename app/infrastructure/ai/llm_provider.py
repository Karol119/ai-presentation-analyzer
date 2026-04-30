# app/infrastructure/ai/llm_provider.py
import os
import re
import sys
import time
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

ruta_actual = Path(__file__).resolve()
ruta_raiz = ruta_actual.parent.parent.parent.parent 
ruta_env = ruta_raiz / ".env"

load_dotenv(dotenv_path=ruta_env, override=True)

MODELO_ACTIVO = os.getenv("ACTIVE_AI_MODEL", "gemini").lower().strip()
URL_OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api/generate")
CLAVE_API_GEMINI = os.getenv("GEMINI_API_KEY", "")

def verificar_conexion_ia():
    """Verifica la conectividad REAL ANTES de empezar a procesar la presentación."""
    if MODELO_ACTIVO == "gemini":
        try:
            requests.get("https://generativelanguage.googleapis.com", timeout=3)
        except requests.exceptions.RequestException as e:
            raise RuntimeError("SIN CONEXIÓN A INTERNET: No se puede alcanzar el servidor de Gemini. Verifica tu Wi-Fi e intenta de nuevo.") from e
    else:
        try:
            _asegurar_ollama_encendido()
        except Exception as e:
            raise RuntimeError(f"ERROR CON OLLAMA LOCAL: No se pudo encender el motor. {str(e)}") from e
        
def _asegurar_ollama_encendido():
    """Verifica si Ollama está activo. Si no, lo enciende silenciosamente en segundo plano."""
    url_base = URL_OLLAMA.replace("/api/generate", "")
    
    try:
        requests.get(url_base, timeout=3)
    except requests.exceptions.RequestException: 
        print("[PROVEEDOR IA] Ollama está inactivo o cargando. Encendiendo el motor local automáticamente...")
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs
            )
            
            time.sleep(5)
            print("[PROVEEDOR IA] Motor de Ollama inicializado con éxito.")
            
        except FileNotFoundError:
            print("[ERROR PROVEEDOR IA] No se pudo encender Ollama. ¿Asegúrate de que está instalado en tu PC?")

if MODELO_ACTIVO == "gemini":
    import google.generativeai as genai
    genai.configure(api_key=CLAVE_API_GEMINI)
    print(f"\n[PROVEEDOR IA] Conectado a la NUBE: Google Gemini")
else:
    _asegurar_ollama_encendido()
    print(f"\n[PROVEEDOR IA] Conectado a OLLAMA LOCAL. Modelo activo: '{MODELO_ACTIVO}'")

def consultar_modelo(prompt: str, temperatura: float = 0.0) -> str:
    """Enruta la petición al modelo configurado en el .env."""
    if MODELO_ACTIVO == "gemini":
        return _consultar_gemini(prompt, temperatura)
    else:
        return _consultar_ollama(prompt, MODELO_ACTIVO, temperatura)

def _consultar_ollama(prompt: str, nombre_modelo: str, temperatura: float) -> str:
    try:
        prompt_formateado = f"[INST] {prompt} [/INST]"
        carga_util = {
            "model": nombre_modelo,
            "prompt": prompt_formateado,
            "stream": False,
            "options": {"temperature": temperatura}
        }
        
        respuesta = requests.post(URL_OLLAMA, json=carga_util, timeout=600)
        respuesta.raise_for_status()
        return respuesta.json().get("response", "").strip()
        
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError("OLLAMA ESTÁ APAGADO. Por favor abre la aplicación de Ollama en tu PC y vuelve a intentar.") from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"ERROR: ¿Estás seguro de que el modelo '{nombre_modelo}' está instalado en Ollama?") from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError("TIEMPO AGOTADO: Ollama tardó demasiado en responder (más de 10 minutos). El modelo podría estar saturado.") from e
    except Exception as e:
        raise RuntimeError(f"Error inesperado con Ollama: {e}") from e

def _consultar_gemini(prompt: str, temperatura: float) -> str:
    try:
        modelo = genai.GenerativeModel('gemini-2.5-flash-lite') 
        respuesta = modelo.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperatura),
            request_options={"retry": None}
        )
        return respuesta.text.strip()
    except Exception as e:
        error_str = str(e)
        if "Failed to establish" in error_str or "unreachable" in error_str or "aborted" in error_str:
            raise RuntimeError("SE PERDIÓ LA CONEXIÓN A INTERNET durante el análisis. Verifica tu red.") from e
        
        if "Quota" in error_str or "429" in error_str or "exhausted" in error_str.lower():
            match_espera = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str)
            tiempo_espera = f"{round(float(match_espera.group(1)))} segundos" if match_espera else "1 minuto"
            
            tipo_cuota = "Límite general de uso"
            if "TokensPerMinute" in error_str or "TPM" in error_str:
                tipo_cuota = "Tokens por Minuto (Se renueva en un minuto)"
            elif "PerDay" in error_str:
                tipo_cuota = "Peticiones Diarias (Se renueva a la medianoche)"
            elif "PerMinute" in error_str:
                tipo_cuota = "Peticiones por Minuto (Se renueva en un minuto)"

            raise RuntimeError(
                f"LÍMITE DE CUOTA GEMINI: Se agotó tu cuota de '{tipo_cuota}'. "
                f"Google solicita esperar exactamente {tiempo_espera} antes de reintentar."
            ) from e
            
        elif "503" in error_str or "unavailable" in error_str.lower():
            raise RuntimeError("ERROR DE SERVIDOR: Gemini no está disponible temporalmente.") from e
        elif "API_KEY_INVALID" in error_str or "not valid" in error_str:
            raise RuntimeError("CLAVE INVÁLIDA: La API Key de Gemini es incorrecta. Revisa tu archivo .env.") from e
        else:
            raise RuntimeError(f"Error crítico con la IA de Google: {error_str}") from e