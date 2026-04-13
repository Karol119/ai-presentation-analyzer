"""
header_structure.py
Métrica de estructura del encabezado (Header Structure Score — HSS).

Evalúa:
    1. PRESENCIA  — si la diapositiva tiene título.
    2. COHERENCIA — si el título es claro y se relaciona con el contenido.

Score HSS (0–10):
    - 10.0: Título presente y con solapamiento léxico directo.
    - 1.0 - 10.0: Evaluado por Mistral (LLM) en caso de sinónimos o falta de texto.
    - 0.0: Sin título.

Fuente: Reynolds (2011) Beyond Bullet Points; Atkinson (2008) Presentation Zen.
"""

import re

# ── Configuración y Filtros ──────────────────────────────────────────────────

_STOPWORDS = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además", "este", "esta", "estos", 
    "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas",
    "yo","tú","él","ella","nosotros","ellos","me","te","se","nos","es","son"
}

# Palabras que no aportan valor temático real
_EXCLUIDAS_ACADEMICAS = {
    "ejemplo", "caso", "importante", "definicion", "concepto", "introduccion", 
    "conclusion", "tema", "unidad", "capitulo", "objetivo", "descripcion", 
    "analisis", "nota", "resumen", "fundamentos", "presentacion"
}

# Detecta "Nombre Apellido Apellido" (limpieza de footers)
_RE_NOMBRE_PERSONA = re.compile(
    r'[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}'
)

# ── Funciones Principales ────────────────────────────────────────────────────

def calcular_hss(slide_data, llm_fn=None):
    """
    Evalúa la calidad del encabezado. 
    Usa reglas léxicas para velocidad y Mistral para comprensión semántica.
    """
    titulo = slide_data.get("title", "").strip()
    # Limpiamos el cuerpo de posibles nombres de personas (footers)
    contenido_raw = " ".join(slide_data.get("content", []))
    contenido = _filtrar_nombres_persona(contenido_raw)
    
    base = {
        "slide_number": slide_data.get("slide_number"),
        "tiene_titulo": bool(titulo),
        "titulo": titulo,
        "hss_score": 0.0,
        "coherencia": "sin_titulo",
        "metodo_coherencia": "reglas"
    }

    if not titulo:
        return base

    # 1. Análisis léxico (Búsqueda de conceptos clave exactos)
    kw_titulo = _obtener_palabras_clave(titulo)
    kw_cuerpo = _obtener_palabras_clave(contenido)
    solapamiento = [w for w in kw_titulo if w in kw_cuerpo]
    
    # 2. Lógica de Scoring
    if solapamiento:
        # Coincidencia exacta = Coherencia máxima inmediata
        base["hss_score"] = 10.0
        base["coherencia"] = "coherente"
        base["metodo_coherencia"] = "lexico"
        
    elif llm_fn:
        # Si no hay solapamiento léxico, Mistral evalúa semántica y claridad
        # Incluso si el contenido es escaso, el modelo juzga la calidad del título
        score_llm = llm_fn(titulo, contenido)
        
        base["hss_score"] = float(score_llm) if score_llm is not None else 5.0
        base["metodo_coherencia"] = "llm_mistral_eval"
        
        # Clasificación según nota de Mistral
        if base["hss_score"] >= 8.0:
            base["coherencia"] = "coherente"
        elif base["hss_score"] >= 5.0:
            base["coherencia"] = "debil"
        else:
            base["coherencia"] = "no_coherente"
            
    else:
        # Fallback sin conexión a Ollama
        base["hss_score"] = 5.0 if contenido.strip() else 3.0
        base["coherencia"] = "revisar_manualmente"

    return base


def calcular_hss_presentacion(slides_contenido, llm_fn=None):
    """
    Calcula el HSS global de la presentación.
    """
    resultados = [calcular_hss(s, llm_fn=llm_fn) for s in slides_contenido]
    scores = [r["hss_score"] for r in resultados]
    n = len(resultados)

    return {
        "resultados": resultados,
        "hss_promedio": round(sum(scores) / n, 2) if n else 0.0,
        "slides_con_titulo": sum(1 for r in resultados if r["tiene_titulo"]),
        "slides_coherentes": sum(1 for r in resultados if r["coherencia"] == "coherente"),
        "slides_debiles": sum(1 for r in resultados if r["coherencia"] == "debil"),
        "slides_no_coherentes": sum(1 for r in resultados if r["coherencia"] == "no_coherente"),
        "cobertura_titulo": round((sum(1 for r in resultados if r["tiene_titulo"]) / n * 100), 1) if n else 0.0,
    }

# ── Helpers ──────────────────────────────────────────────────────────────────

def _obtener_palabras_clave(texto):
    """
    Extrae palabras significativas eliminando ruido académico y stopwords.
    """
    if not texto:
        return set()
    # Buscamos palabras de 4 o más letras para evitar conectores
    tokens = re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{4,}', texto.lower())
    return {
        t for t in tokens 
        if t not in _STOPWORDS and t not in _EXCLUIDAS_ACADEMICAS
    }

def _filtrar_nombres_persona(texto):
    """
    Elimina secuencias que parecen nombres para evitar falsas coherencias.
    """
    return _RE_NOMBRE_PERSONA.sub("", texto).strip()