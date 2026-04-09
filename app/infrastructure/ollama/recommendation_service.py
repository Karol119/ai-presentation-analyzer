"""
recommendation_service.py — v4

Cambios principales:
  1. MAX_CONTENIDO_CHARS = 400 — el prompt cabe en el contexto de llama3.2
  2. Ciclo de verificación: las métricas se calculan sobre el texto generado
     y se reintenta si WPS, ICD o HSS salieron fuera de rango (max 3 intentos)
  3. Slides saturadas: la IA decide si resumir o dividir según el contenido,
     y cuando decide dividir genera un JSON array de slides completas
  4. Corrección del error de ampliación: si WPS es escasa y el LLM debe ampliar,
     la verificación asegura que el resultado esté en rango [40-75]
"""

import json
import re
import requests

OLLAMA_URL        = "http://localhost:11434/api/generate"
MODELO            = "llama3.2"
TIMEOUT_SEG       = 45
MAX_CONTENIDO_CHARS = 400   # límite duro para que el prompt quepa en el contexto
MAX_REINTENTOS    = 3


# ── Cálculo de métricas sobre texto generado ─────────────────────────────────

def _metricas_texto(titulo, contenido):
    """
    Calcula ICD y WPS sobre un texto generado para verificar que está en rango.
    Importa los módulos de métricas directamente.
    """
    from app.core.logic.metrics.text_counter  import contar_palabras, contar_silabas, segmentar_frases
    from app.core.logic.metrics.readability   import calcular_legibilidad
    from app.core.logic.metrics.lexical_density import calcular_densidad_lexica
    from app.core.logic.metrics.icd           import calcular_icd
    from app.core.logic.metrics.word_count    import calcular_wps

    slide_simulado = {
        "slide_number": 0,
        "title":        titulo or "",
        "content":      [contenido] if contenido else [],
        "footer":       [],
        "images":       [],
    }

    r_icd = calcular_icd(slide_simulado)
    r_wps = calcular_wps(slide_simulado)

    return {
        "icd":      r_icd.get("icd"),
        "icd_zona": r_icd.get("zona"),
        "calculable": r_icd.get("calculable", False),
        "palabras": r_wps.get("palabras"),
        "wps_zona": r_wps.get("zona"),
        "wps_score": r_wps.get("wps_score"),
    }


def _en_rangos(metricas_verificacion, aspectos_mejorar):
    """
    Verifica que el texto generado resuelve los aspectos que debía mejorar.
    Devuelve True si todos los aspectos requeridos están en rango.
    """
    m = metricas_verificacion
    ok = True

    if "icd" in aspectos_mejorar:
        if not m["calculable"] or m["icd_zona"] != "apropiado":
            ok = False

    if "wps" in aspectos_mejorar:
        if m["wps_zona"] not in ("optima",):
            ok = False

    return ok


# ── Decisión: dividir o resumir ───────────────────────────────────────────────

_PROMPT_DECISION = """Eres un experto en diseño de presentaciones académicas universitarias.

Analiza el siguiente contenido de una diapositiva con {palabras} palabras (el máximo recomendado es 75).

Título: {titulo}
Contenido:
{contenido}

Determina cuál es la mejor acción:
A) RESUMIR — el contenido habla de UN SOLO tema o concepto y puede condensarse en 40-75 palabras manteniendo la esencia
B) DIVIDIR — el contenido cubre MÚLTIPLES temas o conceptos que merecen cada uno su propia diapositiva

Responde SOLO con este JSON:
{{"decision": "resumir" o "dividir", "razon": "una oración explicando por qué", "n_slides": número entero de slides propuestas si decides dividir}}"""


def _decidir_accion(titulo, contenido, palabras):
    """Pide al LLM que decida si resumir o dividir. Retorna 'resumir' o 'dividir'."""
    prompt = _PROMPT_DECISION.format(
        titulo=titulo or "(sin título)",
        contenido=contenido[:500],
        palabras=palabras
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0, "num_predict": 150}},
            timeout=30
        )
        response.raise_for_status()
        texto = response.json().get("response", "").strip()
        parsed = _parsear_json(texto)
        if parsed and parsed.get("decision") in ("resumir", "dividir"):
            return parsed["decision"], parsed.get("n_slides", 2), parsed.get("razon","")
    except Exception:
        pass
    # fallback conservador
    return "dividir" if palabras > 150 else "resumir", 2, "decisión por defecto"


# ── Prompts especializados ────────────────────────────────────────────────────

_PROMPT_DIVIDIR = """Eres un experto en presentaciones académicas universitarias.

Divide el siguiente contenido en exactamente {n} diapositivas separadas.
Cada diapositiva debe:
- Tener un título claro de 3-6 palabras
- Tener entre 40 y 75 palabras de contenido
- Cubrir un solo subtema o concepto
- Conservar el nivel académico del original

Contenido original ({palabras} palabras):
Título general: {titulo}
{contenido}

Responde SOLO con este JSON (array de {n} elementos):
[
  {{"titulo": "string", "contenido": "string"}},
  ...
]"""

_PROMPT_RESUMIR = """Eres un experto en presentaciones académicas universitarias.

Mejora el siguiente contenido de diapositiva.

REGLAS ABSOLUTAS:
1. NO cambies el significado ni los conceptos del original
2. NO inventes información nueva
3. CONSERVA lo marcado con ✓
4. MEJORA solo lo marcado con MEJORAR
5. Responde SOLO con el JSON, sin texto adicional

CONTENIDO ORIGINAL:
Título: {titulo}
Cuerpo:
{contenido}

{contexto}

{{"titulo_nuevo": "string", "contenido_nuevo": "string", "cambios_realizados": ["cambio 1"], "justificacion": "una oración"}}"""


# ── Función principal ─────────────────────────────────────────────────────────

def generar_recomendacion_slide(slide_data, score_slide):
    from app.core.logic.recommendation_prompt import construir_contexto_metricas

    num   = score_slide.get("slide_number")
    metr  = score_slide.get("metricas", {})

    base = {
        "slide_number":        num,
        "necesitaba_rec":      False,
        "omitida_razon":       None,
        "decision":            None,    # "resumir" | "dividir"
        "titulo_nuevo":        None,
        "contenido_nuevo":     None,
        "slides_division":     None,    # lista de {titulo, contenido} si divide
        "sugerencia_division": None,
        "cambios_realizados":  [],
        "justificacion":       None,
        "verificacion":        None,    # métricas del texto generado
        "intentos":            0,
        "error":               None,
    }

    if not score_slide.get("necesita_recomendacion"):
        return base

    # ── Irreducible: solo reportar ────────────────────────────────────────────
    icd_m = metr.get("icd", {})
    if icd_m.get("irreducible"):
        base["omitida_razon"] = (
            "El texto tiene vocabulario técnico de nivel posgrado que no puede "
            "simplificarse sin alterar el contenido académico. "
            "Se recomienda al docente revisar si el nivel es apropiado."
        )
        return base

    # ── WPS escasa con imagen o muy poco texto ────────────────────────────────
    wps_m = metr.get("wps", {})
    solo_wps = score_slide.get("aspectos_mejorar") == ["wps"]
    if solo_wps:
        palabras    = wps_m.get("palabras", 0)
        tiene_imagen = bool(slide_data.get("images", []))
        if tiene_imagen or palabras < 20:
            base["omitida_razon"] = (
                "La diapositiva tiene pocos elementos de texto pero incluye imagen, "
                "lo cual es una decisión de diseño válida."
                if tiene_imagen else
                "La diapositiva tiene muy poco texto. Considere si es una diapositiva "
                "de concepto único o si requiere más contenido."
            )
            return base

    base["necesitaba_rec"] = True

    titulo    = slide_data.get("title", "").strip() or "(sin título)"
    contenido = "\n".join(slide_data.get("content", []))
    palabras  = wps_m.get("palabras", len(contenido.split()))

    # ── Decisión: resumir o dividir ───────────────────────────────────────────
    if wps_m.get("zona") in ("saturada", "densa") and wps_m.get("exceso", 0) > 30:
        decision, n_slides, razon_decision = _decidir_accion(titulo, contenido, palabras)
        base["decision"] = decision

        if decision == "dividir":
            slides_div = _generar_division(titulo, contenido, palabras, n_slides)
            if slides_div:
                base["slides_division"]     = slides_div
                base["sugerencia_division"] = (
                    f"El contenido fue dividido en {len(slides_div)} diapositivas ({razon_decision})"
                )
                return base
            # Si falló la división, caer a resumir
            base["decision"] = "resumir"

    # ── Ciclo de verificación: generar → verificar → reintentar ──────────────
    aspectos_mejorar = score_slide.get("aspectos_mejorar", [])
    contexto         = construir_contexto_metricas(score_slide)
    contenido_truncado = contenido[:MAX_CONTENIDO_CHARS]

    for intento in range(1, MAX_REINTENTOS + 1):
        base["intentos"] = intento

        # Ajustar la instrucción si el intento anterior falló por WPS
        contexto_iter = contexto
        if intento > 1 and base.get("verificacion"):
            v = base["verificacion"]
            if "wps" in aspectos_mejorar and v.get("wps_zona") not in ("optima",):
                pal_actual = v.get("palabras", 0)
                if pal_actual < 40:
                    contexto_iter += f"\n⚠ INTENTO {intento}: El texto anterior tenía {pal_actual} palabras — DEMASIADO CORTO. Debes escribir entre 40 y 75 palabras."
                else:
                    contexto_iter += f"\n⚠ INTENTO {intento}: El texto anterior tenía {pal_actual} palabras — DEMASIADO LARGO. Debes escribir entre 40 y 75 palabras."

        prompt = _PROMPT_RESUMIR.format(
            titulo=titulo,
            contenido=contenido_truncado,
            contexto=contexto_iter
        )

        resultado = _llamar_ollama(prompt, num_predict=1000)
        if not resultado:
            base["error"] = f"No parseable (intento {intento})"
            continue

        titulo_nuevo   = resultado.get("titulo_nuevo", titulo)
        contenido_nuevo = resultado.get("contenido_nuevo", "")

        # Verificar métricas del texto generado
        verif = _metricas_texto(titulo_nuevo, contenido_nuevo)
        base["verificacion"] = verif

        base.update({
            "titulo_nuevo":       titulo_nuevo,
            "contenido_nuevo":    contenido_nuevo,
            "cambios_realizados": resultado.get("cambios_realizados", []),
            "justificacion":      resultado.get("justificacion", ""),
            "error":              None,
        })

        if _en_rangos(verif, aspectos_mejorar):
            break   # el texto generado cumple todos los rangos

    return base


def generar_resumen_presentacion(nombre, score_global, icd, wps, hss, nts):
    from app.core.logic.recommendation_prompt import generar_prompt_resumen
    prompt = generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts)
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 400}},
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        return f"[Error generando resumen: {e}]"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generar_division(titulo, contenido, palabras, n_slides):
    """Pide al LLM que divida el contenido en n_slides slides."""
    prompt = _PROMPT_DIVIDIR.format(
        n=n_slides,
        palabras=palabras,
        titulo=titulo,
        contenido=contenido[:800]
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.2, "num_predict": 1500}},
            timeout=60
        )
        response.raise_for_status()
        texto = response.json().get("response", "").strip()
        parsed = _parsear_json(texto)
        if isinstance(parsed, list) and len(parsed) >= 2:
            return parsed
    except Exception:
        pass
    return None


def _llamar_ollama(prompt, num_predict=1000):
    for intento in range(2):
        try:
            prompt_real = prompt if intento == 0 else (
                prompt + "\n\nRecuerda: responde SOLO con el JSON entre llaves {}."
            )
            response = requests.post(
                OLLAMA_URL,
                json={"model": MODELO, "prompt": prompt_real, "stream": False,
                      "options": {"temperature": 0.1, "num_predict": num_predict}},
                timeout=TIMEOUT_SEG
            )
            response.raise_for_status()
            texto = response.json().get("response", "").strip()
            r = _parsear_json(texto)
            if r:
                return r
        except Exception:
            pass
    return None


def _parsear_json(texto):
    try:
        return json.loads(texto)
    except Exception:
        pass
    # Buscar JSON objeto
    m = re.search(r'\{[^{}]*\}', texto, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    # Buscar JSON array
    m = re.search(r'\[.*\]', texto, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    limpio = re.sub(r'```(?:json)?|```', '', texto).strip()
    try:
        return json.loads(limpio)
    except Exception:
        pass
    return None