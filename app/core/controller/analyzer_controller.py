# app/core/controller/analyzer_controller.py
"""
Orquestador principal del análisis de presentaciones.
Solo delega: no imprime, no selecciona archivos, no hace I/O de ningún tipo.
Devuelve un dict estructurado que la GUI, la CLI o los tests pueden consumir.
"""
from pathlib import Path

# Logica de Negocio
from app.core.logic.text_extractor import extraer_datos_pptx
from app.core.logic.slide_classifier import clasificar_diapositiva
from app.core.logic.metrics.icd import calcular_icd  # Cambiado a individual
from app.core.logic.metrics.word_count import calcular_wps # Cambiado a individual
from app.core.logic.metrics.header_structure import calcular_hss # Cambiado a individual
from app.core.logic.metrics.narrative_thread import calcular_nts_individual # Nueva función
from app.core.logic.presentation_score import calcular_score_global, calcular_score_slide

# Infraestructura (Ollama)
from app.infrastructure.ollama.ollama_client import inicializar_motor_llm
from app.infrastructure.ollama.ollama_service import clasificar_tipo_diapositiva
from app.infrastructure.ollama.coherencia_service import verificar_coherencia_titulo
from app.infrastructure.ollama.narrativa_service import verificar_hilo_narrativo
from app.infrastructure.ollama.diagnostic_service import generar_diagnostico_metrico
from app.infrastructure.ollama.restructure_service import reestructurar_slide

_TIPOS_OMITIDOS = {"portada", "indice", "referencias", "cierre", "sin_contenido"}

def analizar_presentacion(ruta: str, ask_install_callback=None, progress_callback=None) -> dict:
    def notificar(m): 
        if progress_callback: progress_callback(m)

    # 0. Inicialización de IA
    notificar("Iniciando motor de Inteligencia Artificial...")
    llm_ok = inicializar_motor_llm(ask_install_callback)
    
    if not llm_ok:
        notificar("⚠️ Advertencia: Análisis básico sin IA activado.")
        
    notificar("Extrayendo datos de la presentación...")
    datos = extraer_datos_pptx(ruta)
    
    slides_finales = [] # Usaremos este nombre consistentemente
    lista_original = datos["slides"]
    total = len(lista_original)

    # 1. Procesamiento en un solo bucle
    for idx, s in enumerate(lista_original):
        n = s["slide_number"]
        notificar(f"Analizando diapositiva {n} de {total}...")

        # Clasificación
        s["clasificacion"] = clasificar_diapositiva(
            s, llm_fn=clasificar_tipo_diapositiva if llm_ok else None
        )
        tipo = s["clasificacion"]["tipo"]

        # Si es omitida, cerramos el ciclo de la slide aquí
        if s["clasificacion"]["excluir"] or tipo in _TIPOS_OMITIDOS:
            slides_finales.append({
                "slide_number": n, "tipo": tipo, "omitida": True,
                "score": None, "metricas_raw": None, "feedback": None, "restructura": None,
            })
            continue

        # 2. Métricas Individuales
        m_icd = calcular_icd(s)
        m_wps = calcular_wps(s)
        m_hss = calcular_hss(s, llm_fn=verificar_coherencia_titulo if llm_ok else None)
        
        # NTS necesita la slide anterior para el hilo narrativo
        s_previa = lista_original[idx-1] if idx > 0 else None
        m_nts = calcular_nts_individual(s, s_previa, llm_fn=verificar_hilo_narrativo if llm_ok else None)

        # 3. Score de la slide
        ss = calcular_score_slide(m_icd, m_wps, m_hss, m_nts)

        # 4. Feedback y Reestructura IA (Solo si necesita mejorar)
        feedback = None
        restructura = None
        
        if ss["necesita_recomendacion"] and llm_ok:
            # Obtener texto de contexto para la IA
            txt_prev = " ".join(lista_original[idx-1].get("content", [])) if idx > 0 else None
            txt_next = " ".join(lista_original[idx+1].get("content", [])) if idx < total-1 else None
            
            notificar(f"Generando recomendaciones para slide {n}...")
            feedback = generar_diagnostico_metrico(s, ss["metricas"], txt_prev, txt_next)
            
            notificar(f"Reestructurando contenido para slide {n}...")
            restructura = reestructurar_slide(s, ss["metricas"], txt_prev, txt_next, notificar)

        # Guardar resultado de la slide
        slides_finales.append({
            "slide_number": n, "tipo": tipo, "omitida": False,
            "score": ss, 
            "metricas_raw": {"icd": m_icd, "wps": m_wps, "hss": m_hss, "nts": m_nts},
            "feedback": feedback, "restructura": restructura
        })

    # 5. Score Global (Consolidado)
    # Debes ajustar calcular_score_global para que reciba la lista de slides_finales
    notificar("Consolidando resultados finales...")
    
    # Simulación de la estructura esperada por tu actual calcular_score_global
    # para evitar romper el código mientras ajustas los otros módulos:
    res_icd_list = {"resultados": [s["metricas_raw"]["icd"] for s in slides_finales if not s["omitida"]]}
    res_wps_list = {"wps_promedio": sum(s["metricas_raw"]["wps"]["wps_score"] for s in slides_finales if not s["omitida"]) / total if total > 0 else 0}
    res_hss_list = {"hss_promedio": sum(s["metricas_raw"]["hss"]["hss_score"] for s in slides_finales if not s["omitida"]) / total if total > 0 else 0}
    res_nts_list = {"nts_promedio": sum(s["metricas_raw"]["nts"]["nts_score"] for s in slides_finales if not s["omitida"]) / total if total > 0 else 0}

    score_global = calcular_score_global(res_icd_list, res_wps_list, res_hss_list, res_nts_list)

    return {
        "nombre": Path(ruta).name,
        "score_global": score_global,
        "slides": slides_finales,
    }

    
def exportar_resultado_json(resultado: dict) -> dict:
    """
    Transforma el resultado de analizar_presentacion() a un dict
    limpio y serializable, listo para JSON o para la GUI.

    Estructura de salida:
    {
        "presentacion": {
            "nombre":       str,
            "score_global": float,
            "zona_global":  str,
            "desglose": {
                "icd": float,
                "wps": float,
                "hss": float,
                "nts": float
            }
        },
        "diapositivas": [
            {
                "numero":   int,
                "tipo":     str,
                "omitida":  bool,

                // Solo si omitida=False:
                "score":    float,
                "zona":     str,
                "metricas": {
                    "icd": { "valor": float, "zona": str,  "aprobada": bool },
                    "wps": { "palabras": int,               "aprobada": bool },
                    "hss": { "coherencia": str,             "aprobada": bool },
                    "nts": { "estado": str,                 "aprobada": bool }
                },
                "aspectos_a_mejorar": ["icd", "wps", ...],

                "feedback": {
                    "icd":           str | null,
                    "wps":           str | null,
                    "hss":           str | null,
                    "nts":           str | null,
                    "preguntas":     [str, ...],
                    "datos_curiosos": [str, ...]
                } | null,

                "reestructura": {
                    "exito":    bool,
                    "intentos": int,
                    "diapositivas": [
                        {
                            "titulo":    str,
                            "contenido": [str, ...]
                        },
                        ...
                    ],
                    "metricas_pendientes": [str, ...]
                } | null
            },
            ...
        ]
    }
    """
    sg = resultado["score_global"]

    salida = {
        "presentacion": {
            "nombre":       resultado["nombre"],
            "score_global": sg["score_global"],
            "zona_global":  sg["zona_global"],
            "desglose": {
                "icd": sg["scores_metrica"]["icd"],
                "wps": sg["scores_metrica"]["wps"],
                "hss": sg["scores_metrica"]["hss"],
                "nts": sg["scores_metrica"]["nts"],
            },
        },
        "diapositivas": [],
    }

    for slide in resultado["slides"]:
        n = slide["slide_number"]

        # ── Slide omitida (portada, índice, etc.) ─────────────────────────
        if slide["omitida"]:
            # Diccionario amigable para la GUI
            nombres_tipos = {
                "portada": "Portada",
                "indice": "Índice / Temario",
                "referencias": "Referencias / Bibliografía",
                "cierre": "Cierre / Conclusión",
                "sin_contenido": "Diapositiva sin texto"
            }
            nombre_legible = nombres_tipos.get(slide["tipo"], slide["tipo"])

            salida["diapositivas"].append({
                "numero":  n,
                "tipo":    slide["tipo"],
                "omitida": True,
                "mensaje_omision": f"Clasificada como '{nombre_legible}'. Esta diapositiva no requiere evaluación métrica.",
                
                # Rellenamos con nulos para mantener la misma estructura del JSON
                "score": None,
                "zona": "N/A",
                "metricas": None,
                "aspectos_a_mejorar": [],
                "feedback": None,
                "reestructura": None
            })
            continue

        ss  = slide["score"]
        raw = slide["metricas_raw"]

        # ── Métricas individuales normalizadas ────────────────────────────
        metricas_limpias = {
            "icd": {
                "valor":    raw["icd"].get("icd"),
                "zona":     raw["icd"].get("zona"),
                "aprobada": "icd" not in ss["aspectos_mejorar"],
            },
            "wps": {
                "palabras": raw["wps"].get("palabras"),
                "aprobada": "wps" not in ss["aspectos_mejorar"],
            },
            "hss": {
                "coherencia": raw["hss"].get("coherencia"),
                "aprobada":   "hss" not in ss["aspectos_mejorar"],
            },
            "nts": {
                "estado":   raw["nts"].get("estado"),
                "aprobada": "nts" not in ss["aspectos_mejorar"],
            },
        }

        # ── Feedback ──────────────────────────────────────────────────────
        fb = slide["feedback"]
        feedback_limpio = None
        if fb:
            feedback_limpio = {
                "icd":           fb.get("icd"),
                "wps":           fb.get("wps"),
                "hss":           fb.get("hss"),
                "nts":           fb.get("nts"),
                "preguntas":     fb.get("preguntas", []),
                "datos_curiosos": fb.get("datos_curiosos", []),
            }

        # ── Reestructura ──────────────────────────────────────────────────
        re = slide["restructura"]
        restructura_limpia = None
        if re:
            restructura_limpia = {
                "exito":    re["exito"],
                "intentos": re["intentos"],
                "diapositivas": [
                    {
                        "titulo":    d["titulo"],
                        "contenido": d["contenido"],
                    }
                    for d in re["diapositivas"]
                ],
                "metricas_pendientes": re.get("metricas_fallidas_final", []),
            }

        salida["diapositivas"].append({
            "numero":             n,
            "tipo":               slide["tipo"],
            "omitida":            False,
            "score":              ss["score"],
            "zona":               ss["zona"],
            "metricas":           metricas_limpias,
            "aspectos_a_mejorar": ss["aspectos_mejorar"],
            "feedback":           feedback_limpio,
            "reestructura":       restructura_limpia,
        })

    return salida