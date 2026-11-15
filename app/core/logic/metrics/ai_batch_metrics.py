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
import sys
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
# CLASIFICACIÓN LOCAL: PORTADA DE SECCIÓN (SEPARADOR DE TEMA)
# ---------------------------------------------------------------------------

# Títulos que abren un tema o subtema del temario: inician con numeración
# jerárquica (ej. "2.3 El proceso de escritura", "2.3.1Elementos de la
# redacción", con o sin espacio/tabulador tras el número) o con la palabra
# unidad/tema/módulo seguida de número ("Unidad 3", "Tema 4.1").
_RE_NUMERACION_TEMARIO = re.compile(r"^\s*\d+(?:\.\d+)+")
_RE_UNIDAD_TEMARIO = re.compile(
    r"^\s*(?:unidad|tema|m[oó]dulo|cap[ií]tulo|bloque|secci[oó]n)\s+\d", re.IGNORECASE
)

# Máximo de palabras en el cuerpo para considerarla separador de sección.
# Coincide con el umbral de "texto_insuficiente" del Prompt 1: si el cuerpo
# desarrolla el tema con 15 palabras o más, es "contenido" aunque el título
# lleve numeración.
MAX_PALABRAS_CUERPO_PORTADA_SECCION = 15


def _es_portada_de_seccion(titulo: str, palabras_cuerpo: int) -> bool:
    """
    Detecta portadas de sección (separadores de tema) de forma determinista:
    título con numeración de temario y cuerpo vacío o mínimo.

    Ejemplo real: título '2.3	El proceso de escritura' con el subtítulo
    '2.3.1	Elementos de la redacción' como único cuerpo (5 palabras) → portada.
    """
    if not titulo or palabras_cuerpo >= MAX_PALABRAS_CUERPO_PORTADA_SECCION:
        return False
    return bool(_RE_NUMERACION_TEMARIO.match(titulo) or _RE_UNIDAD_TEMARIO.match(titulo))


# ---------------------------------------------------------------------------
# ANCLA DETERMINISTA DEL HSS (CLARIDAD DE ENCABEZADO)
# ---------------------------------------------------------------------------

def _resolver_puntaje_hss(
    puntaje_ia: Any,
    titulo: str,
    solapamiento: Any,
):
    """
    Ancla determinista del HSS para eliminar el vaivén entre ejecuciones.

    El veredicto "¿se corrige el título?" (estado BIEN si puntaje > 7) no puede
    depender de la interpretación subjetiva del modelo, que oscila entre
    ejecuciones con el mismo texto. Reglas objetivas con prioridad sobre la IA:

      1. Diapositiva sin título → puntaje ≤ 4 (siempre MEJORAR).
      2. El título comparte al menos un término clave con el contenido →
         puntaje mínimo 8 (siempre BIEN): el título nombra el tema que el
         cuerpo desarrolla. Es la regla que rompe el bucle de "corregir el
         título" sobre el título que la propia IA sugirió en el análisis
         anterior: si el título viene del contenido, el solapamiento existe.
      3. Sin solapamiento → se respeta el juicio de la IA (puede haber
         coherencia semántica por paráfrasis que el léxico no captura).

    Devuelve (puntaje, feedback, anotacion_log); feedback None = usar el de la IA.
    """
    if not (titulo or "").strip():
        puntaje = 4.0 if puntaje_ia is None else min(float(puntaje_ia), 4.0)
        return puntaje, "La diapositiva no tiene título.", "sin título → HSS anclado a ≤4 (MEJORAR)"

    if solapamiento:
        puntaje = 8.0 if puntaje_ia is None else float(puntaje_ia)
        if puntaje < 8.0:
            terminos = ", ".join(list(solapamiento)[:3])
            return 8.0, "", (
                f"la IA dio {puntaje_ia:g} pero hay solapamiento léxico título-contenido "
                f"({terminos}) → HSS anclado a 8 (coherente, no se corrige)"
            )
        return puntaje, "", ""

    puntaje = 5.0 if puntaje_ia is None else float(puntaje_ia)
    return puntaje, None, ""


# ---------------------------------------------------------------------------
# LOGS DE DEPURACIÓN (consola)
# ---------------------------------------------------------------------------

def _texto_seguro_para_log(texto: str) -> str:
    """Evita UnicodeEncodeError al imprimir texto extraído en consolas de Windows."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        texto.encode(encoding)
        return texto
    except UnicodeEncodeError:
        return texto.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _cortar_para_log(texto: str, maximo: int = 120) -> str:
    texto = _texto_seguro_para_log(texto)
    return texto if len(texto) <= maximo else texto[:maximo] + "…"


def _imprimir_resumen_carga(
    carga_lote: List[Dict[str, Any]],
    diapositivas: List[Dict[str, Any]],
) -> None:
    """
    Imprime, por diapositiva, el texto extraído que recibirá la IA (Prompt 1).
    Sirve para detectar fallos de extracción: si una diapositiva se ve llena de
    texto pero aquí aparecen pocas palabras, el extractor no la capturó
    (SmartArt, texto dentro de imágenes, etc.).
    """
    por_numero = {d.get("slide_number"): d for d in diapositivas}
    print("\n[CLASIFICADOR] ── Texto extraído que se envía a la IA (Prompt 1) ──")
    for item in carga_lote:
        num = item.get("slide_number")
        diap = por_numero.get(num, {})
        contenido_enviado = item.get("contenido", "")
        footer = " ".join(diap.get("footer", []))
        print(
            f"[CLASIFICADOR] Diap {num}: {len(contenido_enviado.split())} palabras enviadas | "
            f"{diap.get('image_count', 0)} imágenes | "
            f"{len(footer.split())} palabras excluidas como pie de página | "
            f"título: '{_cortar_para_log(item.get('titulo', ''))}'"
        )
    print("[CLASIFICADOR] Si una diapositiva llena de texto muestra pocas palabras aquí, falló la extracción.")


def _imprimir_texto_enviado(
    num: int,
    texto_enviado: str,
    footer: str,
) -> None:
    """Detalle del texto enviado a la IA para las diapositivas no 'contenido'."""
    print(
        f"    Texto enviado a la IA ({len(texto_enviado.split())} palabras): "
        f"'{_cortar_para_log(texto_enviado, 300)}'"
    )
    if footer:
        print(
            f"    Texto excluido como pie de página ({len(footer.split())} palabras): "
            f"'{_cortar_para_log(footer, 200)}'"
        )
    if not texto_enviado.strip():
        print("    >> ATENCIÓN: contenido vacío. Si la diapositiva se ve llena de texto, la extracción no lo captó")
        print("       (SmartArt, texto dentro de imágenes o en el pie de página).")


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

    # --- Log de depuración: qué texto extraído recibe la IA por diapositiva ---
    _imprimir_resumen_carga(carga_lote, diapositivas)

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
    return _consolidar_resultados(diapositivas, mapa_p1, mapa_p2, temas_presentacion, carga_lote)


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
    carga_lote: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Une los resultados de los 3 prompts con los cálculos locales ya existentes
    y construye el contrato de retorno idéntico al anterior.
    """
    # Texto exacto que recibió la IA por diapositiva (para los logs de depuración)
    texto_enviado = {
        item.get("slide_number"): item.get("contenido", "") for item in carga_lote
    }
    # Solapamiento léxico título-contenido calculado localmente (ancla del HSS)
    solapamientos = {
        item.get("slide_number"): item.get("hss_diagnostico", {}).get("solapamiento_lexico", [])
        for item in carga_lote
    }

    resultados_hss = []
    resultados_nts = []
    clasificaciones = {}

    puntajes_hss_validos = []
    puntajes_nts_validos = []

    print("\n[CLASIFICADOR] ── Decisión de tipo por diapositiva ──")

    for i, diap in enumerate(diapositivas):
        num = diap.get("slide_number")

        datos_p1 = mapa_p1.get(num, {})
        datos_p2 = mapa_p2.get(num, {})

        # ── Clasificación ──────────────────────────────────────────────────
        titulo_diap = diap.get("title", "").strip()
        cuerpo_diap = " ".join(diap.get("content", []))
        palabras_cuerpo = len(cuerpo_diap.split())
        texto_completo_diap = titulo_diap + " " + cuerpo_diap
        palabras_totales = len(texto_completo_diap.split())
        imagenes = diap.get("image_count", 0)
        tipo_ia = (datos_p1.get("tipo") or "contenido").lower()

        # Anulaciones locales que siempre tienen prioridad sobre la IA
        if _es_portada_de_seccion(titulo_diap, palabras_cuerpo):
            tipo_detectado = "portada"
            datos_p1 = {}  # ignorar datos de la IA para esta diapositiva
        elif imagenes > 0 and palabras_totales < 15:
            tipo_detectado = "visual"
            datos_p1 = {}
        elif palabras_totales < 5:
            tipo_detectado = "sin_contenido"
            datos_p1 = {}
        else:
            tipo_detectado = tipo_ia

        # ── Log de depuración: quién decidió el tipo y qué texto vio la IA ──
        anulada = (tipo_detectado != tipo_ia)
        origen = f"anulación local — la IA dijo '{tipo_ia}'" if anulada else "IA"
        print(
            f"[CLASIFICADOR] Diap {num} → '{tipo_detectado}' ({origen}) | "
            f"título: '{_cortar_para_log(titulo_diap, 60)}' | "
            f"cuerpo: {palabras_cuerpo} palabras | total: {palabras_totales} | img: {imagenes}"
        )
        if tipo_detectado == "texto_insuficiente" or anulada:
            _imprimir_texto_enviado(
                num,
                texto_enviado.get(num, ""),
                " ".join(diap.get("footer", [])),
            )

        tiempo_diap    = datos_p1.get("tiempo_estimado_segundos", 10)
        tipo_retorico  = datos_p1.get("tipo_retorico")  # puede ser None

        clasificaciones[num] = {
            "tipo":          tipo_detectado,
            "tiempo":        tiempo_diap,
            "tipo_retorico": tipo_retorico,  # NUEVO: el controller lo usa para reestructurar
        }

        es_contenido = (tipo_detectado == "contenido")

        # ── HSS ────────────────────────────────────────────────────────────
        # El puntaje pasa por el ancla determinista antes de decidir si la
        # métrica falla: elimina el vaivén 7/8 del modelo entre ejecuciones.
        puntaje_hss_crudo = datos_p1.get("hss_score")
        if es_contenido:
            puntaje_hss, feedback_hss, anotacion_hss = _resolver_puntaje_hss(
                puntaje_hss_crudo, titulo_diap, solapamientos.get(num, [])
            )
            if anotacion_hss:
                print(f"[HSS-ANCLA] Diap {num}: {anotacion_hss}")
            if feedback_hss is None:
                feedback_hss = datos_p1.get("hss_feedback", "")
            puntajes_hss_validos.append(puntaje_hss)
        else:
            puntaje_hss = 5.0
            feedback_hss = None

        resultados_hss.append({
            "slide_number": num,
            "tiene_titulo": bool(diap.get("title", "").strip()),
            "titulo":       diap.get("title", ""),
            "hss_score":    puntaje_hss if es_contenido else None,
            "coherencia":   _clasificar_puntaje_hss(puntaje_hss) if es_contenido else "no_aplica",
            "feedback_ai":  feedback_hss if es_contenido else None,
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