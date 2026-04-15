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

from typing import Dict, Any, List

WEIGHTS = {
    "icd": 0.35,
    "wps": 0.25,
    "hss": 0.25,
    "nts": 0.15,
}

_GLOBAL_SCALE = [
    (4.0, "deficiente"),
    (6.0, "regular"),
    (8.0, "bueno"),
    (10.0, "excelente"),
]

# Umbral de rendición para ICD
ICD_IRREDUCIBLE_THRESHOLD      = 7.5
SYLLABLE_IRREDUCIBLE_THRESHOLD = 2.7


def calculate_global_score(icd_result: Dict[str, Any], wps_result: Dict[str, Any], hss_result: Dict[str, Any], nts_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula el score global de la presentación.
    Promedia las normalizaciones individuales para evitar que las 
    diapositivas buenas compensen totalmente a las malas.
    """
    
    # 1. ICD: Promediamos los scores ya normalizados de cada diapositiva calculable
    individual_icd_scores = [
        _normalize_icd(r.get("icd")) for r in icd_result.get("resultados", []) if r.get("calculable")
    ]
    final_icd = sum(individual_icd_scores) / len(individual_icd_scores) if individual_icd_scores else 0.0

    # 2. Otros: Promedio directo de sus scores (WPS, HSS y NTS ya vienen normalizados)
    wps_final = wps_result.get("wps_promedio", 0.0)
    hss_final = hss_result.get("hss_promedio", 0.0)
    nts_final = nts_result.get("nts_promedio", 0.0)

    metrics_scores = {
        "icd": round(final_icd, 2),
        "wps": round(wps_final, 2),
        "hss": round(hss_final, 2),
        "nts": round(nts_final, 2),
    }

    # Aplicar pesos definidos en la tesis (ICD: 35%, WPS: 25%, HSS: 25%, NTS: 15%)
    score_breakdown = {
        f"{k}_pond": round(v * WEIGHTS[k], 3)
        for k, v in metrics_scores.items()
    }

    global_score = sum(score_breakdown.values())

    return {
        "score_global":   round(global_score, 2),
        "zona_global":    _get_global_zone(global_score),
        "scores_metrica": metrics_scores,
        "desglose":       score_breakdown,
        "pesos":          WEIGHTS,
    }


def calculate_slide_score(icd_r: Dict[str, Any], wps_r: Dict[str, Any], hss_r: Dict[str, Any], nts_r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula el score de una slide evitando errores de tipo None.
    """
    # 1. Diccionario de métricas para el Asesor (con valores por defecto seguros)
    metrics_summary = {
        "icd": {"valor": 0.0, "zona": "Sin texto", "estado": "REVISAR"},
        "wps": {"valor": 0.0, "palabras": 0, "estado": "N/A"},
        "hss": {"valor": 0.0, "coherencia": "N/A", "estado": "N/A"},
        "nts": {"valor": 0.0, "estado_narrativo": "N/A", "estado": "N/A"}
    }
    
    aspects_to_improve: List[str] = []
    normalized_values: Dict[str, float] = {}

    # --- Validación Individual de Métricas ---
    
    # ICD
    if icd_r and icd_r.get("calculable") and icd_r.get("icd") is not None:
        val = icd_r["icd"]
        score_n = _normalize_icd(val)
        normalized_values["icd"] = score_n
        
        is_irreducible = _is_icd_irreducible(icd_r)
        estado_icd_str = _get_icd_status(icd_r.get("zona"), is_irreducible)
        
        metrics_summary["icd"] = {"valor": val, "zona": icd_r.get("zona"), "estado": estado_icd_str}
        if estado_icd_str in ["MEJORAR", "ADVERTENCIA"]: 
            aspects_to_improve.append("icd")

    # WPS
    if wps_r and wps_r.get("wps_score") is not None:
        val = wps_r["wps_score"]
        normalized_values["wps"] = val
        estado_wps_str = _get_wps_status(wps_r.get("zona", ""))
        
        metrics_summary["wps"] = {"valor": val, "palabras": wps_r.get("palabras", 0), "estado": estado_wps_str}
        if estado_wps_str == "MEJORAR": 
            aspects_to_improve.append("wps")

    # HSS
    if hss_r and hss_r.get("hss_score") is not None:
        val = hss_r["hss_score"]
        normalized_values["hss"] = val
        estado_hss_str = _get_hss_status(hss_r.get("coherencia", "N/A"), val)
        
        metrics_summary["hss"] = {"valor": val, "coherencia": hss_r.get("coherencia", "N/A"), "estado": estado_hss_str}
        if estado_hss_str in ["MEJORAR", "REVISAR"]: 
            aspects_to_improve.append("hss")

    # NTS
    if nts_r and nts_r.get("nts_score") is not None:
        val = nts_r["nts_score"]
        normalized_values["nts"] = val
        estado_nts_str = _get_nts_status(nts_r.get("estado", "N/A"), val)
        
        metrics_summary["nts"] = {"valor": val, "estado_narrativo": nts_r.get("estado", "N/A"), "estado": estado_nts_str}
        if estado_nts_str in ["MEJORAR", "REVISAR"]: 
            aspects_to_improve.append("nts")

    # --- Cálculo Ponderado Seguro ---
    if normalized_values:
        total_points = 0.0
        accumulated_weight = 0.0
        for k, v in normalized_values.items():
            total_points += v * WEIGHTS[k]
            accumulated_weight += WEIGHTS[k]
        score = total_points / accumulated_weight if accumulated_weight > 0 else 0.0
    else:
        score = 0.0

    return {
        "score": round(score, 2),
        "zona": _get_global_zone(score),
        "metricas": metrics_summary,
        "necesita_recomendacion": len(aspects_to_improve) > 0,
        "aspectos_mejorar": aspects_to_improve
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_icd_irreducible(icd_r: Dict[str, Any]) -> bool:
    """
    Detecta si el texto tiene complejidad intrínseca no reducible
    sin alterar el contenido académico especializado.
    """
    if not icd_r:
        return False
    icd_val  = icd_r.get("icd", 0)
    sil_pal  = icd_r.get("prom_sil_pal", 0)
    return icd_val > ICD_IRREDUCIBLE_THRESHOLD and sil_pal > SYLLABLE_IRREDUCIBLE_THRESHOLD


def _normalize_icd(icd: float) -> float:
    """Normaliza el ICD a 0-10."""
    if icd is None:
        return 0.0 
    
    if 4.0 <= icd <= 6.5:
        return 10.0
    
    if icd < 4.0:
        return max(0.0, 10.0 - (4.0 - icd) * 2.5)
    else:
        return max(0.0, 10.0 - (icd - 6.5) * 2.5)


def _get_icd_status(zona: str, irreducible: bool) -> str:
    if zona == "apropiado":
        return "BIEN"
    if irreducible:
        return "ADVERTENCIA"
    return "MEJORAR"


def _get_wps_status(zona: str) -> str:
    return "BIEN" if zona == "optima" else "MEJORAR"


def _get_hss_status(coherencia: str, score: float) -> str:
    """Unificado para usar el score validado."""
    if score > 7.0:
        return "BIEN"
    if coherencia == "no_coherente" or score <= 4.0:
        return "MEJORAR"
    return "REVISAR"


def _get_nts_status(estado_narrativo: str, score: float) -> str:
    """Unificado para usar el score validado."""
    if score > 5.0 or estado_narrativo == "relacionada":
        return "BIEN"
    if estado_narrativo == "desconectada":
        return "MEJORAR"
    return "REVISAR"


def _get_global_zone(score: float) -> str:
    for limit, label in _GLOBAL_SCALE:
        if score <= limit:
            return label
    return "excelente"