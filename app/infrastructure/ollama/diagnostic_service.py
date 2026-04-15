# app/infrastructure/ollama/diagnostic_service.py
import requests
import json

from app.infrastructure.ollama.ollama_client import generar_respuesta

# Opciones fijas para respuestas deterministas
_OLLAMA_OPTIONS = {
    "temperature": 0,   # Sin aleatoriedad
    "seed":        42,  # Semilla fija → misma entrada = misma salida
    "top_k":       1,   # Solo el token más probable
    "top_p":       1.0,
}

_PROMPT_DIAGNOSTICO_METRICO = """[INST]
Eres un revisor pedagógico de Universidad. Tu tono es directo, breve y personal (usa "tú").

Tu tarea tiene tres partes:
  1. Analizar las métricas de la diapositiva y generar retroalimentación para el docente.
     No corrijas el contenido, solo explica POR QUÉ falló y da 1-2 sugerencias concretas
     basadas en lo que él ya escribió. Cada feedback: 3-5 oraciones.
  2. Generar exactamente {num_preguntas} pregunta(s) de comprensión que el docente pueda
     hacer a sus alumnos sobre el contenido de esta diapositiva. Deben ir de menor a mayor
     dificultad.
  3. Generar exactamente {num_curiosidades} dato(s) curioso(s) o interesante(s) relacionado(s)
     con el tema de la diapositiva. Deben ser datos verificables y sorprendentes de nivel licenciatura.

━━━━━━━━━━━━━━━━━━━━━━━━
DIAPOSITIVA ANALIZADA
━━━━━━━━━━━━━━━━━━━━━━━━
Título    : {titulo}
Contenido : {contenido}

━━━━━━━━━━━━━━━━━━━━━━━━
RESULTADOS DE MÉTRICAS
━━━━━━━━━━━━━━━━━━━━━━━━
ICD – Complejidad : {icd_valor} (zona: {icd_zona}) | Rango ideal: 4.0 – 6.5
WPS – Palabras    : {wps_valor}                    | Máximo: 75
HSS – Estructura  : {hss_estado}
NTS – Narrativa   : {nts_estado}
{nts_contexto_bloque}
━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS DE FEEDBACK POR MÉTRICA
━━━━━━━━━━━━━━━━━━━━━━━━

ICD (Complejidad):
- Si está POR ENCIMA del rango (> 6.5): explica que el lenguaje está muy técnico.
  Señala 1-2 palabras del texto y sugiere equivalentes más claros sin perder el concepto.
- Si está POR DEBAJO del rango (< 4.0): explica que el lenguaje está demasiado básico.
  Sugiere incorporar algún término técnico propio del tema que ya está en el texto.
- Si está dentro del rango: responde null.

WPS (Palabras):
- Solo genera feedback si supera las 75 palabras.
- Indica exactamente cuántas palabras sobran ({wps_valor} - 75).
- No digas que resuma: explica que puede dividir el contenido si hay más de una idea,
  o ajustar frases largas. Menciona una frase del texto como ejemplo.
- Si tiene 75 o menos: responde null.

HSS (Estructura):
- Si el título no existe: indica que es importante incluir un título claro y una o dos sugerencias de qué título funcionaría.
- Si el título no es coherente con el contenido: explica qué relación esperabas encontrar y qué ves en su lugar.
- Si la estructura está bien: responde null.

NTS (Narrativa):
- Si hay contexto adyacente: explica qué idea no conecta bien con la slide anterior
  o siguiente, y sugiere cómo hacer ese puente.
- Si NO hay contexto: indica que no se pudo evaluar por estar aislada, y recomiéndale
  revisar manualmente la transición.
- Si la narrativa está bien: responde null.

━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE RESPUESTA
━━━━━━━━━━━━━━━━━━━━━━━━
Responde ÚNICAMENTE con este JSON. Sin texto extra, sin bloques de código.
{{
  "icd":           "Feedback de 3-5 oraciones o null",
  "wps":           "Feedback de 3-5 oraciones o null",
  "hss":           "Feedback de 3-5 oraciones o null",
  "nts":           "Feedback de 3-5 oraciones o null",
  "preguntas":     ["Pregunta 1", "Pregunta 2"],
  "datos_curiosos":["Dato curioso 1", "Dato curioso 2"]
}}
[/INST]"""

_NTS_CON_CONTEXTO = """
CONTEXTO NARRATIVO:
  Diapositiva anterior : {slide_prev}
  Diapositiva siguiente: {slide_next}
"""

_NTS_SIN_CONTEXTO = """
CONTEXTO NARRATIVO: No disponible (diapositiva analizada de forma aislada).
"""

def _calcular_num_preguntas(palabras: int) -> int:
    if palabras <= 30: return 1
    elif palabras <= 60: return 2
    return 3

def _calcular_num_curiosidades(palabras: int) -> int:
    return 2 if palabras > 40 else 1

def generar_diagnostico_metrico(
    slide_data: dict,
    metricas:   dict,
    slide_prev: str = None,
    slide_next: str = None,
) -> dict:
    palabras = metricas.get("wps", {}).get("palabras", 0)

    nts_contexto = (
        _NTS_CON_CONTEXTO.format(
            slide_prev=slide_prev or "No disponible",
            slide_next=slide_next or "No disponible",
        )
        if (slide_prev or slide_next)
        else _NTS_SIN_CONTEXTO
    )

    prompt = _PROMPT_DIAGNOSTICO_METRICO.format(
        titulo              = slide_data.get("title", "Sin título"),
        contenido           = " ".join(slide_data.get("content", []))[:1200],
        icd_valor           = metricas.get("icd", {}).get("valor", "N/A"),
        icd_zona            = metricas.get("icd", {}).get("zona", "N/A"),
        wps_valor           = palabras,
        hss_estado          = metricas.get("hss", {}).get("coherencia", "N/A"),
        nts_estado          = metricas.get("nts", {}).get("estado", "N/A"),
        nts_contexto_bloque = nts_contexto,
        num_preguntas       = _calcular_num_preguntas(palabras),
        num_curiosidades    = _calcular_num_curiosidades(palabras),
    )

    try:
        # Llamada centralizada
        response = generar_respuesta(
            prompt=prompt,
            formato="json",
            options=_OLLAMA_OPTIONS,
            timeout=35
        )
        response.raise_for_status()
        resultado = json.loads(response.json().get("response", "{}"))

        resultado.setdefault("preguntas",     [])
        resultado.setdefault("datos_curiosos", [])
        return resultado

    except (requests.RequestException, json.JSONDecodeError):
        return {"preguntas": [], "datos_curiosos": []}