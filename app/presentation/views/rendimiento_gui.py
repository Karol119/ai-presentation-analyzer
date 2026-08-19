# app/presentation/views/rendimiento_gui.py
"""
Vista de Rendimiento (modo post-clase).

Mismo patrón que presentation_gui.py:
  - La transición SIEMPRE entra por navigator.ir_a_rendimiento(...).
  - Esta vista no importa a ninguna otra vista.
  - Orquesta DOS contenedores dentro de _contenedor_rendimiento:
        · el visor de diapositivas (reutiliza el de presentation_mode,
          es un widget genérico que solo pinta el PDF), y
        · el panel de datos de rendimiento (rendimiento_mode), que lleva
          el selector de grupo, el análisis por slide, la navegación y el reporte.
  - El panel de datos maneja la navegación y el visor le avisa de cada
    cambio de página mediante on_pagina_cambiada (idéntico a presentación).
"""

import customtkinter as ctk

_contenedor_rendimiento = None
_visor_panel = None
_datos_panel = None


def mostrar_vista_rendimiento(root, subject: str, nombre_presentacion: str, ruta_pdf: str):
    global _contenedor_rendimiento, _visor_panel, _datos_panel

    _contenedor_rendimiento = ctk.CTkFrame(master=root, fg_color="#EEF2F7", corner_radius=0)
    _contenedor_rendimiento.pack(fill="both", expand=True)

    # Contenedor 1: visor genérico de diapositivas (reutilizado)
    from app.presentation.widgets.presentation_mode.slides_viewer_panel import crear_visor_diapositivas
    # Contenedor 2: panel de datos propio de la vista de rendimiento
    from app.presentation.widgets.rendimiento_mode.rendimiento_data_panel import crear_panel_rendimiento

    _datos_panel = crear_panel_rendimiento(
        master=_contenedor_rendimiento,
        subject=subject,
        nombre_presentacion=nombre_presentacion,
        ruta_pdf=ruta_pdf,
        visor_referencia=None,
    )
    _datos_panel.pack(side="right", fill="y", padx=(6, 12), pady=12)

    _visor_panel = crear_visor_diapositivas(master=_contenedor_rendimiento, ruta_pdf=ruta_pdf)
    _visor_panel.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

    def evento_cambio_pagina(indice_slide):
        _datos_panel.actualizar_contenido_por_slide(indice_slide)

    _datos_panel.visor = _visor_panel
    _visor_panel.on_pagina_cambiada = evento_cambio_pagina

    root.after(300, _visor_panel.renderizar_slide_actual)


def ocultar_vista_rendimiento():
    global _contenedor_rendimiento, _visor_panel, _datos_panel

    # Cerrar modal de reporte si quedó abierto
    if _datos_panel is not None and _datos_panel.winfo_exists():
        if hasattr(_datos_panel, "cerrar_modal"):
            _datos_panel.cerrar_modal()

    if _visor_panel is not None:
        _visor_panel.cerrar_documento()
        _visor_panel.destroy()
        _visor_panel = None

    if _datos_panel is not None:
        _datos_panel.destroy()
        _datos_panel = None

    if _contenedor_rendimiento is not None:
        _contenedor_rendimiento.destroy()
        _contenedor_rendimiento = None