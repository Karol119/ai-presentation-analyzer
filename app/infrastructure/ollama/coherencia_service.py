"""
Agregar esta función a ollama_service.py
para verificar coherencia título-contenido cuando el solapamiento léxico
no es concluyente.
"""

import requests

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "llama3.2"
TIMEOUT_SEG = 15

_PROMPT_COHERENCIA = """Eres un evaluador de presentaciones académicas universitarias.

Determina si el título de una diapositiva es coherente con su contenido.
Un título es coherente si describe, resume o introduce el tema del contenido.

RESPONDE ÚNICAMENTE con: si  (si es coherente)  o  no  (si no lo es)

Título: {titulo}
Contenido: {contenido}

¿El título es coherente con el contenido?"""


def verificar_coherencia_titulo(titulo, contenido):
    """
    Verifica si el título es coherente con el contenido via LLM.

    Returns:
        True si coherente, False si no, None si error.
    """
    prompt = _PROMPT_COHERENCIA.format(
        titulo=titulo[:200],
        contenido=contenido[:400]
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 5}
            },
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        respuesta = response.json().get("response", "").strip().lower()
        if "si" in respuesta or "sí" in respuesta:
            return True
        if "no" in respuesta:
            return False
        return None

    except Exception as e:
        print(f"[ollama] Error coherencia: {e}")
        return None