# app/core/logic/presentation_score.py
"""
presentation_score.py — v2

Corrección: se agrega el concepto de "icd_irreducible".
Si el texto tiene FSZ=0 (árido) Y las palabras clave son intrínsecamente
polisílabas (terminología especializada del dominio), el ICD no puede bajar
mediante reformulación sencilla. En ese caso el estado cambia de MEJORAR
a ADVERTENCIA — se informa al profesor pero no se envía a recomendación
infinita.

Umbral de rendición:
    Si ICD > 7.5 Y prom_sil_pal > 2.7 → marcar como "icd_irreducible"
    El texto tiene vocabulario técnico especializado que no puede simplificarse
    sin perder el contenido académico.
"""

PESOS = {
    "icd": 0.35,
    "wps": 0.25,
    "hss": 0.25,
    "nts": 0.15,
}

_ESCALA_GLOBAL = [
    (4.0, "deficiente"),
    (6.0, "regular"),
    (8.0, "bueno"),
    (10.0, "excelente"),
]

# Umbral de rendición para ICD
ICD_IRREDUCIBLE_UMBRAL     = 7.5
SILAPAL_IRREDUCIBLE_UMBRAL = 2.7


def calcular_score_global(icd_resultado, wps_resultado, hss_resultado, nts_resultado):
    """
    Calcula el score global de la presentación.
    MEJORA: Promedia las normalizaciones individuales para evitar que las 
    diapositivas buenas compensen totalmente a las malas.
    """
    
    # 1. ICD: Promediamos los scores ya normalizados de cada diapositiva calculable
    icd_scores_ind = [
        _normalizar_icd(r["icd"]) for r in icd_resultado.get("resultados", []) if r.get("calculable")
    ]
    icd_final = sum(icd_scores_ind) / len(icd_scores_ind) if icd_scores_ind else 0.0

    # 2. Otros: Promedio directo de sus scores (WPS, HSS y NTS ya vienen normalizados)
    wps_final = wps_resultado.get("wps_promedio", 0.0)
    hss_final = hss_resultado.get("hss_promedio", 0.0)
    nts_final = nts_resultado.get("nts_promedio", 0.0)

    scores = {
        "icd": round(icd_final, 2),
        "wps": round(wps_final, 2),
        "hss": round(hss_final, 2),
        "nts": round(nts_final, 2),
    }

    # Aplicar pesos definidos en la tesis (ICD: 35%, WPS: 25%, HSS: 25%, NTS: 15%)
    desglose = {
        f"{k}_pond": round(v * PESOS[k], 3)
        for k, v in scores.items()
    }

    score_global = sum(desglose.values())

    return {
        "score_global":   round(score_global, 2),
        "zona_global":    _zona_global(score_global),
        "scores_metrica": scores,
        "desglose":       desglose,
        "pesos":          PESOS,
    }


def calcular_score_slide(icd_r, wps_r, hss_r, nts_r):
    """
    Calcula el score de una slide evitando errores de tipo None.
    """
    # 1. Diccionario de métricas para el Asesor (con valores por defecto seguros)
    metricas = {
        "icd": {"valor": 0.0, "zona": "Sin texto", "estado": "REVISAR"},
        "wps": {"valor": 0.0, "palabras": 0, "estado": "N/A"},
        "hss": {"valor": 0.0, "coherencia": "N/A", "estado": "N/A"},
        "nts": {"valor": 0.0, "estado_narrativo": "N/A", "estado": "N/A"}
    }
    
    mejorar = []
    valores_norm = {}

    # --- Validación Individual de Métricas ---
    # ICD
    if icd_r and icd_r.get("calculable") and icd_r.get("icd") is not None:
        val = icd_r["icd"]
        score_n = _normalizar_icd(val)
        valores_norm["icd"] = score_n
        metricas["icd"] = {"valor": val, "zona": icd_r.get("zona"), "estado": _estado_icd(icd_r.get("zona"), False)}
        if metricas["icd"]["estado"] in ["MEJORAR", "ADVERTENCIA"]: mejorar.append("icd")

    # WPS
    if wps_r and wps_r.get("wps_score") is not None:
        val = wps_r["wps_score"]
        valores_norm["wps"] = val
        metricas["wps"] = {"valor": val, "palabras": wps_r.get("palabras", 0), "estado": _estado_wps(wps_r.get("zona", ""))}
        if metricas["wps"]["estado"] == "MEJORAR": mejorar.append("wps")

    # HSS
    if hss_r and hss_r.get("hss_score") is not None:
        val = hss_r["hss_score"]
        valores_norm["hss"] = val
        metricas["hss"] = {"valor": val, "coherencia": hss_r.get("coherencia", "N/A"), "estado": "OK" if val > 7 else "MEJORAR"}
        if val <= 7: mejorar.append("hss")

    # NTS
    if nts_r and nts_r.get("nts_score") is not None:
        val = nts_r["nts_score"]
        valores_norm["nts"] = val
        metricas["nts"] = {"valor": val, "estado_narrativo": nts_r.get("estado", "N/A"), "estado": "OK" if val > 5 else "REVISAR"}
        if val <= 5: mejorar.append("nts")

    # --- Cálculo Ponderado Seguro ---
    if valores_norm:
        puntos_totales = 0.0
        peso_acumulado = 0.0
        for k, v in valores_norm.items():
            # v SIEMPRE será float aquí, nunca None
            puntos_totales += v * PESOS[k]
            peso_acumulado += PESOS[k]
        score = puntos_totales / peso_acumulado if peso_acumulado > 0 else 0.0
    else:
        score = 0.0

    return {
        "score": round(score, 2),
        "zona": _zona_global(score),
        "metricas": metricas,
        "necesita_recomendacion": len(mejorar) > 0,
        "aspectos_mejorar": mejorar
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

def _es_icd_irreducible(icd_r):
    """
    Detecta si el texto tiene complejidad intrínseca no reducible
    sin alterar el contenido académico especializado.
    Un texto árido de posgrado con vocabulario polisílabo específico
    no puede simplificarse a ICD 4-6 sin perder su esencia.
    """
    if not icd_r:
        return False
    icd_val    = icd_r.get("icd", 0)
    sil_pal    = icd_r.get("prom_sil_pal", 0)
    return icd_val > ICD_IRREDUCIBLE_UMBRAL and sil_pal > SILAPAL_IRREDUCIBLE_UMBRAL


def _normalizar_icd(icd):
    """
    Normaliza el ICD a 0-10. 
    Maneja casos donde el ICD es None (no calculable).
    """
    if icd is None:
        # Si no es calculable por falta de texto, devolvemos un score neutro 
        # o penalización mínima, dependiendo de tu criterio. 
        # Para nivel superior, poco texto en una slide de contenido suele ser negativo.
        return 0.0 
    
    if 4.0 <= icd <= 6.5:
        return 10.0
    
    if icd < 4.0:
        return max(0.0, 10.0 - (4.0 - icd) * 2.5)
    else:
        return max(0.0, 10.0 - (icd - 6.5) * 2.5)


def _estado_icd(zona, irreducible):
    if zona == "apropiado":
        return "BIEN"
    if irreducible:
        # Texto técnico que no puede simplificarse — advertir pero no recomendar
        return "ADVERTENCIA"
    return "MEJORAR"


def _estado_wps(zona):
    return "BIEN" if zona == "optima" else "MEJORAR"


def _estado_hss(coherencia, tiene_titulo):
    if not tiene_titulo:
        return "MEJORAR"
    if coherencia == "coherente":
        return "BIEN"
    if coherencia == "no_coherente":
        return "MEJORAR"
    return "REVISAR"


def _estado_nts(estado_narrativo):
    if estado_narrativo == "relacionada":
        return "BIEN"
    if estado_narrativo == "debil":
        return "REVISAR"
    return "MEJORAR"


def _zona_global(score):
    for limite, etiqueta in _ESCALA_GLOBAL:
        if score <= limite:
            return etiqueta
    return "excelente"