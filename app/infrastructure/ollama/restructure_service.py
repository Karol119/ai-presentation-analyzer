"""
Servicio de reestructuración de diapositivas.
Recibe el contenido original y los resultados de las métricas,
y genera slides corregidas que cumplan con todas las métricas.

Si WPS > 75 y hay múltiples ideas, divide en varias diapositivas.
Cada slide generada se valida contra las métricas; si falla se reintenta
desde el contenido original (máximo MAX_INTENTOS veces).
"""
import json
import requests

from app.core.logic.metrics.icd            import calcular_icd_presentacion
from app.core.logic.metrics.word_count     import calcular_wps_presentacion
from app.core.logic.metrics.header_structure import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread import calcular_nts
from app.core.logic.presentation_score     import calcular_score_slide

OLLAMA_URL   = "http://localhost:11434/api/generate"
MODELO       = "mistral"
MAX_INTENTOS = 3

_OLLAMA_OPTIONS = {
    "temperature": 0,
    "seed":        42,
    "top_k":       1,
    "top_p":       1.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_REESTRUCTURAR = """[INST]
Eres un experto en diseño instruccional para educación superior.
Tu tarea es reestructurar el contenido de una diapositiva para que cumpla
con estas cuatro reglas pedagógicas. NO inventes conceptos nuevos ni omitas
definiciones clave del autor.

━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS QUE DEBES CUMPLIR
━━━━━━━━━━━━━━━━━━━━━━━━
1. ICD – Complejidad (rango 4.0–6.5):
   - Si el lenguaje es muy técnico (ICD > 6.5): sustituye términos muy especializados
     por equivalentes claros para estudiantes universitarios, sin perder el concepto.
   - Si es muy básico (ICD < 4.0): incorpora terminología técnica propia del tema.
   - Si ya está en rango: mantén el lenguaje tal como está.

2. WPS – Máximo 75 palabras por diapositiva:
   - Si el contenido tiene UNA sola idea y excede 75 palabras: ajusta el redactado
     para reducirlo a máximo 75 palabras sin quitar el concepto central.
   - Si el contenido tiene VARIAS ideas y excede 75 palabras: separa en una
     diapositiva por idea. Cada diapositiva resultante debe tener máximo 75 palabras.
   - Si ya está en rango: no modifiques la cantidad de palabras.

3. HSS – Estructura (título coherente):
   - Si la diapositiva ya tiene un título coherente con su contenido: CONSERVA ESE
     MISMO TÍTULO sin modificarlo.
   - Si no tiene título o es incoherente: genera un título corto (máximo 8 palabras)
     que refleje exactamente el contenido.

4. NTS – Hilo narrativo:
   - Mantén los conceptos en un orden lógico que fluya desde la diapositiva anterior
     hacia la siguiente según el contexto que se te proporciona.

━━━━━━━━━━━━━━━━━━━━━━━━
DIAPOSITIVA ORIGINAL
━━━━━━━━━━━━━━━━━━━━━━━━
Título   : {titulo}
Contenido: {contenido}
Palabras actuales: {wps_valor}

━━━━━━━━━━━━━━━━━━━━━━━━
ESTADO ACTUAL DE MÉTRICAS
━━━━━━━━━━━━━━━━━━━━━━━━
ICD: {icd_valor} (zona: {icd_zona}) | Rango ideal: 4.0–6.5
WPS: {wps_valor} palabras           | Máximo: 75
HSS: {hss_estado}
NTS: {nts_estado}
{nts_contexto_bloque}
━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE RESPUESTA
━━━━━━━━━━━━━━━━━━━━━━━━
Devuelve ÚNICAMENTE un JSON con esta estructura. Sin texto extra.

Si el contenido cabe en UNA sola diapositiva:
{{
  "diapositivas": [
    {{
      "titulo":    "Título de la diapositiva",
      "contenido": ["Bullet o párrafo 1", "Bullet o párrafo 2"]
    }}
  ]
}}

Si el contenido debe dividirse en VARIAS diapositivas:
{{
  "diapositivas": [
    {{
      "titulo":    "Título idea 1",
      "contenido": ["Bullet 1", "Bullet 2"]
    }},
    {{
      "titulo":    "Título idea 2",
      "contenido": ["Bullet 1"]
    }}
  ]
}}
[/INST]"""

_NTS_CON_CONTEXTO = """
CONTEXTO NARRATIVO:
  Diapositiva anterior : {slide_prev}
  Diapositiva siguiente: {slide_next}
"""
_NTS_SIN_CONTEXTO = """
CONTEXTO NARRATIVO: No disponible (analizada de forma aislada).
"""


# ─────────────────────────────────────────────────────────────────────────────
# Validación interna de slides generadas
# ─────────────────────────────────────────────────────────────────────────────

def _slide_cumple_metricas(slide_dict: dict) -> tuple[bool, list[str]]:
    """
    Valida que una slide generada cumpla ICD, WPS y HSS.
    NTS no se valida aquí porque depende del contexto global.

    Retorna (cumple: bool, metricas_fallidas: list[str])
    """
    slide_como_lista = [slide_dict]

    res_icd = calcular_icd_presentacion(slide_como_lista)
    res_wps = calcular_wps_presentacion(slide_como_lista)
    res_hss = calcular_hss_presentacion(slide_como_lista, llm_fn=None)  # sin LLM en validación

    ri = res_icd["resultados"][0] if res_icd["resultados"] else {}
    rw = res_wps["resultados"][0] if res_wps["resultados"] else {}
    rh = res_hss["resultados"][0] if res_hss["resultados"] else {}

    # Usamos calcular_score_slide para aprovechar la lógica ya definida
    ss = calcular_score_slide(ri, rw, rh, {})
    fallidas = ss.get("aspectos_mejorar", [])

    # Excluimos NTS de la validación local
    fallidas_sin_nts = [m for m in fallidas if m != "nts"]
    return (len(fallidas_sin_nts) == 0), fallidas_sin_nts


# ─────────────────────────────────────────────────────────────────────────────
# Llamada al modelo
# ─────────────────────────────────────────────────────────────────────────────

def _llamar_modelo(prompt: str) -> list[dict] | None:
    """
    Llama a Ollama y retorna la lista de diapositivas generadas,
    o None si algo falla.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":   MODELO,
                "prompt":  prompt,
                "stream":  False,
                "format":  "json",
                "options": _OLLAMA_OPTIONS,
            },
            timeout=45,
        )
        response.raise_for_status()
        data = json.loads(response.json().get("response", "{}"))
        slides = data.get("diapositivas", [])

        # Validación estructural mínima
        if not isinstance(slides, list) or not slides:
            return None
        for s in slides:
            if not isinstance(s.get("titulo"), str):
                return None
            if not isinstance(s.get("contenido"), list):
                return None

        return slides

    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def reestructurar_slide(
    slide_data: dict,
    metricas:   dict,
    slide_prev: str = None,
    slide_next: str = None,
) -> dict:
    """
    Reestructura el contenido de una diapositiva para que cumpla las métricas.

    Parámetros
    ----------
    slide_data  : dict con 'title', 'content' (list[str]) y 'slide_number'
    metricas    : dict con resultados de ICD, WPS, HSS y NTS (de calcular_score_slide)
    slide_prev  : texto plano de la diapositiva anterior (para NTS)
    slide_next  : texto plano de la diapositiva siguiente (para NTS)

    Retorna
    -------
    {
        "exito":        bool,
        "intentos":     int,
        "diapositivas": [              # 1 o más slides reestructuradas
            {
                "titulo":    str,
                "contenido": list[str],
                "slide_number_origen": int,   # número de la slide original
            },
            ...
        ],
        "metricas_fallidas_final": list[str],  # vacío si exito=True
    }
    """
    n              = slide_data.get("slide_number", 0)
    titulo_orig    = slide_data.get("title", "Sin título")
    contenido_orig = " ".join(slide_data.get("content", []))

    nts_contexto = (
        _NTS_CON_CONTEXTO.format(
            slide_prev=slide_prev or "No disponible",
            slide_next=slide_next or "No disponible",
        )
        if (slide_prev or slide_next)
        else _NTS_SIN_CONTEXTO
    )

    prompt = _PROMPT_REESTRUCTURAR.format(
        titulo              = titulo_orig,
        contenido           = contenido_orig[:1500],
        icd_valor           = metricas.get("icd", {}).get("valor", "N/A"),
        icd_zona            = metricas.get("icd", {}).get("zona", "N/A"),
        wps_valor           = metricas.get("wps", {}).get("palabras", "N/A"),
        hss_estado          = metricas.get("hss", {}).get("coherencia", "N/A"),
        nts_estado          = metricas.get("nts", {}).get("estado", "N/A"),
        nts_contexto_bloque = nts_contexto,
    )

    ultimo_fallo: list[str] = []

    for intento in range(1, MAX_INTENTOS + 1):
        slides_generadas = _llamar_modelo(prompt)

        if slides_generadas is None:
            ultimo_fallo = ["error_modelo"]
            continue

        # ── Validar cada slide generada contra las métricas ──────────────────
        todas_ok   = True
        fallas_acc = []

        for sg in slides_generadas:
            # Armamos un dict compatible con las funciones de métricas
            slide_eval = {
                "slide_number": n,
                "title":        sg["titulo"],
                "content":      sg["contenido"],
            }
            cumple, fallidas = _slide_cumple_metricas(slide_eval)
            if not cumple:
                todas_ok = False
                fallas_acc.extend(fallidas)

        if todas_ok:
            # ── Éxito: enriquecer con número de origen y retornar ─────────────
            resultado_slides = [
                {
                    "titulo":              sg["titulo"],
                    "contenido":           sg["contenido"],
                    "slide_number_origen": n,
                }
                for sg in slides_generadas
            ]
            return {
                "exito":                   True,
                "intentos":                intento,
                "diapositivas":            resultado_slides,
                "metricas_fallidas_final": [],
            }

        # Si falló, registramos y reintentamos desde el contenido original
        ultimo_fallo = list(set(fallas_acc))

    # Agotamos intentos: retornamos el último resultado aunque no sea perfecto
    slides_generadas = _llamar_modelo(prompt) or []
    resultado_slides = [
        {
            "titulo":              sg.get("titulo", titulo_orig),
            "contenido":           sg.get("contenido", slide_data.get("content", [])),
            "slide_number_origen": n,
        }
        for sg in slides_generadas
    ] or [{
        "titulo":              titulo_orig,
        "contenido":           slide_data.get("content", []),
        "slide_number_origen": n,
    }]

    return {
        "exito":                   False,
        "intentos":                MAX_INTENTOS,
        "diapositivas":            resultado_slides,
        "metricas_fallidas_final": ultimo_fallo,
    }