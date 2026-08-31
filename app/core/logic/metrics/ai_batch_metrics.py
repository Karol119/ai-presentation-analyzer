# app/core/logic/metrics/ai_batch_metrics.py
"""
Fase 1 del análisis IA: 3 prompts ejecutados en paralelo.

  Prompt 1 — Clasificación + tipo retórico + HSS + tiempo estimado
  Prompt 2 — Hilo narrativo (NTS)
  Prompt 3 — Cobertura del temario (global)

El contrato de retorno es idéntico al anterior para no tocar el controller:
  {
    "hss":              { resultados[], hss_promedio, slides_con_titulo, ... },
    "nts":              { resultados[], nts_promedio, slides_relacionadas, ... },
    "clasificaciones":  { num: { tipo, tiempo, tipo_retorico } },
    "temas_presentacion": []
  }

NUEVO en clasificaciones: se agrega "tipo_retorico" por diapositiva.
El controller lo lee para pasárselo al módulo de restructuración.
"""

import json
import re
import concurrent.futures
from typing import Dict, Any, List

from app.infrastructure.ai.llm_provider import consultar_modelo
from app.infrastructure.ai.prompts import (
    PROMPT_1_CLASIFICACION,  SI_CLASIFICACION,
    PROMPT_2_HILO_NARRATIVO, SI_HILO_NARRATIVO,
    PROMPT_3_COBERTURA,      SI_COBERTURA,
)
from app.core.logic.metrics.header_structure import (
    _obtener_palabras_clave,
    _filtrar_nombres_personas,
    _clasificar_puntaje_hss,
)
from app.core.logic.metrics.narrative_thread import (
    _vectorizar,
    _similitud_coseno,
    _texto_completo,
    _determinar_estado_por_puntaje,
)


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA PÚBLICO
# ---------------------------------------------------------------------------

def calcular_metricas_ia_lote(
    diapositivas: List[Dict[str, Any]],
    temario: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Ejecuta los 3 prompts de evaluación en paralelo y consolida los resultados.
    Retorna el mismo contrato que la versión anterior para no tocar el controller.
    """
    if not diapositivas:
        return {
            "hss": _hss_vacio(),
            "nts": _nts_vacio(),
            "clasificaciones": {},
            "temas_presentacion": [],
        }

    # --- Construir la carga de datos compartida por Prompt 1 y Prompt 2 ---
    carga_lote = _construir_carga_lote(diapositivas)

    # --- Construir la carga resumida para Prompt 3 (solo título + contenido) ---
    carga_cobertura = _construir_carga_cobertura(diapositivas)

    # --- Ejecutar los 3 prompts en paralelo ---
    print("[IA LOTE] Ejecutando 3 prompts en paralelo (Clasificación / NTS / Cobertura)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futuro_p1 = pool.submit(_llamar_prompt_1, carga_lote)
        futuro_p2 = pool.submit(_llamar_prompt_2, carga_lote)
        futuro_p3 = pool.submit(_llamar_prompt_3, carga_cobertura, temario)

        resultados_p1 = futuro_p1.result()   # lista de dicts por diapositiva
        resultados_p2 = futuro_p2.result()   # lista de dicts por diapositiva
        temas_presentacion = futuro_p3.result()  # lista de unidades/temas

    print("[IA LOTE] Prompts 1, 2 y 3 completados.")

    # --- Indexar respuestas por slide_number para acceso O(1) ---
    mapa_p1 = {item.get("slide_number"): item for item in resultados_p1}
    mapa_p2 = {item.get("slide_number"): item for item in resultados_p2}

    # --- Consolidar resultados en el contrato esperado por el controller ---
    return _consolidar_resultados(diapositivas, mapa_p1, mapa_p2, temas_presentacion)


# ---------------------------------------------------------------------------
# CONSTRUCCIÓN DE CARGAS
# ---------------------------------------------------------------------------

def _construir_carga_lote(diapositivas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepara el batch de datos para Prompt 1 y Prompt 2.
    Incluye diagnósticos locales previos (solapamiento léxico y coseno)
    para que el modelo los use como evidencia objetiva.
    """
    carga = []
    for i, diap in enumerate(diapositivas):
        diap_previa = diapositivas[i - 1] if i > 0 else None

        titulo = diap.get("title", "").strip()
        contenido_limpio = _filtrar_nombres_personas(
            " ".join(diap.get("content", []))
        )

        pc_titulo = _obtener_palabras_clave(titulo)
        pc_contenido = _obtener_palabras_clave(contenido_limpio)
        solapamiento = pc_titulo.intersection(pc_contenido)

        v_actual = _vectorizar(_texto_completo(diap))
        v_previa  = _vectorizar(_texto_completo(diap_previa)) if diap_previa else {}
        coseno    = _similitud_coseno(v_previa, v_actual) if diap_previa else 1.0

        carga.append({
            "slide_number": diap.get("slide_number"),
            "titulo": titulo if titulo else "[SIN TÍTULO]",
            "contenido": (
                contenido_limpio[:500] + "..."
                if len(contenido_limpio) > 500
                else contenido_limpio
            ),
            "hss_diagnostico": {
                "solapamiento_lexico": list(solapamiento) if solapamiento else []
            },
            "nts_diagnostico": {
                "similitud_coseno": round(coseno, 4)
            },
        })
    return carga


def _construir_carga_cobertura(diapositivas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepara la carga para Prompt 3: solo título y contenido completo,
    sin los diagnósticos de solapamiento y coseno que no son relevantes
    para la evaluación global de temario.
    """
    return [
        {
            "slide_number": d.get("slide_number"),
            "titulo": d.get("title", "").strip() or "[SIN TÍTULO]",
            "contenido": " ".join(d.get("content", [])),
        }
        for d in diapositivas
    ]


# ---------------------------------------------------------------------------
# LLAMADAS A CADA PROMPT
# ---------------------------------------------------------------------------

def _llamar_prompt_1(carga_lote: List[Dict]) -> List[Dict]:
    """Prompt 1: Clasificación + tipo retórico + HSS + tiempo estimado."""
    prompt = PROMPT_1_CLASIFICACION.format(
        batch_data=json.dumps(carga_lote, ensure_ascii=False, indent=2)
    )
    respuesta = consultar_modelo(prompt, system_instruction=SI_CLASIFICACION)
    return _parsear_arreglo_json(respuesta, "Prompt 1 (Clasificación)")


def _llamar_prompt_2(carga_lote: List[Dict]) -> List[Dict]:
    """Prompt 2: Hilo narrativo (NTS)."""
    prompt = PROMPT_2_HILO_NARRATIVO.format(
        batch_data=json.dumps(carga_lote, ensure_ascii=False, indent=2)
    )
    respuesta = consultar_modelo(prompt, system_instruction=SI_HILO_NARRATIVO)
    return _parsear_arreglo_json(respuesta, "Prompt 2 (NTS)")


def _llamar_prompt_3(
    carga_cobertura: List[Dict],
    temario: List[Dict],
) -> List[Dict]:
    """Prompt 3: Cobertura del temario (evaluación global)."""
    prompt = PROMPT_3_COBERTURA.format(
        batch_data=json.dumps(carga_cobertura, ensure_ascii=False, indent=2),
        temario=json.dumps(temario, ensure_ascii=False, indent=2),
    )
    respuesta = consultar_modelo(prompt, system_instruction=SI_COBERTURA)

    try:
        match = re.search(r"\{.*\}", respuesta, re.DOTALL)
        if match:
            datos = json.loads(
                re.sub(r"[\n\r\t]+", " ", match.group()), strict=False
            )
            return datos.get("temas_presentacion", [])
    except Exception as e:
        print(f"[ERROR Prompt 3 (Cobertura)] Fallo al parsear JSON: {e}")
    return []


# ---------------------------------------------------------------------------
# CONSOLIDACIÓN
# ---------------------------------------------------------------------------

def _consolidar_resultados(
    diapositivas: List[Dict[str, Any]],
    mapa_p1: Dict[int, Dict],
    mapa_p2: Dict[int, Dict],
    temas_presentacion: List[Dict],
) -> Dict[str, Any]:
    """
    Une los resultados de los 3 prompts con los cálculos locales ya existentes
    y construye el contrato de retorno idéntico al anterior.
    """
    resultados_hss = []
    resultados_nts = []
    clasificaciones = {}

    puntajes_hss_validos = []
    puntajes_nts_validos = []

    for i, diap in enumerate(diapositivas):
        num = diap.get("slide_number")

        datos_p1 = mapa_p1.get(num, {})
        datos_p2 = mapa_p2.get(num, {})

        # ── Clasificación ──────────────────────────────────────────────────
        texto_completo_diap = (
            diap.get("title", "") + " " + " ".join(diap.get("content", []))
        )
        palabras_totales = len(texto_completo_diap.split())
        imagenes = diap.get("image_count", 0)

        # Anulaciones locales que siempre tienen prioridad sobre la IA
        if imagenes > 0 and palabras_totales < 15:
            tipo_detectado = "visual"
            datos_p1 = {}  # ignorar datos de la IA para esta diapositiva
        elif palabras_totales < 5:
            tipo_detectado = "sin_contenido"
            datos_p1 = {}
        else:
            tipo_detectado = datos_p1.get("tipo", "contenido").lower()

        tiempo_diap    = datos_p1.get("tiempo_estimado_segundos", 10)
        tipo_retorico  = datos_p1.get("tipo_retorico")  # puede ser None

        clasificaciones[num] = {
            "tipo":          tipo_detectado,
            "tiempo":        tiempo_diap,
            "tipo_retorico": tipo_retorico,  # NUEVO: el controller lo usa para reestructurar
        }

        es_contenido = (tipo_detectado == "contenido")

        # ── HSS ────────────────────────────────────────────────────────────
        puntaje_hss_crudo = datos_p1.get("hss_score")
        puntaje_hss = (
            float(puntaje_hss_crudo)
            if puntaje_hss_crudo is not None and es_contenido
            else 5.0
        )
        if es_contenido:
            puntajes_hss_validos.append(puntaje_hss)

        resultados_hss.append({
            "slide_number": num,
            "tiene_titulo": bool(diap.get("title", "").strip()),
            "titulo":       diap.get("title", ""),
            "hss_score":    puntaje_hss if es_contenido else None,
            "coherencia":   _clasificar_puntaje_hss(puntaje_hss) if es_contenido else "no_aplica",
            "feedback_ai":  datos_p1.get("hss_feedback", "") if es_contenido else None,
        })

        # ── NTS ────────────────────────────────────────────────────────────
        puntaje_nts_crudo = datos_p2.get("nts_score")
        puntaje_nts = (
            float(puntaje_nts_crudo)
            if puntaje_nts_crudo is not None and es_contenido
            else 10.0
        )
        if es_contenido:
            puntajes_nts_validos.append(puntaje_nts)

        # Similitud coseno local (ya calculada en _construir_carga_lote, la recalculamos
        # aquí para mantener el campo en el resultado sin duplicar lógica crítica)
        diap_previa = diapositivas[i - 1] if i > 0 else None
        sim_coseno = (
            _similitud_coseno(
                _vectorizar(_texto_completo(diap_previa)),
                _vectorizar(_texto_completo(diap)),
            )
            if diap_previa
            else 1.0
        )

        resultados_nts.append({
            "slide_number": num,
            "sim_anterior": round(sim_coseno, 4) if diap_previa else None,
            "sim_promedio": round(sim_coseno, 4),
            "nts_score":    puntaje_nts if es_contenido else None,
            "estado":       _determinar_estado_por_puntaje(puntaje_nts) if es_contenido else "no_aplica",
            "feedback_ai":  datos_p2.get("nts_feedback", "") if es_contenido else None,
        })

    # ── Resúmenes agregados ─────────────────────────────────────────────────
    n_hss = len(puntajes_hss_validos)
    n_nts = len(puntajes_nts_validos)

    res_hss = {
        "resultados":        resultados_hss,
        "hss_promedio":      round(sum(puntajes_hss_validos) / n_hss, 2) if n_hss else 0.0,
        "slides_con_titulo": sum(1 for r in resultados_hss if r["tiene_titulo"] and r["coherencia"] != "no_aplica"),
        "slides_coherentes": sum(1 for r in resultados_hss if r["coherencia"] == "coherente"),
        "slides_debiles":    sum(1 for r in resultados_hss if r["coherencia"] == "debil"),
        "slides_no_coherentes": sum(1 for r in resultados_hss if r["coherencia"] == "no_coherente"),
    }

    res_nts = {
        "resultados":          resultados_nts,
        "nts_promedio":        round(sum(puntajes_nts_validos) / n_nts, 2) if n_nts else 0.0,
        "slides_relacionadas": sum(1 for r in resultados_nts if r["estado"] == "relacionada"),
        "slides_debiles":      sum(1 for r in resultados_nts if r["estado"] == "debil"),
        "slides_desconectadas":sum(1 for r in resultados_nts if r["estado"] == "desconectada"),
    }

    return {
        "hss":               res_hss,
        "nts":               res_nts,
        "clasificaciones":   clasificaciones,
        "temas_presentacion": temas_presentacion,
    }


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _parsear_arreglo_json(respuesta: str, origen: str) -> List[Dict]:
    """Extrae y parsea un arreglo JSON de la respuesta del modelo."""
    try:
        match = re.search(r"\[\s*\{.*\}\s*\]", respuesta, re.DOTALL)
        if match:
            limpio = re.sub(r"[\n\r\t]+", " ", match.group())
            return json.loads(limpio, strict=False)
    except Exception as e:
        print(f"[ERROR {origen}] Fallo al parsear JSON: {e}")
    return []


def _hss_vacio() -> Dict[str, Any]:
    return {
        "resultados": [],
        "hss_promedio": 0.0,
        "slides_con_titulo": 0,
        "slides_coherentes": 0,
        "slides_debiles": 0,
        "slides_no_coherentes": 0,
    }


def _nts_vacio() -> Dict[str, Any]:
    return {
        "resultados": [],
        "nts_promedio": 0.0,
        "slides_relacionadas": 0,
        "slides_debiles": 0,
        "slides_desconectadas": 0,
    }