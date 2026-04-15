# app/infrastructure/ollama/coherencia_service.py

from app.infrastructure.ollama.ollama_client import generar_respuesta
import re

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
    cuerpo_para_llm = contenido[:1500] if contenido.strip() else "(Sin contenido adicional)"
    prompt = _PROMPT_EVALUACION_HSS.format(titulo=titulo, contenido=cuerpo_para_llm)

    try:
        # Usamos el cliente centralizado
        response = generar_respuesta(
            prompt=prompt, 
            options={"temperature": 0.0, "num_predict": 5},
            timeout=15
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