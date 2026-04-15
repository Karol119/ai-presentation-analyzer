# app/infrastructure/ollama/ollama_service.py
import requests
from app.infrastructure.ollama.ollama_client import generar_respuesta

_TIPOS_VALIDOS = {"portada", "indice", "referencias", "cierre", "contenido"}

_PROMPT = """Eres un clasificador de diapositivas académicas universitarias.

Clasifica la diapositiva en EXACTAMENTE UNO de estos tipos:
  portada     → portada principal, título del curso, datos del autor
  indice      → lista de temas, agenda, tabla de contenido
  referencias → bibliografía, fuentes, webgrafía, citas
  cierre      → cierre, gracias, preguntas, conclusiones
  contenido   → contenido educativo real del tema

Responde ÚNICAMENTE con una de esas cinco palabras, en minúsculas, sin explicación.

Título: {titulo}
Contenido: {contenido}

Tipo:"""
def clasificar_tipo_diapositiva(slide_data):
    titulo   = slide_data.get("title", "").strip() or "(sin título)"
    contenido = " | ".join(slide_data.get("content", []))[:500]

    prompt = _PROMPT.format(
        titulo=titulo,
        contenido=contenido or "(sin contenido)"
    )

    try:
        response = generar_respuesta(
            prompt=prompt,
            options={"temperature": 0.0, "num_predict": 10},
            timeout=15
        )
        response.raise_for_status()
        tipo_raw = response.json().get("response", "").strip().lower()
        return _parsear_tipo(tipo_raw)

    except requests.exceptions.ConnectionError:
        print("[ollama_clasificador] No disponible")
        return None
    except Exception as e:
        print(f"[ollama_clasificador] Error: {e}")
        return None

def _parsear_tipo(respuesta):
    limpio = respuesta.strip().strip(".,;:\"'").lower()
    if limpio in _TIPOS_VALIDOS:
        return limpio
    for tipo in _TIPOS_VALIDOS:
        if tipo in limpio:
            return tipo
    return None