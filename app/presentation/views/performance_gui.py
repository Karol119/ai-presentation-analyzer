# app/presentation/views/performance_gui.py
"""
Vista de Rendimiento (dashboard vertical).

Entra por navigator.ir_a_rendimiento(...). Carga los dos JSON una vez
(análisis IA + reporte de tiempos) y los inyecta a:

    · Resumen (fila de tarjetas compactas, arriba)
    · Gráfica (ocupa todo el espacio inferior; pestañas de grupo, scroll y hover)

Las desviaciones ya no van fijas: se abren en una ventana desde el botón
"Desviaciones" de la gráfica. El filtro de grupo vive en la gráfica y, al
cambiar, la vista actualiza el resumen.
"""

import json
import customtkinter as ctk

from app.core.controller.presentation_controller import (
    orquestar_obtener_analisis,
    orquestar_obtener_reporte_tiempo,
)
from app.core.controller.subject_controller import obtener_id_materia_controlador

_contenedor_rendimiento = None
_resumen_panel = None
_grafica_panel = None


def mostrar_vista_rendimiento(root, subject: str, nombre_presentacion: str, ruta_pdf=None):
    global _contenedor_rendimiento, _resumen_panel, _grafica_panel

    _contenedor_rendimiento = ctk.CTkFrame(master=root, fg_color="#EEF2F7", corner_radius=0)
    _contenedor_rendimiento.pack(fill="both", expand=True)

    id_materia = obtener_id_materia_controlador(subject)
    analisis, grupos = {}, {}
    raw_a = orquestar_obtener_analisis(nombre_presentacion, id_materia)
    if raw_a:
        try:
            analisis = json.loads(raw_a)
        except Exception as e:
            print(f"[performance_gui] análisis: {e}")
    raw_r = orquestar_obtener_reporte_tiempo(nombre_presentacion, id_materia)
    if raw_r:
        try:
            grupos = json.loads(raw_r).get("grupos", {}) or {}
        except Exception as e:
            print(f"[performance_gui] reporte: {e}")

    grupo_inicial = next(iter(grupos.keys()), None)

    from app.presentation.widgets.performance_mode.performance_summary_panel import crear_resumen_rendimiento
    from app.presentation.widgets.performance_mode.performance_chart_panel import crear_grafica_rendimiento
    from app.presentation.widgets.performance_mode.performance_deviations_panel import abrir_reporte_desviaciones

    # Resumen (arriba, compacto)
    _resumen_panel = crear_resumen_rendimiento(_contenedor_rendimiento, analisis, grupos)
    _resumen_panel.pack(side="top", fill="x", padx=12, pady=(12, 8))

    def _on_grupo(g):
        _resumen_panel.actualizar(g)

    def _on_reporte(g):
        abrir_reporte_desviaciones(root, analisis, grupos, g)

    # Gráfica (ocupa todo el espacio restante)
    _grafica_panel = crear_grafica_rendimiento(_contenedor_rendimiento, nombre_presentacion,
                                               analisis, grupos,
                                               on_grupo_cambiado=_on_grupo,
                                               on_ver_reporte=_on_reporte)
    _grafica_panel.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 12))

    _resumen_panel.actualizar(grupo_inicial)
    root.after(260, lambda: _grafica_panel.dibujar(grupo_inicial))


def ocultar_vista_rendimiento():
    global _contenedor_rendimiento, _resumen_panel, _grafica_panel

    for p in (_resumen_panel, _grafica_panel):
        if p is not None:
            p.destroy()
    _resumen_panel = _grafica_panel = None

    if _contenedor_rendimiento is not None:
        _contenedor_rendimiento.destroy()
        _contenedor_rendimiento = None