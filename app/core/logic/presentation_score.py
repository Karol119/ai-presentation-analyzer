# app/core/logic/presentation_score.py
from typing import Dict, Any, List

WEIGHTS = {
    "icd": 0.30,
    "wps": 0.30,
    "hss": 0.25,
    "nts": 0.15,
}

_GLOBAL_SCALE = [
    (4.0, "deficiente"),
    (6.0, "regular"),
    (8.0, "bueno"),
    (10.0, "excelente"),
]

def calculate_global_score(avg_icd: float, avg_wps: float, avg_hss: float, avg_nts: float) -> Dict[str, Any]:
    """Calcula el score global usando los promedios matemáticos exactos de las diapositivas válidas."""
    metrics_scores = {
        "icd": round(avg_icd, 2),
        "wps": round(avg_wps, 2),
        "hss": round(avg_hss, 2),
        "nts": round(avg_nts, 2),
    }

    # Desglose ponderado (Métrica * Peso)
    score_breakdown = {f"{k}_pond": round(v * WEIGHTS[k], 3) for k, v in metrics_scores.items()}
    global_score = sum(score_breakdown.values())

    return {
        "score_global":   round(global_score, 2),
        "zona_global":    _get_global_zone(global_score),
        "scores_metrica": metrics_scores,
        "desglose":       score_breakdown,
        "pesos":          WEIGHTS,
    }

def calculate_slide_score(icd_r: Dict[str, Any], wps_r: Dict[str, Any], hss_r: Dict[str, Any], nts_r: Dict[str, Any]) -> Dict[str, Any]:
    metrics_summary = {
        "icd": {"valor": 0.0, "estado": "REVISAR"},
        "wps": {"valor": 0.0, "estado": "N/A"},
        "hss": {"valor": 0.0, "estado": "N/A"},
        "nts": {"valor": 0.0, "estado": "N/A"}
    }
    
    aspects_to_improve: List[str] = []
    normalized_values = {"icd": 0.0, "wps": 0.0, "hss": 0.0, "nts": 0.0}

    if icd_r and icd_r.get("calculable") and icd_r.get("icd") is not None:
        val = icd_r["icd"]
        score_n = _normalize_icd(val)
        normalized_values["icd"] = score_n
        estado = "BIEN" if icd_r.get("zona") == "apropiado" else "MEJORAR"
        metrics_summary["icd"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspects_to_improve.append("icd")

    if wps_r and wps_r.get("wps_score") is not None:
        val = wps_r["wps_score"]
        normalized_values["wps"] = val
        estado = "BIEN" if wps_r.get("zona") == "optima" else "MEJORAR"
        metrics_summary["wps"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspects_to_improve.append("wps")

    if hss_r and hss_r.get("hss_score") is not None:
        val = hss_r["hss_score"]
        normalized_values["hss"] = val
        estado = "BIEN" if val > 7.0 else "MEJORAR"
        metrics_summary["hss"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspects_to_improve.append("hss")

    if nts_r and nts_r.get("nts_score") is not None:
        val = nts_r["nts_score"]
        normalized_values["nts"] = val
        estado = "BIEN" if val > 5.0 else "MEJORAR"
        metrics_summary["nts"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspects_to_improve.append("nts")

    if normalized_values:
        total_points = sum(v * WEIGHTS[k] for k, v in normalized_values.items())
        accumulated_weight = sum(WEIGHTS[k] for k in normalized_values.keys())
        score = total_points / accumulated_weight if accumulated_weight > 0 else 0.0
    else:
        score = 0.0

    return {
        "score_total": round(score, 2),
        "zona": _get_global_zone(score),
        "estados": metrics_summary,
        "valores_normalizados": normalized_values, # Necesario para promediar bien
        "necesita_recomendacion": len(aspects_to_improve) > 0
    }

def _normalize_icd(icd: float) -> float:
    if icd is None: return 0.0 
    if 4.0 <= icd <= 6.5: return 10.0
    # PENALIZACIÓN SEVERA: Multiplicador de 5.0. 
    # Un ICD de 7.1 ahora saca 7.0 de calificación. Un ICD de 8.0 saca 2.5.
    if icd < 4.0: return max(0.0, 10.0 - (4.0 - icd) * 5.0)
    return max(0.0, 10.0 - (icd - 6.5) * 5.0)

def _get_global_zone(score: float) -> str:
    for limit, label in _GLOBAL_SCALE:
        if score <= limit: return label
    return "excelente"