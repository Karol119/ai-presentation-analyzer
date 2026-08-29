# app/core/controller/analyzer_controller.py
import concurrent.futures
from builtins import str
import json
from typing import Dict, Any, List, Callable, Optional

from app.core.logic.text_extractor import extraer_datos_pptx
from app.core.logic.metrics.icd import calcular_icd_presentacion
from app.infrastructure.ai.llm_provider import verificar_conexion_ia
from app.core.logic.metrics.word_count import calcular_wps_presentacion
from app.core.logic.metrics.ai_restructure import reestructurar_diapositivas_lote
from app.core.logic.metrics.ai_batch_metrics import calcular_metricas_ia_lote
from app.core.logic.presentation_score import calcular_puntaje_global, calcular_puntaje_diapositiva
from app.core.controller.subject_controller import obtener_temario_completo


def _ejecutar_metricas_locales(diapositivas_contenido: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "icd": calcular_icd_presentacion(diapositivas_contenido),
        "wps": calcular_wps_presentacion(diapositivas_contenido),
    }


def _ejecutar_metricas_ia(
    diapositivas_contenido: List[Dict[str, Any]],
    temario: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return calcular_metricas_ia_lote(diapositivas_contenido, temario)


def analizar_presentacion(
    ruta_archivo: str,
    nombre_materia: str,
    callback_estado: Optional[Callable] = None,
) -> Dict[str, Any]:

    # --- PRE-FLIGHT CHECK (FAIL FAST) ---
    if callback_estado:
        callback_estado("[SISTEMA] Comprobando estado del motor de Inteligencia Artificial...")
    try:
        verificar_conexion_ia()
    except Exception as e:
        if callback_estado:
            callback_estado("[CANCELADO] El análisis no pudo iniciar.")
        raise e

    # --- EXTRACCIÓN ---
    if callback_estado:
        callback_estado("[SISTEMA] Iniciando extracción de datos...")
    datos_extraidos = extraer_datos_pptx(ruta_archivo)

    if callback_estado:
        callback_estado("[SISTEMA] Recuperando temario de la materia...")
    temario = obtener_temario_completo(nombre_materia)
    if not temario:
        raise ValueError(
            f"No se encontró un temario para la materia '{nombre_materia}'."
        )

    total_diapositivas_pptx = datos_extraidos.get("total_slides", 0)
    diapositivas_contenido  = datos_extraidos["slides"]

    # --- FASE 1: MÉTRICAS EN PARALELO ---
    # Hilo A: métricas locales (ICD + WPS) — sin IA
    # Hilo B: métricas IA (3 prompts en paralelo dentro de ai_batch_metrics)
    if callback_estado:
        callback_estado(
            f"[SISTEMA] Analizando {len(diapositivas_contenido)} diapositivas..."
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ejecutor:
        futuro_local = ejecutor.submit(_ejecutar_metricas_locales, diapositivas_contenido)
        futuro_ia    = ejecutor.submit(_ejecutar_metricas_ia, diapositivas_contenido, temario)

        try:
            res_local = futuro_local.result()
            if callback_estado:
                callback_estado("[OK] Métricas locales completadas.")
            res_ia = futuro_ia.result()
            if callback_estado:
                callback_estado("[OK] Evaluación de IA completada.")
        except Exception as e:
            if callback_estado:
                callback_estado("[CANCELADO] Proceso interrumpido por un error de IA.")
            raise e

    res_icd = res_local["icd"]
    res_wps = res_local["wps"]
    res_hss = res_ia["hss"]
    res_nts = res_ia["nts"]
    datos_ia_lote      = res_ia.get("clasificaciones", {})
    temas_presentacion = res_ia.get("temas_presentacion", [])

    print("[TEMAS] Cobertura temática detectada por la IA")

    # --- CONSTRUCCIÓN DEL OBJETO POR DIAPOSITIVA ---
    diapositivas_finales      = []
    diapositivas_para_enriquecer = []
    tiempo_total_segundos     = 0

    conteo_diapositivas_validas = 0
    suma_icd = suma_wps = suma_hss = suma_nts = 0.0

    for diapositiva in diapositivas_contenido:
        num      = diapositiva["slide_number"]
        info_ia  = datos_ia_lote.get(num, {"tipo": "contenido", "tiempo": 10, "tipo_retorico": None})

        tipo_detectado  = info_ia["tipo"]
        tiempo_diap     = info_ia["tiempo"]
        tipo_retorico   = info_ia.get("tipo_retorico")   # ← NUEVO: viene de Prompt 1
        tiempo_total_segundos += tiempo_diap

        omitida = (tipo_detectado != "contenido")

        if omitida:
            diapositivas_finales.append({
                "slide_number":    num,
                "tipo":            tipo_detectado,
                "tiempo_exposicion": tiempo_diap,
                "omitida":         True,
                "score_slide":     None,
                "zona_slide":      None,
                "metricas":        None,
                "preguntas":       None,
                "datos_curiosos":  None,
                "reestructuracion": None,
            })
            continue

        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == num), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == num), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == num), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == num), {})

        datos_puntaje = calcular_puntaje_diapositiva(mi, mw, mh, mn)
        estados       = datos_puntaje["estados"]
        valores_norm  = datos_puntaje["valores_normalizados"]

        conteo_diapositivas_validas += 1
        suma_icd += valores_norm["icd"]
        suma_wps += valores_norm["wps"]
        suma_hss += valores_norm["hss"]
        suma_nts += valores_norm["nts"]

        necesita_reestructurar = datos_puntaje["necesita_recomendacion"]
        retroalimentacion = (
            f"ICD: {mi.get('feedback_local', '')} | "
            f"WPS: {mw.get('feedback_local', '')} | "
            f"HSS: {mh.get('feedback_ai', '')} | "
            f"NTS: {mn.get('feedback_ai', '')}"
        )

        formato_db_diapositiva = {
            "slide_number":   num,
            "tipo":           tipo_detectado,
            "tiempo_exposicion": tiempo_diap,
            "omitida":        False,
            "requiere_reestructuracion": necesita_reestructurar,
            "score_slide":    datos_puntaje["score_total"],
            "zona_slide":     datos_puntaje["zona"],
            "metricas": {
                "icd": {
                    "valor":    estados["icd"]["valor"],
                    "estado":   estados["icd"]["estado"],
                    "feedback": mi.get("feedback_local"),
                },
                "wps": {
                    "valor":    estados["wps"]["valor"],
                    "estado":   estados["wps"]["estado"],
                    "feedback": mw.get("feedback_local"),
                },
                "hss": {
                    "valor":    estados["hss"]["valor"],
                    "estado":   estados["hss"]["estado"],
                    "feedback": mh.get("feedback_ai"),
                },
                "nts": {
                    "valor":    estados["nts"]["valor"],
                    "estado":   estados["nts"]["estado"],
                    "feedback": mn.get("feedback_ai"),
                },
            },
            "preguntas":       [],
            "datos_curiosos":  [],
            "reestructuracion": None,
            # ── Campos temporales (se extraen con pop() antes de la salida final) ──
            "content":            diapositiva.get("content", []),
            "content_blocks":     diapositiva.get("content_blocks", []),  # estructura párrafo/lista
            "feedback_combinado": retroalimentacion,
            # ── NUEVOS campos temporales que necesita Prompt 4 y 5 ──────────────
            "titulo_original":  diapositiva.get("title", ""),      # título de la diapositiva
            "tipo_retorico":    tipo_retorico,                     # clasificado por Prompt 1
            "icd_valor":        mi.get("icd"),                     # valor numérico ICD (puede ser None)
            "palabras_count":   mw.get("palabras", 0),            # conteo real de palabras WPS
        }

        diapositivas_finales.append(formato_db_diapositiva)
        diapositivas_para_enriquecer.append(formato_db_diapositiva)

    # --- SCORE GLOBAL ---
    if callback_estado:
        callback_estado("[SISTEMA] Calculando Score Global final...")
    if conteo_diapositivas_validas > 0:
        datos_puntaje_global = calcular_puntaje_global(
            suma_icd / conteo_diapositivas_validas,
            suma_wps / conteo_diapositivas_validas,
            suma_hss / conteo_diapositivas_validas,
            suma_nts / conteo_diapositivas_validas,
        )
    else:
        datos_puntaje_global = calcular_puntaje_global(0, 0, 0, 0)

    # --- FASE 2: ENRIQUECIMIENTO Y RESTRUCTURACIÓN ---
    if diapositivas_para_enriquecer:
        if callback_estado:
            callback_estado("[SISTEMA] Generando Material Didáctico y Reestructurando...")
        try:
            mapa_reestructurado = reestructurar_diapositivas_lote([
                {
                    "slide_number":             s["slide_number"],
                    # ── Campos que ya existían ───────────────────────────
                    "content":                  s.pop("content"),
                    "content_blocks":           s.pop("content_blocks"),  # estructura párrafo/lista
                    "requiere_reestructuracion": s["requiere_reestructuracion"],
                    "feedback_a_corregir":       s.pop("feedback_combinado"),
                    # ── Campos nuevos para Prompt 4 y 5 ─────────────────
                    "titulo":                   s.pop("titulo_original"),
                    "tipo_retorico":            s.pop("tipo_retorico"),
                    "icd_valor":                s.pop("icd_valor"),
                    "palabras_count":           s.pop("palabras_count"),
                }
                for s in diapositivas_para_enriquecer
            ])
        except Exception as e:
            if callback_estado:
                callback_estado("[CANCELADO] El enriquecimiento fue interrumpido.")
            raise e

        for s in diapositivas_finales:
            if not s["omitida"]:
                datos_ia = mapa_reestructurado.get(s["slide_number"], {})
                s["preguntas"]       = datos_ia.get("preguntas", [])
                s["datos_curiosos"]  = datos_ia.get("datos_curiosos", [])
                arreglo_gen          = datos_ia.get("diapositivas_generadas", [])
                s["reestructuracion"] = {"diapositivas_generadas": arreglo_gen} if arreglo_gen else None

    # --- JSON DE SALIDA (contrato invariante) ---
    return {
        "total_diapositivas":                total_diapositivas_pptx,
        "score_global_presentacion":         datos_puntaje_global,
        "tiempo_total_exposicion_segundos":  tiempo_total_segundos,
        "tiempo_total_formateado":           f"{tiempo_total_segundos // 60}m {tiempo_total_segundos % 60}s",
        "temas_presentacion":                temas_presentacion,
        "slides":                            diapositivas_finales,
    }