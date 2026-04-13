# app/core/logic/slide_classifier.py
import re

UMBRAL_ALTA  = 0.80
UMBRAL_MEDIA = 0.60

TIPOS_EXCLUIR = {"portada", "indice", "referencias", "cierre", "visual", "cita", "sin_contenido"}

_KW = {
    "portada": re.compile(
        r'\b(portada|presentaci[oó]n|bienvenid[oa]s?)\b',
        re.IGNORECASE
    ),
    # "temas?" eliminado — coincidía con "Tema 3", "Tema 2" (títulos de sección)
    # Ahora solo atrapa palabras que no pueden ser sección: índice, temario, agenda
    "indice": re.compile(
        r'\b([íi]ndice|temario|agenda)\b',
        re.IGNORECASE
    ),
    "referencias": re.compile(
        r'\b(referencias?|bibliograf[íi]a|fuentes?|webgraf[íi]a|recursos)\b',
        re.IGNORECASE
    ),
    "cierre": re.compile(
        r'\b(gracias|conclusiones?|cierre|fin|preguntas?|dudas?)\b',
        re.IGNORECASE
    ),
}

# "Tema N" al inicio del título = portada de sección, no índice
_RE_TEMA_SECCION = re.compile(r'^(Tema|Unidad|Cap[íi]tulo|Módulo)\s+\d', re.IGNORECASE)

_RE_ANIO   = re.compile(r'\((19|20)\d{2}\)')
_RE_URL    = re.compile(r'https?://|www\.', re.IGNORECASE)
_RE_BULLET = re.compile(r'^\s*([•\-\*\u2022]|\d+[\.\)])\s+')

_RE_CITA_COMILLAS = re.compile(
    r'[«""\u201c\u00ab].{60,}[»""\u201d\u00bb]',
    re.DOTALL
)

MIN_PALABRAS_UTIL = 8

_REGLAS = [
    # ── Portada ───────────────────────────────────────────────────────────────
    ("R01", "portada",       0.95, lambda f: f["tiene_solo_imagen"] and f["W"] == 0 and f["W_titulo"] == 0),
    ("R02", "portada",       0.90, lambda f: f["W"] <= 5 and f["B"] == 0 and f["W_titulo"] <= 8),
    ("R03", "portada",       0.85, lambda f: f["KT"]["portada"]),
    # "Tema N / Unidad N" en título = portada de sección
    ("R03b","portada",       0.85, lambda f: f["es_seccion"] and f["W"] <= 15),
    ("R04", "portada",       0.68, lambda f: f["W"] <= 20 and f["B"] <= 1 and f["ABW"] <= 8 and f["W_titulo"] <= 8),

    # ── Índice ────────────────────────────────────────────────────────────────
    ("R05", "indice",        0.92, lambda f: f["KT"]["indice"]),
    # R06 corregida: muchos bullets cortos solo es índice si el título sugiere agenda
    # Si no, puede ser lista de conceptos del tema → no clasificar como índice aquí
    ("R06a", "indice", 0.95, lambda f: f["KT"]["indice"] and f["B"] >= 2),
    ("R06b", "indice", 0.55, lambda f: not f["KT"]["indice"] 
                                     and f["B"] >= 5 
                                     and f["ABW"] <= 3 
                                     and f["W_titulo"] <= 3),

    # ── Referencias ───────────────────────────────────────────────────────────
    ("R07", "referencias",   0.92, lambda f: f["KT"]["referencias"]),
    ("R08", "referencias",   0.88, lambda f: f["YP"] >= 0.40),
    ("R09", "referencias",   0.82, lambda f: f["UP"] >= 0.30),
    ("R10", "referencias",   0.78, lambda f: f["YP"] >= 0.25 and f["UP"] >= 0.15),

    # ── Cierre ────────────────────────────────────────────────────────────────
    ("R11", "cierre",        0.92, lambda f: f["KT"]["cierre"] and f["W"] <= 20),
    ("R12", "cierre",        0.75, lambda f: f["KT"]["cierre"] and f["W"] <= 40),

    # ── Cita textual ──────────────────────────────────────────────────────────
    ("R15", "cita",          0.85, lambda f: f["es_cita"]),

    # ── Sin contenido útil ────────────────────────────────────────────────────
    ("R16", "sin_contenido", 0.80, lambda f: (f["W"] + f["W_titulo"]) < MIN_PALABRAS_UTIL
                                              and not f["tiene_solo_imagen"]
                                              and not f["KT"]["cierre"]),

    # ── Contenido ─────────────────────────────────────────────────────────────
    # Título largo (definición visual) con cuerpo vacío o mínimo
    ("R17", "contenido",     0.82, lambda f: f["W_titulo"] >= 12 and f["W"] <= 5),
    # Texto sustancial sin patrones de cita/URL
    ("R13", "contenido",     0.82, lambda f: f["W"] >= 25 and f["YP"] < 0.25 and f["UP"] < 0.20),
    # Bullets de contenido con volumen suficiente
    ("R14", "contenido",     0.76, lambda f: f["W"] >= 15 and f["B"] >= 2 and f["YP"] < 0.25),
    # Título claro + párrafo corto (slides 8-10 del caso Relaciones humanas)
    ("R18", "contenido",     0.72, lambda f: f["W_titulo"] >= 4 and f["W"] >= 8 and f["W"] < 25
                                              and f["B"] == 0 and f["YP"] < 0.25),
    # Lista de conceptos: varios bullets cortos CON título sustancial
    # Esto resuelve el caso slide 5 (estilos del conflicto)
    ("R19", "contenido",     0.70, lambda f: f["B"] >= 3 and f["W_titulo"] >= 4
                                              and f["ABW"] <= 6 and f["W"] >= 8),
]


def extraer_features(slide_data):
    ft = {
        "W":               0,
        "W_titulo":        0,
        "B":               0,
        "ABW":             0.0,
        "YP":              0.0,
        "UP":              0.0,
        "es_cita":         False,
        "es_seccion":      False,
        "tiene_solo_imagen": slide_data.get("tiene_solo_imagen", False),
        "KT": {"portada": False, "indice": False, "referencias": False, "cierre": False}
    }

    titulo = slide_data.get("title", "")
    ft["W_titulo"] = len(titulo.split()) if titulo else 0

    # Detectar "Tema N", "Unidad N", "Capítulo N", "Módulo N" en el título
    ft["es_seccion"] = bool(_RE_TEMA_SECCION.match(titulo.strip()))

    for tipo, patron in _KW.items():
        if patron.search(titulo):
            ft["KT"][tipo] = True

    texto_completo = titulo + " " + " ".join(slide_data.get("content", []))
    ft["es_cita"] = bool(_RE_CITA_COMILLAS.search(texto_completo))

    lineas = _aplanar_contenido(slide_data.get("content", []))
    if not lineas:
        return ft

    total_palabras = bullets = lineas_anio = lineas_url = 0

    for linea in lineas:
        total_palabras += len(linea.split())
        if _RE_BULLET.match(linea): bullets     += 1
        if _RE_ANIO.search(linea):  lineas_anio += 1
        if _RE_URL.search(linea):   lineas_url  += 1

    n = len(lineas)
    ft["W"]   = total_palabras
    ft["B"]   = bullets
    ft["ABW"] = round(total_palabras / n, 2) if n else 0.0
    ft["YP"]  = round(lineas_anio / n, 2)    if n else 0.0
    ft["UP"]  = round(lineas_url  / n, 2)    if n else 0.0

    return ft


def clasificar_por_reglas(ft):
    scores     = {}
    disparadas = []

    for rid, tipo, score, test in _REGLAS:
        try:
            if test(ft):
                disparadas.append(rid)
                if tipo not in scores or scores[tipo] < score:
                    scores[tipo] = score
        except Exception:
            pass

    if not scores:
        return {"tipo": None, "confianza": 0.0, "reglas_disparadas": []}

    tipo_ganador = max(scores, key=scores.get)
    return {
        "tipo":              tipo_ganador,
        "confianza":         scores[tipo_ganador],
        "reglas_disparadas": disparadas
    }


def clasificar_diapositiva(slide_data, llm_fn=None):
    ft     = extraer_features(slide_data)
    result = clasificar_por_reglas(ft)
    metodo = "reglas"

    if result["confianza"] < UMBRAL_MEDIA:
        if llm_fn is not None:
            try:
                tipo_llm = llm_fn(slide_data)
                tipos_validos = {"portada", "indice", "referencias", "cierre", "contenido", "cita"}
                if tipo_llm in tipos_validos:
                    result["tipo"]      = tipo_llm
                    result["confianza"] = 0.70
                    metodo = "llm"
                else:
                    result["tipo"]      = "contenido"
                    result["confianza"] = 0.50
                    metodo = "fallback_contenido"
            except Exception as e:
                print(f"[slide_classifier] Error LLM: {e}")
                result["tipo"]      = "contenido"
                result["confianza"] = 0.50
                metodo = "fallback_contenido"
        else:
            result["tipo"]      = result["tipo"] or "contenido"
            result["confianza"] = result["confianza"] or 0.50
            metodo = "fallback_contenido"

    return {
        "tipo":              result["tipo"],
        "confianza":         result["confianza"],
        "metodo":            metodo,
        "reglas_disparadas": result.get("reglas_disparadas", []),
        "excluir":           result["tipo"] in TIPOS_EXCLUIR
    }


def _aplanar_contenido(content):
    lineas = []
    for bloque in content:
        for linea in bloque.split("\n"):
            l = linea.strip()
            if l:
                lineas.append(l)
    return lineas