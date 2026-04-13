import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO     = "mistral"

# ── Prompt principal ──────────────────────────────────────────────────────────
_PROMPT_DIAGNOSTICO_METRICO = """[INST]
Eres un revisor pedagógico de la Universidad. Tu tono es directo, breve y personal (usa "tú").

Tu tarea es analizar los resultados de las métricas de UNA diapositiva y generar retroalimentación
para el docente. No corrijas el contenido, solo explícale POR QUÉ falló y dale 1 o 2 sugerencias
concretas basadas en lo que él ya tiene escrito. Cada feedback debe tener entre 3 y 5 oraciones.

━━━━━━━━━━━━━━━━━━━━━━━━
DIAPOSITIVA ANALIZADA
━━━━━━━━━━━━━━━━━━━━━━━━
Título    : {titulo}
Contenido : {contenido}

━━━━━━━━━━━━━━━━━━━━━━━━
RESULTADOS DE MÉTRICAS
━━━━━━━━━━━━━━━━━━━━━━━━
ICD – Complejidad del contenido : {icd_valor} (zona: {icd_zona}) | Rango ideal: 4.0 – 6.0
WPS – Cantidad de palabras      : {wps_valor} palabras          | Máximo: 75
HSS – Estructura (encabezado)   : {hss_estado}
NTS – Hilo narrativo            : {nts_estado}
{nts_contexto_bloque}
━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS PARA CADA MÉTRICA
━━━━━━━━━━━━━━━━━━━━━━━━

ICD (Complejidad):
- Si está POR ENCIMA del rango (> 6.0): explica que el lenguaje está muy técnico para el público.
  Señala una o dos palabras del texto que sean muy especializadas y sugiere cambiarlas por
  equivalentes más claros sin perder el concepto (ej. "en vez de 'paradigma epistemológico'
  puedes escribir 'forma de ver el conocimiento'").
- Si está POR DEBAJO del rango (< 4.0): explica que el lenguaje está demasiado básico para
  nivel superior. Sugiere incorporar algún término técnico propio del tema que ya está en el texto.
- Si está dentro del rango: responde null.

WPS (Cantidad de palabras):
- Solo genera feedback si supera las 75 palabras.
- Calcula cuántas palabras sobran ({wps_valor} - 75) e indícaselo al docente.
- No le digas que resuma: explícale que puede dividir el contenido en varias diapositivas si
  hay más de una idea, o ajustar las frases más largas. Menciona una frase del texto que
  podría recortarse o moverse a otra diapositiva.
- Si tiene 75 o menos: responde null.

HSS (Estructura):
- Si el título no existe o no es coherente con el contenido: explica brevemente qué relación
  esperabas encontrar y qué se lee en su lugar.
- Si la estructura está bien: responde null.

NTS (Hilo narrativo):
- Si tienes contexto de diapositivas adyacentes: explica qué concepto o idea de la diapositiva
  actual no conecta bien con la anterior o la siguiente, y sugiere una forma de hacer ese puente.
- Si NO tienes contexto adyacente: explica que no se pudo evaluar el hilo porque la diapositiva
  está aislada, y recomiéndale revisar manualmente si hace transición desde la slide anterior.
- Si la narrativa está bien: responde null.

━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE RESPUESTA
━━━━━━━━━━━━━━━━━━━━━━━━
Responde ÚNICAMENTE con este JSON. Sin texto extra, sin bloques de código, sin comillas de markdown.
{{
  "icd": "Feedback de 3-5 oraciones o null",
  "wps": "Feedback de 3-5 oraciones o null",
  "hss": "Feedback de 3-5 oraciones o null",
  "nts": "Feedback de 3-5 oraciones o null"
}}
[/INST]"""

# Bloque de contexto NTS cuando hay diapositivas adyacentes disponibles
_NTS_CON_CONTEXTO = """
CONTEXTO NARRATIVO:
  Diapositiva anterior : {slide_prev}
  Diapositiva siguiente: {slide_next}
"""

_NTS_SIN_CONTEXTO = """
CONTEXTO NARRATIVO: No disponible (diapositiva analizada de forma aislada).
"""


# ── Función principal ─────────────────────────────────────────────────────────
def generar_diagnostico_metrico(slide_data: dict, metricas: dict,
                                 slide_prev: str = None, slide_next: str = None) -> dict:
    """
    Genera feedback por métrica para una diapositiva.

    Parámetros
    ----------
    slide_data  : dict con 'title' y 'content' (lista de strings) de la slide actual
    metricas    : dict con resultados de ICD, WPS, HSS y NTS
    slide_prev  : resumen de texto de la diapositiva anterior (None si no aplica)
    slide_next  : resumen de texto de la diapositiva siguiente (None si no aplica)
    """

    # Bloque de contexto NTS: solo se incluye si hay al menos una adyacente
    if slide_prev or slide_next:
        nts_contexto = _NTS_CON_CONTEXTO.format(
            slide_prev=slide_prev or "No disponible",
            slide_next=slide_next or "No disponible"
        )
    else:
        nts_contexto = _NTS_SIN_CONTEXTO

    prompt = _PROMPT_DIAGNOSTICO_METRICO.format(
        titulo           = slide_data.get("title", "Sin título"),
        contenido        = " ".join(slide_data.get("content", []))[:1200],
        icd_valor        = metricas.get("icd", {}).get("valor", "N/A"),
        icd_zona         = metricas.get("icd", {}).get("zona", "N/A"),
        wps_valor        = metricas.get("wps", {}).get("palabras", 0),
        hss_estado       = metricas.get("hss", {}).get("coherencia", "N/A"),
        nts_estado       = metricas.get("nts", {}).get("estado", "N/A"),
        nts_contexto_bloque = nts_contexto,
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False, "format": "json"},
            timeout=30
        )
        response.raise_for_status()
        return json.loads(response.json().get("response", "{}"))

    except (requests.RequestException, json.JSONDecodeError):
        return {}