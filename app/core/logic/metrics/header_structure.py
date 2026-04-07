"""
header_structure.py
Métrica de estructura del encabezado (Header Structure Score — HSS).

Evalúa:
    1. PRESENCIA  — la diapositiva tiene título o no
    2. COHERENCIA — el título está relacionado con el contenido

Score HSS (0–10):
    Sin título                              →  0.0
    Título presente + contenido vacío       →  5.0  (no verificable)
    Título presente + coherente             → 10.0
    Título presente + no coherente (LLM)    →  3.0
    Sin solapamiento + sin LLM              →  5.0  (no penalizar sin evidencia)

Fuente: Reynolds (2011) Beyond Bullet Points;
        Atkinson (2008) Presentation Zen.
"""

import re

_STOPWORDS = {
    "el","la","los","las","un","una","unos","unas",
    "a","ante","bajo","con","contra","de","desde","en","entre",
    "hacia","hasta","para","por","según","sin","sobre","tras",
    "y","e","ni","o","u","pero","sino","aunque","porque","que",
    "si","como","cuando","donde","mientras","ya","también","además",
    "yo","tú","él","ella","nosotros","ellos","me","te","se","nos",
    "es","son","era","fue","ser","estar","hay","haber","ha","han",
    "tiene","tienen","puede","pueden","debe","deben","hace","hacer",
    "este","esta","estos","estas","ese","esa","todo","todos","otra",
    "más","menos","muy","bien","tan","tanto","no","sí","al","del",
    "ahora","este","aquí","allí","así","aún","sea","ser",
}

_MIN_PALABRAS_TITULO_SIGNIFICATIVO = 2
_MIN_PALABRAS_CLAVE_CUERPO         = 3

# Detecta "Nombre Apellido Apellido" en cualquier parte del texto
# Cubre el caso "Comunicación oral y Escrita  Sandra Mercedes Perez Vera"
_RE_NOMBRE_PERSONA = re.compile(
    r'[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}'
)

# Detecta títulos que son encabezados de tabla multi-línea
# Ej: "Estándar \n Ancho de Banda \n Velocidad \n Distancia"
_RE_TITULO_TABLA = re.compile(r'\n')


def calcular_hss(slide_data, llm_fn=None):
    """
    Calcula HSS para una diapositiva de contenido.

    Returns:
        {
            "slide_number":           int,
            "tiene_titulo":           bool,
            "titulo":                 str,
            "hss_score":              float,
            "coherencia":             str,
            "palabras_clave_titulo":  [str],
            "palabras_clave_cuerpo":  [str],
            "solapamiento":           [str],
            "metodo_coherencia":      str
        }
    """
    titulo   = slide_data.get("title", "").strip()
    contenido = _texto_cuerpo(slide_data)

    base = {
        "slide_number":          slide_data.get("slide_number"),
        "tiene_titulo":          bool(titulo),
        "titulo":                titulo,
        "hss_score":             0.0,
        "coherencia":            "sin_titulo",
        "palabras_clave_titulo": [],
        "palabras_clave_cuerpo": [],
        "solapamiento":          [],
        "metodo_coherencia":     "sin_titulo",
    }

    if not titulo:
        return base

    # Título de encabezado de tabla (multi-línea): tratar como no verificable
    if _RE_TITULO_TABLA.search(titulo):
        base["hss_score"]        = 5.0
        base["coherencia"]       = "no_verificable"
        base["metodo_coherencia"] = "tabla"
        return base

    # Filtrar contenido que parece nombre de persona (footer que filtró mal)
    contenido_limpio = _filtrar_nombres_persona(contenido)

    kw_titulo = _palabras_clave(titulo)
    kw_cuerpo = _palabras_clave(contenido_limpio)

    base["palabras_clave_titulo"] = kw_titulo
    base["palabras_clave_cuerpo"] = kw_cuerpo

    # Sin contenido útil — no se puede verificar coherencia
    if len(kw_cuerpo) < _MIN_PALABRAS_CLAVE_CUERPO:
        base["hss_score"]        = 5.0
        base["coherencia"]       = "no_verificable"
        base["metodo_coherencia"] = "sin_contenido"
        return base

    # Título genérico de una sola palabra significativa
    if len(kw_titulo) < _MIN_PALABRAS_TITULO_SIGNIFICATIVO:
        base["hss_score"]        = 5.0
        base["coherencia"]       = "no_verificable"
        base["metodo_coherencia"] = "titulo_generico"
        return base

    # Solapamiento léxico directo
    solapamiento = _solapamiento(kw_titulo, kw_cuerpo)
    base["solapamiento"] = solapamiento

    if solapamiento:
        base["hss_score"]        = 10.0
        base["coherencia"]       = "coherente"
        base["metodo_coherencia"] = "lexico"
        return base

    # Sin solapamiento — intentar con LLM si disponible
    if llm_fn is not None:
        try:
            es_coherente = llm_fn(titulo, contenido_limpio[:400])
            if es_coherente is True:
                base["hss_score"]        = 10.0
                base["coherencia"]       = "coherente"
                base["metodo_coherencia"] = "llm"
            elif es_coherente is False:
                base["hss_score"]        = 3.0
                base["coherencia"]       = "no_coherente"
                base["metodo_coherencia"] = "llm"
            else:
                # LLM no concluyente
                base["hss_score"]        = 5.0
                base["coherencia"]       = "no_verificable"
                base["metodo_coherencia"] = "llm_inconclusivo"
        except Exception as e:
            print(f"[header_structure] Error LLM: {e}")
            base["hss_score"]        = 5.0
            base["coherencia"]       = "no_verificable"
            base["metodo_coherencia"] = "llm_error"
        return base

    # Sin LLM — no podemos confirmar incoherencia, no penalizar
    base["hss_score"]        = 5.0
    base["coherencia"]       = "no_verificable"
    base["metodo_coherencia"] = "sin_llm"
    return base


def calcular_hss_presentacion(slides_contenido, llm_fn=None):
    """
    Calcula HSS para todas las slides de contenido y agrega resumen.
    """
    resultados = [calcular_hss(s, llm_fn=llm_fn) for s in slides_contenido]

    scores = [r["hss_score"] for r in resultados]
    n      = len(resultados)

    con_titulo    = sum(1 for r in resultados if r["tiene_titulo"])
    sin_titulo    = n - con_titulo
    coherentes    = sum(1 for r in resultados if r["coherencia"] == "coherente")
    no_coherentes = sum(1 for r in resultados if r["coherencia"] == "no_coherente")
    no_verif      = sum(1 for r in resultados if r["coherencia"] == "no_verificable")

    return {
        "resultados":             resultados,
        "hss_promedio":           round(sum(scores) / n, 2) if n else 0.0,
        "slides_con_titulo":      con_titulo,
        "slides_sin_titulo":      sin_titulo,
        "slides_coherentes":      coherentes,
        "slides_no_coherentes":   no_coherentes,
        "slides_no_verificables": no_verif,
        "cobertura_titulo":       round(con_titulo / n * 100, 1) if n else 0.0,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _texto_cuerpo(slide_data):
    return " ".join(slide_data.get("content", []))


def _filtrar_nombres_persona(texto):
    """
    Elimina secuencias que parecen nombres de persona
    para evitar que footers mal filtrados contaminen el HSS.
    """
    return _RE_NOMBRE_PERSONA.sub("", texto).strip()


def _palabras_clave(texto):
    """Palabras significativas: sin stopwords, mínimo 3 chars, en minúsculas."""
    tokens = re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}', texto)
    return list({
        t.lower() for t in tokens
        if t.lower() not in _STOPWORDS
    })


def _solapamiento(kw_titulo, kw_cuerpo):
    """Palabras clave del título que aparecen en el cuerpo."""
    set_cuerpo = set(kw_cuerpo)
    return [w for w in kw_titulo if w in set_cuerpo]