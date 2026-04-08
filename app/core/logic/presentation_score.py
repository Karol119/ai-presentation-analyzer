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
    icd_score = icd_resultado.get("icd_promedio") or 0.0
    icd_norm  = _normalizar_icd(icd_score)

    scores = {
        "icd": round(icd_norm, 2),
        "wps": round(wps_resultado.get("wps_promedio", 0.0), 2),
        "hss": round(hss_resultado.get("hss_promedio", 0.0), 2),
        "nts": round(nts_resultado.get("nts_promedio", 0.0), 2),
    }

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
    icd_val = icd_r.get("icd") if icd_r and icd_r.get("calculable") else None
    wps_val = wps_r.get("wps_score") if wps_r else None
    hss_val = hss_r.get("hss_score") if hss_r else None
    nts_val = nts_r.get("nts_score") if nts_r else None

    metricas  = {}
    mejorar   = []
    conservar = []

    # ICD — con detección de irreducible
    if icd_val is not None:
        irreducible = _es_icd_irreducible(icd_r)
        estado      = _estado_icd(icd_r.get("zona", ""), irreducible)
        metricas["icd"] = {
            "valor":       icd_val,
            "zona":        icd_r.get("zona", ""),
            "estado":      estado,
            "irreducible": irreducible,
        }
        if estado == "MEJORAR":
            mejorar.append("icd")
        else:
            conservar.append("icd")

    # WPS
    if wps_val is not None:
        estado = _estado_wps(wps_r.get("zona", ""))
        metricas["wps"] = {
            "valor":    wps_val,
            "palabras": wps_r.get("palabras", 0),
            "zona":     wps_r.get("zona", ""),
            "exceso":   wps_r.get("exceso", 0),
            "deficit":  wps_r.get("deficit", 0),
            "estado":   estado,
        }
        if estado == "MEJORAR":
            mejorar.append("wps")
        else:
            conservar.append("wps")

    # HSS
    if hss_val is not None:
        estado = _estado_hss(hss_r.get("coherencia", ""), hss_r.get("tiene_titulo", False))
        metricas["hss"] = {
            "valor":        hss_val,
            "tiene_titulo": hss_r.get("tiene_titulo", False),
            "coherencia":   hss_r.get("coherencia", ""),
            "estado":       estado,
        }
        if estado == "MEJORAR":
            mejorar.append("hss")
        else:
            conservar.append("hss")

    # NTS
    if nts_val is not None:
        estado = _estado_nts(nts_r.get("estado", ""))
        metricas["nts"] = {
            "valor":            nts_val,
            "estado_narrativo": nts_r.get("estado", ""),
            "estado":           estado,
        }
        if estado == "MEJORAR":
            mejorar.append("nts")
        else:
            conservar.append("nts")

    # Score ponderado
    valores_norm = {}
    if "icd" in metricas:
        valores_norm["icd"] = _normalizar_icd(metricas["icd"]["valor"])
    if "wps" in metricas:
        valores_norm["wps"] = metricas["wps"]["valor"]
    if "hss" in metricas:
        valores_norm["hss"] = metricas["hss"]["valor"]
    if "nts" in metricas:
        valores_norm["nts"] = metricas["nts"]["valor"]

    if valores_norm:
        total_pesos = sum(PESOS[k] for k in valores_norm)
        score = sum(v * PESOS[k] for k, v in valores_norm.items()) / total_pesos
    else:
        score = 0.0

    return {
        "slide_number":           icd_r.get("slide_number") if icd_r else None,
        "score":                  round(score, 2),
        "zona":                   _zona_global(score),
        "metricas":               metricas,
        "necesita_recomendacion": bool(mejorar),
        "aspectos_mejorar":       mejorar,
        "aspectos_conservar":     conservar,
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
    centro    = 5.0
    radio     = 1.0
    distancia = abs(icd - centro)
    if distancia <= radio:
        return 10.0
    penalizacion = (distancia - radio) * 2.0
    return round(max(0.0, 10.0 - penalizacion), 2)


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