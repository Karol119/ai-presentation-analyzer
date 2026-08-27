# app/infrastructure/ai/llm_provider.py
import os
import re
import requests
from importlib import import_module
from pathlib import Path
from dotenv import load_dotenv

try:
    genai = import_module("google.generativeai")
except ImportError as e:
    raise RuntimeError(
        "Falta la dependencia de Gemini. Instala el paquete "
        "'google-generativeai' en el entorno activo."
    ) from e

ruta_actual = Path(__file__).resolve()
ruta_raiz = ruta_actual.parent.parent.parent.parent
ruta_env = ruta_raiz / ".env"

load_dotenv(dotenv_path=ruta_env, override=True)

CLAVE_API_GEMINI = os.getenv("GEMINI_API_KEY", "")
MODELO_GEMINI = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

genai.configure(api_key=CLAVE_API_GEMINI)
print(f"\n[PROVEEDOR IA] Conectado a la NUBE: Google Gemini — Modelo: '{MODELO_GEMINI}'")


def verificar_conexion_ia():
    """Verifica la conectividad REAL ANTES de empezar a procesar la presentación."""
    try:
        requests.get("https://generativelanguage.googleapis.com", timeout=3)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            "SIN CONEXIÓN A INTERNET: No se puede alcanzar el servidor de Gemini. "
            "Verifica tu Wi-Fi e intenta de nuevo."
        ) from e


def consultar_modelo(prompt: str, system_instruction: str = "") -> str:
    """
    Envía una petición a Gemini.

    NOTA: A partir de gemini-3.5-flash-lite, los parámetros temperature, top_p
    y top_k están deprecados y son ignorados por la API. El determinismo se
    controla mediante system_instruction con reglas explícitas de formato.
    Fuente: Google AI release notes, julio 2026.

    Args:
        prompt: El prompt principal con los datos y las instrucciones de tarea.
        system_instruction: Instrucción de sistema que define el rol y el formato
                            de respuesta. Se procesa ANTES que el prompt y es
                            el mecanismo oficial de determinismo en Gemini 3.x.
    """
    return _consultar_gemini(prompt, system_instruction)


def _consultar_gemini(prompt: str, system_instruction: str) -> str:
    try:
        # Si hay system_instruction, se inicializa el modelo con ella.
        # Gemini la procesa como contexto base antes de leer el prompt,
        # lo que produce respuestas de formato más consistente entre llamadas.
        if system_instruction:
            modelo = genai.GenerativeModel(
                MODELO_GEMINI,
                system_instruction=system_instruction
            )
        else:
            modelo = genai.GenerativeModel(MODELO_GEMINI)

        respuesta = modelo.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                # temperature, top_p, top_k: ELIMINADOS.
                # Están deprecados en gemini-3.5-flash-lite y gemini-3.6-flash+.
                # La API los acepta sin error pero los ignora completamente.
                # En versiones futuras devolverán HTTP 400.
                # El control de determinismo se hace por system_instruction.
            ),
            request_options={"retry": None}
        )
        return respuesta.text.strip()

    except Exception as e:
        error_str = str(e)

        if "Failed to establish" in error_str or "unreachable" in error_str or "aborted" in error_str:
            raise RuntimeError(
                "SE PERDIÓ LA CONEXIÓN A INTERNET durante el análisis. Verifica tu red."
            ) from e

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
            raise RuntimeError(
                "ERROR DE SERVIDOR: Gemini no está disponible temporalmente."
            ) from e

        elif "API_KEY_INVALID" in error_str or "not valid" in error_str:
            raise RuntimeError(
                "CLAVE INVÁLIDA: La API Key de Gemini es incorrecta. Revisa tu archivo .env."
            ) from e

        else:
            raise RuntimeError(f"Error crítico con la IA de Google: {error_str}") from e