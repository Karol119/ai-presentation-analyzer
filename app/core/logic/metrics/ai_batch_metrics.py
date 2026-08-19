# app/core/logic/metrics/ai_batch_metrics.py
import json
import re
from typing import Dict, Any, List

from app.infrastructure.ai.llm_provider import consultar_modelo
from app.infrastructure.ai.prompts import PROMPT_EVALUACION_LOTE

from app.core.logic.metrics.header_structure import _obtener_palabras_clave, _filtrar_nombres_personas, _clasificar_puntaje_hss
from app.core.logic.metrics.narrative_thread import _vectorizar, _similitud_coseno, _texto_completo, _determinar_estado_por_puntaje

def calcular_metricas_ia_lote(diapositivas: List[Dict[str, Any]], temario: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not diapositivas:
        return {"hss": _hss_vacio(), "nts": _nts_vacio(), "clasificaciones": {},  "temas_presentacion": []}

    carga_lote = []
    
    for i, diapositiva_actual in enumerate(diapositivas):
        diapositiva_previa = diapositivas[i-1] if i > 0 else None
        
        titulo = diapositiva_actual.get("title", "").strip()
        contenido_limpio = _filtrar_nombres_personas(" ".join(diapositiva_actual.get("content", [])))
        pc_titulo = _obtener_palabras_clave(titulo)
        pc_contenido = _obtener_palabras_clave(contenido_limpio)
        solapamiento = pc_titulo.intersection(pc_contenido)
        
        v_actual = _vectorizar(_texto_completo(diapositiva_actual))
        v_previa = _vectorizar(_texto_completo(diapositiva_previa)) if diapositiva_previa else {}
        puntaje_coseno = _similitud_coseno(v_previa, v_actual) if diapositiva_previa else 1.0

        carga_lote.append({
            "slide_number": diapositiva_actual.get("slide_number"),
            "titulo": titulo if titulo else "[SIN TÍTULO]",
            "contenido_truncado": contenido_limpio[:400] + "..." if len(contenido_limpio) > 400 else contenido_limpio,
            "hss_diagnostico": {
                "solapamiento_lexico": list(solapamiento) if solapamiento else "Ninguno"
            },
            "nts_diagnostico": {
                "similitud_coseno": round(puntaje_coseno, 4)
            }
        })

    prompt = PROMPT_EVALUACION_LOTE.format(
        batch_data=json.dumps(
            carga_lote,
            ensure_ascii=False,
            indent=2
        ),
        temario=json.dumps(
            temario,
            ensure_ascii=False,
            indent=2
        )
    )
    
    print("[IA LOTE] Evaluando lote en la IA (Clasificación + HSS + NTS)...")
    respuesta = consultar_modelo(prompt)

    mapa_resultados_ia = {}
    temas_presentacion = []

    try:
        match_json = re.search(r'\{.*\}', respuesta, re.DOTALL)

        if match_json:
            json_crudo = match_json.group()
            json_limpio = re.sub(r'[\n\r\t]+', ' ', json_crudo)

            datos_respuesta_ia = json.loads(json_limpio, strict=False)

            # Resultados individuales de cada diapositiva
            lista_datos_ia = datos_respuesta_ia.get("diapositivas", [])

            for item in lista_datos_ia:
                mapa_resultados_ia[item.get("slide_number")] = item

            # Cobertura temática de toda la presentación
            temas_presentacion = datos_respuesta_ia.get("temas_presentacion", [])

        else:
            raise ValueError("No se detectó un objeto JSON válido en la respuesta.")

    except Exception as e:
        print(f"[ERROR IA LOTE] Fallo al parsear JSON de la IA: {e}")

    resultados_hss = []
    resultados_nts = []
    clasificaciones = {}

    puntajes_hss_validos = []
    puntajes_nts_validos = []

    for i, diapositiva in enumerate(diapositivas):
        num_diapositiva = diapositiva.get("slide_number")
        datos_originales_ia = mapa_resultados_ia.get(num_diapositiva, {})
        
        tiempo_diapositiva = datos_originales_ia.get("tiempo_estimado_segundos", 10)
        datos_ia = datos_originales_ia.copy() 
        
        texto_completo = diapositiva.get("title", "") + " " + " ".join(diapositiva.get("content", []))
        palabras_totales = len(texto_completo.split())
        imagenes = diapositiva.get("image_count", 0)
        
        if imagenes > 0 and palabras_totales < 15:
            tipo_diapositiva = "visual"
            datos_ia = {} 
        elif palabras_totales < 5:
            tipo_diapositiva = "sin_contenido"
            datos_ia = {}
        else:
            tipo_diapositiva = datos_ia.get("tipo", "contenido").lower()
            
        clasificaciones[num_diapositiva] = {
            "tipo": tipo_diapositiva,
            "tiempo": tiempo_diapositiva
        }
        es_contenido = (tipo_diapositiva == "contenido")

        puntaje_hss_crudo = datos_ia.get("hss_score")
        puntaje_hss = float(puntaje_hss_crudo) if puntaje_hss_crudo is not None and es_contenido else 5.0
        
        if es_contenido: puntajes_hss_validos.append(puntaje_hss)

        resultados_hss.append({
            "slide_number": num_diapositiva,
            "tiene_titulo": bool(diapositiva.get("title", "").strip()),
            "titulo": diapositiva.get("title", ""),
            "hss_score": puntaje_hss if es_contenido else None,
            "coherencia": _clasificar_puntaje_hss(puntaje_hss) if es_contenido else "no_aplica",
            "feedback_ai": datos_ia.get("hss_feedback", "") if es_contenido else None
        })

        puntaje_nts_crudo = datos_ia.get("nts_score")
        puntaje_nts = float(puntaje_nts_crudo) if puntaje_nts_crudo is not None and es_contenido else 10.0
        
        if es_contenido: puntajes_nts_validos.append(puntaje_nts)

        diapositiva_previa = diapositivas[i-1] if i > 0 else None
        sim_coseno = _similitud_coseno(_vectorizar(_texto_completo(diapositiva_previa)), _vectorizar(_texto_completo(diapositiva))) if diapositiva_previa else 1.0

        resultados_nts.append({
            "slide_number": num_diapositiva,
            "sim_anterior": round(sim_coseno, 4) if diapositiva_previa else None,
            "sim_promedio": round(sim_coseno, 4),
            "nts_score": puntaje_nts if es_contenido else None,
            "estado": _determinar_estado_por_puntaje(puntaje_nts) if es_contenido else "no_aplica",
            "feedback_ai": datos_ia.get("nts_feedback", "") if es_contenido else None
        })
        
    num_validos_hss = len(puntajes_hss_validos)
    num_validos_nts = len(puntajes_nts_validos)

    res_hss = {
        "resultados": resultados_hss,
        "hss_promedio": round(sum(puntajes_hss_validos) / num_validos_hss, 2) if num_validos_hss else 0.0,
        "slides_con_titulo": sum(1 for r in resultados_hss if r["tiene_titulo"] and r["coherencia"] != "no_aplica"),
        "slides_coherentes": sum(1 for r in resultados_hss if r["coherencia"] == "coherente"),
        "slides_debiles": sum(1 for r in resultados_hss if r["coherencia"] == "debil"),
        "slides_no_coherentes": sum(1 for r in resultados_hss if r["coherencia"] == "no_coherente")
    }

    res_nts = {
        "resultados": resultados_nts,
        "nts_promedio": round(sum(puntajes_nts_validos) / num_validos_nts, 2) if num_validos_nts else 0.0,
        "slides_relacionadas": sum(1 for r in resultados_nts if r["estado"] == "relacionada"),
        "slides_debiles": sum(1 for r in resultados_nts if r["estado"] == "debil"),
        "slides_desconectadas": sum(1 for r in resultados_nts if r["estado"] == "desconectada")
    }

    return {"hss": res_hss, "nts": res_nts, "clasificaciones": clasificaciones, "temas_presentacion": temas_presentacion}

def _hss_vacio() -> Dict[str, Any]: 
    return {"resultados": [], "hss_promedio": 0.0}

def _nts_vacio() -> Dict[str, Any]: 
    return {"resultados": [], "nts_promedio": 0.0}