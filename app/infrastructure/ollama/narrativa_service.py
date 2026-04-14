# app/infrastructure/ollama/narrativa_service.py
import requests
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO     = "mistral"

_PROMPT_NTS = """[INST] Eres un experto en pedagogía universitaria. 
Tu tarea es evaluar la SECUENCIA LÓGICA o HILO CONDUCTOR entre dos diapositivas de una clase.

Diapositiva A: {t1}
Diapositiva B: {t2}

¿B es una continuación, ejemplo, o concepto relacionado con A? 
Responde ÚNICAMENTE con un número del 1 al 10 (10 es conexión perfecta, 1 es cambio de tema total). No escribas nada más. [/INST]"""

def verificar_hilo_narrativo(texto1, texto2):
    """
    Consulta a Mistral para validar si hay un hilo narrativo semántico.
    """
    # Acortamos texto para no saturar el contexto del modelo
    prompt = _PROMPT_NTS.format(t1=texto1[:1500], t2=texto2[:1500])
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            },
            timeout=15
        )
        response.raise_for_status()
        output = response.json().get("response", "").strip()
        
        # Extraer el primer número que aparezca en la respuesta
        match = re.search(r'\d+', output)
        if match:
            return int(match.group())
        return 5 # Valor neutro si el modelo no responde un número
        
    except Exception as e:
        print(f"[ollama_nts] Error: {e}")
        return None