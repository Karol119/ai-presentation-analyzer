# app/infrastructure/ollama/coherencia_service.py
import requests
import re

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "mistral"
TIMEOUT_NORMAL = 15
TIMEOUT_CARGA  = 60 # Tiempo extra para la primera vez que se carga el modelo

# Nuevo prompt optimizado para Mistral con tags [INST]
_PROMPT_EVALUACION_HSS = """[INST] Eres un experto en pedagogía universitaria y diseño instruccional. 
Tu tarea es calificar la CALIDAD y COHERENCIA del título de una diapositiva respecto a su tema o contenido.

CRITERIOS DE CALIFICACIÓN (1 a 10):
- 10: El título es profesional, claro y describe perfectamente el contenido o el tema central.
- 7-9: Es coherente pero podría ser más preciso o usa sinónimos válidos.
- 4-6: El título es muy genérico o tiene poca relación con el texto.
- 1-3: El título no tiene ninguna relación con el contenido o es confuso.

TÍTULO: {titulo}
CONTENIDO: {contenido}

Responde ÚNICAMENTE con un número del 1 al 10. No escribas texto, ni explicaciones, ni puntos. [/INST]"""

def precargar_modelo():
    """
    Hace una petición mínima en frío para que Ollama cargue el modelo en RAM/VRAM.
    Puedes llamar esta función cuando arranque tu aplicación (ej. en el main.py).
    """
    try:
        print(f"[ollama] Iniciando/Cargando el modelo '{MODELO}' en memoria...")
        requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO,
                "prompt": "", 
                "options": {"num_predict": 1} # Petición mínima para no gastar recursos
            },
            timeout=TIMEOUT_CARGA
        )
        print("[ollama] Modelo cargado y listo para usarse.")
    except requests.exceptions.ConnectionError:
        print("[ollama] ERROR: El servicio de Ollama no está corriendo. Asegúrate de iniciar la app de Ollama o ejecutar 'ollama serve'.")
    except Exception as e:
        print(f"[ollama] Advertencia al precargar: {e}")

def verificar_coherencia_titulo(titulo, contenido):
    """
    Pide a Mistral una calificación numérica de coherencia/claridad.
    Returns: int (1-10) o None si hay error.
    """
    cuerpo_para_llm = contenido[:1500] if contenido.strip() else "(Sin contenido adicional en la diapositiva)"
    
    prompt = _PROMPT_EVALUACION_HSS.format(
        titulo=titulo,
        contenido=cuerpo_para_llm
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 5}
            },
            # Usamos el timeout largo por si no se hizo la precarga
            timeout=TIMEOUT_CARGA 
        )
        response.raise_for_status()
        respuesta = response.json().get("response", "").strip()
        
        numeros = re.findall(r'\d+', respuesta)
        if numeros:
            score = int(numeros[0])
            return min(10, max(1, score))
        return 5 
        
    except Exception as e:
        print(f"[ollama] Error en evaluación HSS: {e}")
        return None