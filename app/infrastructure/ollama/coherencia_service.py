import requests
import re

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "mistral"
TIMEOUT_SEG = 15

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

def verificar_coherencia_titulo(titulo, contenido):
    """
    Pide a Mistral una calificación numérica de coherencia/claridad.
    Returns: int (1-10) o None si hay error.
    """
    # Si no hay contenido, evaluamos la claridad intrínseca del título
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
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        respuesta = response.json().get("response", "").strip()
        
        # Extraemos el número de la respuesta (por si Mistral añade texto extra)
        numeros = re.findall(r'\d+', respuesta)
        if numeros:
            score = int(numeros[0])
            return min(10, max(1, score)) # Aseguramos que esté entre 1 y 10
        return 5 # Fallback si no detecta número
        
    except Exception as e:
        print(f"[ollama] Error en evaluación HSS: {e}")
        return None