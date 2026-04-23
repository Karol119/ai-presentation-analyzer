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

def calculate_global_score(icd_result: Dict[str, Any], wps_result: Dict[str, Any], hss_result: Dict[str, Any], nts_result: Dict[str, Any]) -> Dict[str, Any]:
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

    # Aplicar pesos definidos en la tesis
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
    normalized_values: Dict[str, float] = {}

    # ICD
    if icd_r and icd_r.get("calculable") and icd_r.get("icd") is not None:
        val = icd_r["icd"]
        score_n = _normalize_icd(val)
        normalized_values["icd"] = score_n
        estado_icd_str = "BIEN" if icd_r.get("zona") == "apropiado" else "MEJORAR" # Irreducible ignorado por ahora
        metrics_summary["icd"] = {"valor": val, "estado": estado_icd_str}
        if estado_icd_str == "MEJORAR": aspects_to_improve.append("icd")

    # WPS
    if wps_r and wps_r.get("wps_score") is not None:
        val = wps_r["wps_score"]
        normalized_values["wps"] = val
        estado_wps_str = "BIEN" if wps_r.get("zona", "") == "optima" else "MEJORAR"
        metrics_summary["wps"] = {"valor": val, "estado": estado_wps_str}
        if estado_wps_str == "MEJORAR": aspects_to_improve.append("wps")

    # HSS
    if hss_r and hss_r.get("hss_score") is not None:
        val = hss_r["hss_score"]
        normalized_values["hss"] = val
        estado_hss_str = "BIEN" if val > 7.0 else "MEJORAR"
        metrics_summary["hss"] = {"valor": val, "estado": estado_hss_str}
        if estado_hss_str == "MEJORAR": aspects_to_improve.append("hss")

    # NTS
    if nts_r and nts_r.get("nts_score") is not None:
        val = nts_r["nts_score"]
        normalized_values["nts"] = val
        estado_nts_str = "BIEN" if val > 5.0 else "MEJORAR"
        metrics_summary["nts"] = {"valor": val, "estado": estado_nts_str}
        if estado_nts_str == "MEJORAR": aspects_to_improve.append("nts")

    # Cálculo Ponderado
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
        "necesita_recomendacion": len(aspects_to_improve) > 0
    }

def _normalize_icd(icd: float) -> float:
    if icd is None: return 0.0 
    if 4.0 <= icd <= 6.5: return 10.0
    if icd < 4.0: return max(0.0, 10.0 - (4.0 - icd) * 2.5)
    return max(0.0, 10.0 - (icd - 6.5) * 2.5)

def _get_global_zone(score: float) -> str:
    for limit, label in _GLOBAL_SCALE:
        if score <= limit: return label
    return "excelente"