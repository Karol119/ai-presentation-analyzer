# app/core/logic/metrics/ai_restructure.py
"""
Fase 2 del análisis IA: 2 prompts secuenciales.

  Prompt 4 — Plan de restructuración (decide QUÉ y CUÁNTO, sin escribir)
  Prompt 5 — Redacción final (escribe usando el plan ya resuelto)

El contrato de retorno es idéntico al anterior para no tocar el controller:
  {
    slide_number: {
      "preguntas":           [...],
      "datos_curiosos":      [...],
      "diapositivas_generadas": [
        { "titulo_sugerido", "contenido_optimizado", "tipo_retorico_aplicado" }
      ]
    }
  }
"""

import json
import re
from typing import Dict, Any, List

from app.infrastructure.ai.llm_provider import consultar_modelo
from app.infrastructure.ai.prompts import (
    PROMPT_4_PLAN,          SI_PLAN,
    PROMPT_5_REDACCION,     SI_REDACCION,
    PROMPT_6_MATERIAL_APOYO, SI_MATERIAL_APOYO,
)
from app.core.logic.text_extractor import serializar_bloques_para_prompt


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA PÚBLICO
# ---------------------------------------------------------------------------

def reestructurar_diapositivas_lote(
    diapositivas_a_corregir: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """
    Recibe el lote de diapositivas con sus métricas y ejecuta 2 prompts
    en secuencia: primero el plan, luego la redacción basada en ese plan.

    Campos esperados en cada elemento del lote (vienen del controller):
        slide_number            int
        titulo                  str   ← NUEVO (viene del campo title original)
        tipo_retorico           str|None ← NUEVO (viene de clasificaciones)
        icd_valor               float|None ← NUEVO (valor numérico del ICD)
        palabras_count          int   ← NUEVO (conteo real de palabras WPS)
        content                 list[str]
        requiere_reestructuracion bool
        feedback_a_corregir     str   (formato "ICD: ... | WPS: ... | HSS: ... | NTS: ...")
    """
    if not diapositivas_a_corregir:
        return {}

    # ── PROMPT 4: Plan ──────────────────────────────────────────────────────
    carga_plan = _construir_carga_plan(diapositivas_a_corregir)
    prompt_4   = PROMPT_4_PLAN.format(
        batch_data=json.dumps(carga_plan, ensure_ascii=False, indent=2)
    )

    print("[IA REESTRUCTURACIÓN] Prompt 4: generando plan de restructuración...")
    respuesta_plan = consultar_modelo(prompt_4, system_instruction=SI_PLAN)
    planes         = _parsear_arreglo_json(respuesta_plan, "Prompt 4 (Plan)")

    if not planes:
        print("[ADVERTENCIA] Prompt 4 no devolvió un plan válido. Se omite la restructuración.")
        return {}

    # Indexar planes por slide_number para cruzarlo con los datos originales
    mapa_planes = {item.get("slide_number"): item for item in planes}

    # ── PROMPT 5: Redacción ─────────────────────────────────────────────────
    carga_redaccion = _construir_carga_redaccion(diapositivas_a_corregir, mapa_planes)
    prompt_5        = PROMPT_5_REDACCION.format(
        batch_data=json.dumps(carga_redaccion, ensure_ascii=False, indent=2)
    )

    print("[IA REESTRUCTURACIÓN] Prompt 5: redactando contenido optimizado...")
    respuesta_final = consultar_modelo(prompt_5, system_instruction=SI_REDACCION)
    resultados      = _parsear_arreglo_json(respuesta_final, "Prompt 5 (Redacción)")

    # ── Construir mapa de retorno con el contrato esperado por el controller ─
    mapa_reestructurado: Dict[int, Dict[str, Any]] = {}
    for item in resultados:
        num = item.get("slide_number")
        if num is None:
            continue
        mapa_reestructurado[num] = {
            "preguntas":              item.get("preguntas", []),
            "datos_curiosos":         item.get("datos_curiosos", []),
            "diapositivas_generadas": item.get("diapositivas_generadas", []),
        }

    return mapa_reestructurado


# ---------------------------------------------------------------------------
# CONSTRUCCIÓN DE CARGAS
# ---------------------------------------------------------------------------

def _construir_carga_plan(
    diapositivas: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Prepara el batch para Prompt 4.
    Incluye los valores numéricos de las métricas (no solo el feedback de texto)
    para que el modelo pueda aplicar el árbol de decisión con precisión.
    """
    carga = []
    for d in diapositivas:
        # Usar content_blocks[] si está disponible (preserva estructura párrafo/lista).
        # Fallback a " ".join(content[]) para compatibilidad hacia atrás.
        content_blocks = d.get("content_blocks")
        if content_blocks:
            contenido_original = serializar_bloques_para_prompt(content_blocks)
        else:
            contenido_original = " ".join(d.get("content", []))

        # Determinar cuáles métricas fallan a partir del feedback
        # (el feedback es None/vacío cuando la métrica está en rango)
        feedback_raw = d.get("feedback_a_corregir", "")
        metricas_que_fallan = _extraer_metricas_que_fallan(feedback_raw)

        entrada = {
            "slide_number":              d["slide_number"],
            "titulo":                    d.get("titulo", ""),
            "tipo_retorico":             d.get("tipo_retorico"),
            "requiere_reestructuracion": d.get("requiere_reestructuracion", True),
            "contenido_original":        contenido_original[:1500],
            "palabras_count":            d.get("palabras_count", 0),
            "icd_valor":                 d.get("icd_valor"),
            "metricas_que_fallan":       metricas_que_fallan,
            "feedback_detallado": {
                "icd": _extraer_segmento_feedback(feedback_raw, "ICD"),
                "wps": _extraer_segmento_feedback(feedback_raw, "WPS"),
                "hss": _extraer_segmento_feedback(feedback_raw, "HSS"),
                "nts": _extraer_segmento_feedback(feedback_raw, "NTS"),
            },
        }
        carga.append(entrada)
    return carga


def _construir_carga_redaccion(
    diapositivas: List[Dict[str, Any]],
    mapa_planes: Dict[int, Dict],
) -> List[Dict[str, Any]]:
    """
    Prepara el batch para Prompt 5.
    Combina los datos originales con el plan generado por Prompt 4,
    de modo que el modelo solo necesita escribir, no decidir.
    """
    carga = []
    for d in diapositivas:
        num = d["slide_number"]
        # Usar content_blocks[] si está disponible (preserva estructura párrafo/lista).
        # Fallback a " ".join(content[]) para compatibilidad hacia atrás.
        content_blocks = d.get("content_blocks")
        if content_blocks:
            contenido_original = serializar_bloques_para_prompt(content_blocks)
        else:
            contenido_original = " ".join(d.get("content", []))

        plan = mapa_planes.get(num, {})

        # Si el plan dice "reescribir_una" o "dividir", hay trabajo de escritura.
        # Si no hay plan para esta diapositiva, la marcamos como sin_cambios.
        accion = plan.get("accion", "sin_cambios")

        entrada = {
            "slide_number":       num,
            "titulo":             d.get("titulo", ""),
            "tipo_retorico":      d.get("tipo_retorico"),
            "contenido_original": contenido_original[:1500],
            "palabras_count":     d.get("palabras_count", 0),
            "accion":             accion,
            # El plan resuelto: el modelo solo tiene que ejecutarlo
            "diapositivas_plan":  plan.get("diapositivas_plan", []),
            "razon_plan":         plan.get("razon", ""),
        }
        carga.append(entrada)
    return carga


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _extraer_metricas_que_fallan(feedback: str) -> List[str]:
    """
    Dado el string concatenado "ICD: ... | WPS: ... | HSS: ... | NTS: ...",
    devuelve la lista de métricas que tienen feedback no vacío (es decir, fallaron).
    Una métrica está en rango cuando su segmento de feedback es vacío o 'None'.
    """
    fallan = []
    for metrica in ["ICD", "WPS", "HSS", "NTS"]:
        segmento = _extraer_segmento_feedback(feedback, metrica)
        if segmento and segmento.strip().lower() not in ("", "none"):
            fallan.append(metrica.lower())
    return fallan


def _extraer_segmento_feedback(feedback: str, metrica: str) -> str:
    """
    Extrae el texto correspondiente a una métrica del string concatenado.
    Formato esperado: "ICD: texto | WPS: texto | HSS: texto | NTS: texto"
    """
    patron = rf"{metrica}:\s*(.*?)(?:\s*\|\s*(?:ICD|WPS|HSS|NTS):|$)"
    match  = re.search(patron, feedback, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


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


# ---------------------------------------------------------------------------
# FUNCIÓN PÚBLICA: MATERIAL DE APOYO (TODAS LAS DIAPOSITIVAS DE CONTENIDO)
# ---------------------------------------------------------------------------

def generar_material_apoyo_lote(
    diapositivas_contenido: list,
) -> dict:
    """
    Genera preguntas y datos curiosos para TODAS las diapositivas de tipo
    "contenido", usando el Prompt 6 de forma independiente a la reestructuración.

    Se ejecuta en paralelo con reestructurar_diapositivas_lote() desde el controller.

    Args:
        diapositivas_contenido: lista de dicts con al menos:
            slide_number, content[], content_blocks[] (opcional), titulo

    Returns:
        Dict[int, Dict] mapeando slide_number → {preguntas, datos_curiosos}
    """
    if not diapositivas_contenido:
        return {}

    carga = []
    for d in diapositivas_contenido:
        content_blocks = d.get("content_blocks")
        if content_blocks:
            from app.core.logic.text_extractor import serializar_bloques_para_prompt
            contenido_original = serializar_bloques_para_prompt(content_blocks)
        else:
            contenido_original = " ".join(d.get("content", []))

        carga.append({
            "slide_number":       d["slide_number"],
            "contenido_original": contenido_original[:1200],
        })

    prompt = PROMPT_6_MATERIAL_APOYO.format(
        batch_data=__import__("json").dumps(carga, ensure_ascii=False, indent=2)
    )

    print("[IA MATERIAL] Prompt 6: generando preguntas y datos curiosos para todas las slides...")
    respuesta = consultar_modelo(prompt, system_instruction=SI_MATERIAL_APOYO)
    resultados = _parsear_arreglo_json(respuesta, "Prompt 6 (Material de Apoyo)")

    mapa: dict = {}
    for item in resultados:
        num = item.get("slide_number")
        if num is not None:
            mapa[num] = {
                "preguntas":     item.get("preguntas", []),
                "datos_curiosos": item.get("datos_curiosos", []),
            }
    return mapa