"""
narrative_thread.py
Métrica de hilo narrativo (NTS).

CAMBIO: Score calculado por tramos en lugar de lineal.
La escala lineal anterior penalizaba demasiado el rango débil.

Nuevo mapa de score:
    sim >= 0.30  → 10.0  (fuertemente relacionada)
    sim >= 0.15  → 7.0 + ((sim - 0.15) / 0.15) × 3   (relacionada: 7–10)
    sim >= 0.05  → 3.0 + ((sim - 0.05) / 0.10) × 4   (débil: 3–7)
    sim < 0.05   → (sim / 0.05) × 3                   (desconectada: 0–3)

Umbrales de estado (sin cambio):
    ≥ 0.15 → relacionada
    0.05–0.14 → débil
    < 0.05 → desconectada
"""

import re
import math

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
}

UMBRAL_RELACIONADA = 0.15
UMBRAL_DEBIL       = 0.05
UMBRAL_FUERTE      = 0.30


def calcular_nts(slides_contenido):
    if not slides_contenido:
        return _resumen_vacio()

    vectores = [_vectorizar(_texto_completo(s)) for s in slides_contenido]
    nums     = [s.get("slide_number") for s in slides_contenido]
    n        = len(vectores)

    resultados = []

    for i in range(n):
        sim_ant  = _coseno(vectores[i-1], vectores[i]) if i > 0     else None
        sim_sig  = _coseno(vectores[i],   vectores[i+1]) if i < n-1 else None

        sims_validas = [s for s in [sim_ant, sim_sig] if s is not None]
        sim_prom     = sum(sims_validas) / len(sims_validas) if sims_validas else 0.0

        nts_score = _score_tramos(sim_prom)
        estado    = _estado(sim_prom)

        resultados.append({
            "slide_number":  nums[i],
            "sim_anterior":  round(sim_ant,  4) if sim_ant  is not None else None,
            "sim_siguiente": round(sim_sig,  4) if sim_sig  is not None else None,
            "sim_promedio":  round(sim_prom, 4),
            "nts_score":     nts_score,
            "estado":        estado,
        })

    pares_rotura = []
    for i in range(n - 1):
        sim = _coseno(vectores[i], vectores[i+1])
        if sim < UMBRAL_DEBIL:
            pares_rotura.append({
                "entre":     [nums[i], nums[i+1]],
                "similitud": round(sim, 4)
            })

    scores = [r["nts_score"] for r in resultados]

    return {
        "resultados":           resultados,
        "nts_promedio":         round(sum(scores) / len(scores), 2) if scores else 0.0,
        "slides_relacionadas":  sum(1 for r in resultados if r["estado"] == "relacionada"),
        "slides_debiles":       sum(1 for r in resultados if r["estado"] == "debil"),
        "slides_desconectadas": sum(1 for r in resultados if r["estado"] == "desconectada"),
        "pares_rotura":         pares_rotura,
    }


def _score_tramos(sim):
    """
    Mapa por tramos para evitar penalización excesiva en zona débil.
    sim=0.035 → ~2.1 (desconectada leve, no catastrófico)
    sim=0.10  → ~5.0 (débil)
    sim=0.20  → ~8.0 (relacionada)
    sim=0.30+ → 10.0
    """
    if sim >= UMBRAL_FUERTE:
        return 10.0
    if sim >= UMBRAL_RELACIONADA:
        # 7.0 a 10.0 en el rango [0.15, 0.30]
        t = (sim - UMBRAL_RELACIONADA) / (UMBRAL_FUERTE - UMBRAL_RELACIONADA)
        return round(7.0 + t * 3.0, 2)
    if sim >= UMBRAL_DEBIL:
        # 3.0 a 7.0 en el rango [0.05, 0.15]
        t = (sim - UMBRAL_DEBIL) / (UMBRAL_RELACIONADA - UMBRAL_DEBIL)
        return round(3.0 + t * 4.0, 2)
    # 0.0 a 3.0 en el rango [0.0, 0.05]
    t = sim / UMBRAL_DEBIL
    return round(t * 3.0, 2)


def _texto_completo(slide_data):
    partes = []
    titulo = slide_data.get("title", "").strip()
    if titulo:
        partes.append(titulo)
    for bloque in slide_data.get("content", []):
        bloque = bloque.strip()
        if bloque:
            partes.append(bloque)
    return " ".join(partes)


def _vectorizar(texto):
    tokens = re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}', texto)
    tokens = [t.lower() for t in tokens if t.lower() not in _STOPWORDS]
    if not tokens:
        return {}
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in tf.items()}


def _coseno(v1, v2):
    if not v1 or not v2:
        return 0.0
    comunes = set(v1.keys()) & set(v2.keys())
    if not comunes:
        return 0.0
    dot    = sum(v1[t] * v2[t] for t in comunes)
    mag_v1 = math.sqrt(sum(x**2 for x in v1.values()))
    mag_v2 = math.sqrt(sum(x**2 for x in v2.values()))
    if mag_v1 == 0 or mag_v2 == 0:
        return 0.0
    return dot / (mag_v1 * mag_v2)


def _estado(sim):
    if sim >= UMBRAL_RELACIONADA:
        return "relacionada"
    if sim >= UMBRAL_DEBIL:
        return "debil"
    return "desconectada"


def _resumen_vacio():
    return {
        "resultados":[], "nts_promedio":0.0,
        "slides_relacionadas":0, "slides_debiles":0,
        "slides_desconectadas":0, "pares_rotura":[],
    } 