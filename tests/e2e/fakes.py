# tests/e2e/fakes.py
"""
Dobles de prueba (test doubles) para la dependencia externa de IA (Gemini).

Se usan para ejecutar de forma reproducible y sin red:
  * `metricas_ia_fake`   -> sustituye a `calcular_metricas_ia_lote`
  * `reestructura_fake`  -> sustituye a `reestructurar_diapositivas_lote`
  * `material_fake`      -> sustituye a `generar_material_apoyo_lote`

IMPORTANTE: no son pruebas contra la API real. Se distinguen explícitamente en
el registro de resultados como "servicio simulado".
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest import mock


def metricas_ia_fake(diapositivas, temario):
    """Devuelve el mismo contrato que `calcular_metricas_ia_lote`, con valores fijos."""
    hss, nts, clasificaciones = [], [], {}
    for d in diapositivas:
        n = d.get("slide_number")
        clasificaciones[n] = {"tipo": "contenido", "tiempo": 10, "tipo_retorico": "introduccion"}
        hss.append({
            "slide_number": n,
            "tiene_titulo": bool(d.get("title")),
            "titulo": d.get("title", ""),
            "hss_score": 8.0,
            "coherencia": "coherente",
            "feedback_ai": "Encabezado claro y relacionado con el contenido.",
        })
        nts.append({
            "slide_number": n,
            "sim_anterior": 0.5,
            "sim_promedio": 0.5,
            "nts_score": 8.0,
            "estado": "relacionada",
            "feedback_ai": "Continuidad temática adecuada.",
        })
    return {
        "hss": {"resultados": hss, "hss_promedio": 8.0},
        "nts": {"resultados": nts, "nts_promedio": 8.0},
        "clasificaciones": clasificaciones,
        "temas_presentacion": [
            {
                "unidad": "Unidad Temática 1. Conceptos Fundamentales",
                "temas": [
                    {
                        "tema": "1.1 Introducción",
                        "subtemas": ["1.1.1 Definiciones básicas"],
                    }
                ],
            }
        ],
    }


def reestructura_fake(diapositivas):
    """Finge que ninguna diapositiva requiere reestructuración."""
    return {d.get("slide_number"): {} for d in diapositivas}


def material_fake(diapositivas):
    """Material de apoyo determinista (preguntas y datos curiosos)."""
    return {
        d.get("slide_number"): {
            "preguntas": ["¿Qué es un protocolo de red?"],
            "datos_curiosos": ["El modelo OSI se publicó en 1984."],
        }
        for d in diapositivas
    }


@contextmanager
def ia_simulada(conectada: bool = True, error: Exception | None = None):
    """
    Parchea el controlador de análisis para no depender de red ni de la API.

    conectada=False simula `verificar_conexion_ia` fallando con `error`.
    conectada=True parchea las métricas y el enriquecimiento con los dobles.
    """
    import app.core.controller.analyzer_controller as ac

    parches = []
    if not conectada:
        exc = error or RuntimeError("SIN CONEXIÓN A INTERNET: simulada en pruebas.")
        parches.append(mock.patch.object(ac, "verificar_conexion_ia", side_effect=exc))
    else:
        parches.append(mock.patch.object(ac, "verificar_conexion_ia", return_value=None))
        parches.append(mock.patch.object(ac, "calcular_metricas_ia_lote", side_effect=metricas_ia_fake))
        parches.append(mock.patch.object(ac, "reestructurar_diapositivas_lote", side_effect=reestructura_fake))
        parches.append(mock.patch.object(ac, "generar_material_apoyo_lote", side_effect=material_fake))

    iniciados = [p.start() for p in parches]
    try:
        yield
    finally:
        for p in reversed(parches):
            p.stop()


def _generar_miniatura_fake(ruta_pptx, ruta_salida_png):
    """Sustituye a la miniatura por PowerPoint COM (no requiere Office)."""
    from PIL import Image
    ruta_salida_png = str(ruta_salida_png)
    Image.new("RGB", (960, 540), (238, 242, 247)).save(ruta_salida_png)
    return True


def _generar_pdf_fake(ruta_pptx, ruta_salida_pdf):
    """Sustituye a la exportación PDF por COM: genera un PDF real de N páginas."""
    from pathlib import Path
    from app.core.logic.text_extractor import contar_diapositivas
    from tests.e2e import sandbox
    n = contar_diapositivas(ruta_pptx) or 1
    sandbox.crear_pdf_minimo(Path(ruta_salida_pdf), n)
    return True


@contextmanager
def offimatica_simulada():
    """
    Parchea la generación de miniatura/PDF (PowerPoint vía COM) por equivalentes
    locales y deterministas. Permite ejecutar el flujo de carga sin Office.
    """
    import app.data.persistence as per
    with mock.patch.object(per, "generar_miniatura", side_effect=_generar_miniatura_fake), \
         mock.patch.object(per, "generar_pdf", side_effect=_generar_pdf_fake):
        yield
