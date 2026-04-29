# app/core/logic/presentation_score.py
from typing import Dict, Any, List

PESOS = {
    "icd": 0.30,
    "wps": 0.30,
    "hss": 0.25,
    "nts": 0.15,
}

_ESCALA_GLOBAL = [
    (4.0, "deficiente"),
    (6.0, "regular"),
    (8.0, "bueno"),
    (10.0, "excelente"),
]

def calcular_puntaje_global(prom_icd: float, prom_wps: float, prom_hss: float, prom_nts: float) -> Dict[str, Any]:
    puntajes_metricas = {
        "icd": round(prom_icd, 2),
        "wps": round(prom_wps, 2),
        "hss": round(prom_hss, 2),
        "nts": round(prom_nts, 2),
    }

    desglose_puntaje = {f"{k}_pond": round(v * PESOS[k], 3) for k, v in puntajes_metricas.items()}
    puntaje_global = sum(desglose_puntaje.values())

    return {
        "score_global":   round(puntaje_global, 2),
        "zona_global":    _obtener_zona_global(puntaje_global),
        "scores_metrica": puntajes_metricas,
        "desglose":       desglose_puntaje,
        "pesos":          PESOS,
    }

def calcular_puntaje_diapositiva(res_icd: Dict[str, Any], res_wps: Dict[str, Any], res_hss: Dict[str, Any], res_nts: Dict[str, Any]) -> Dict[str, Any]:
    resumen_metricas = {
        "icd": {"valor": 0.0, "estado": "REVISAR"},
        "wps": {"valor": 0.0, "estado": "N/A"},
        "hss": {"valor": 0.0, "estado": "N/A"},
        "nts": {"valor": 0.0, "estado": "N/A"}
    }
    
    aspectos_a_mejorar: List[str] = []
    valores_normalizados = {"icd": 0.0, "wps": 0.0, "hss": 0.0, "nts": 0.0}

    if res_icd and res_icd.get("calculable") and res_icd.get("icd") is not None:
        val = res_icd["icd"]
        valores_normalizados["icd"] = _normalizar_icd(val)
        estado = "BIEN" if res_icd.get("zona") == "apropiado" else "MEJORAR"
        resumen_metricas["icd"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspectos_a_mejorar.append("icd")

    if res_wps and res_wps.get("wps_score") is not None:
        val = res_wps["wps_score"]
        valores_normalizados["wps"] = val
        estado = "BIEN" if res_wps.get("zona") == "optima" else "MEJORAR"
        resumen_metricas["wps"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspectos_a_mejorar.append("wps")

    if res_hss and res_hss.get("hss_score") is not None:
        val = res_hss["hss_score"]
        valores_normalizados["hss"] = val
        estado = "BIEN" if val > 7.0 else "MEJORAR"
        resumen_metricas["hss"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspectos_a_mejorar.append("hss")

    if res_nts and res_nts.get("nts_score") is not None:
        val = res_nts["nts_score"]
        valores_normalizados["nts"] = val
        estado = "BIEN" if val > 5.0 else "MEJORAR"
        resumen_metricas["nts"] = {"valor": val, "estado": estado}
        if estado == "MEJORAR": aspectos_a_mejorar.append("nts")

    if valores_normalizados:
        puntos_totales = sum(v * PESOS[k] for k, v in valores_normalizados.items())
        peso_acumulado = sum(PESOS[k] for k in valores_normalizados.keys())
        puntaje = puntos_totales / peso_acumulado if peso_acumulado > 0 else 0.0
    else:
        puntaje = 0.0

    return {
        "score_total": round(puntaje, 2),
        "zona": _obtener_zona_global(puntaje),
        "estados": resumen_metricas,
        "valores_normalizados": valores_normalizados,
        "necesita_recomendacion": len(aspectos_a_mejorar) > 0
    }

def _normalizar_icd(icd: float) -> float:
    if icd is None: return 0.0 
    if 4.0 <= icd <= 6.5: return 10.0
    if icd < 4.0: return max(0.0, 10.0 - (4.0 - icd) * 5.0)
    return max(0.0, 10.0 - (icd - 6.5) * 5.0)

def _obtener_zona_global(puntaje: float) -> str:
    for limite, etiqueta in _ESCALA_GLOBAL:
        if puntaje <= limite: return etiqueta
    return "excelente"