# app/presentation/widgets/analysis/results_panel.py
"""
Panel derecho de la vista de análisis.
Muestra los resultados de evaluación de la diapositiva activa.
Se sincroniza con presentation_panel mediante callback.
"""

import customtkinter as ctk
from app.presentation.views.ui_state import ui
from app.presentation.widgets.analysis.presentation_panel import set_on_pagina_cambiada

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

# Referencias internas a widgets que se actualizan al cambiar de diapositiva
_widgets = {
    "titulo_slide":    None,
    "contenido_frame": None,
}


def build_results_panel(subject: str, nombre_presentacion: str):
    """
    Construye el panel derecho de resultados.
    """
    panel = ctk.CTkFrame(
        ui["analysis_body"],
        fg_color="white",
        corner_radius=14,
        width=320,
        border_width=1,
        border_color="#E8ECF2",
    )
    panel.pack(side="right", fill="y", padx=(6, 12), pady=12)
    panel.pack_propagate(False)
    ui["results_panel"] = panel

    _build_header(panel)
    _build_slide_info(panel)
    _build_results_area(panel)

    # Registrar callback para sincronización con el visor
    set_on_pagina_cambiada(_on_pagina_cambiada)

    # Mostrar resultados de la primera diapositiva
    _on_pagina_cambiada(0)


# ---------------------------------------------------------------------------
# Construcción del layout
# ---------------------------------------------------------------------------

def _build_header(parent):
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(18, 10))

    icon_bg = ctk.CTkFrame(
        header, fg_color=COLOR_GUINDA_SUAVE,
        corner_radius=8, width=30, height=30
    )
    icon_bg.pack(side="left", padx=(0, 10))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(
        icon_bg, text="📊", font=ctk.CTkFont(size=14), text_color=COLOR_GUINDA
    ).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        header,
        text="Resultados de evaluación",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(side="left")

    ctk.CTkFrame(parent, height=1, fg_color="#F1F5F9").pack(fill="x", padx=16, pady=(0, 10))


def _build_slide_info(parent):
    """Muestra el número de la diapositiva activa."""
    _widgets["titulo_slide"] = ctk.CTkLabel(
        parent,
        text="",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#94A3B8",
        anchor="w",
    )
    _widgets["titulo_slide"].pack(fill="x", padx=16, pady=(0, 12))


def _build_results_area(parent):
    """Área scrollable donde se muestran los resultados por diapositiva."""
    scroll = ctk.CTkScrollableFrame(
        parent,
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    scroll.pack(fill="both", expand=True, padx=12, pady=(0, 16))
    _widgets["contenido_frame"] = scroll


# ---------------------------------------------------------------------------
# Actualización dinámica al cambiar de diapositiva
# ---------------------------------------------------------------------------

def _on_pagina_cambiada(indice: int):
    """
    Callback invocado por presentation_panel cada vez que el usuario navega.
    Recarga los resultados correspondientes a la diapositiva activa.
    """
    from app.presentation.widgets.analysis.presentation_panel import get_total_paginas

    total = get_total_paginas()

    # Actualizar etiqueta de diapositiva
    if _widgets["titulo_slide"]:
        _widgets["titulo_slide"].configure(
            text=f"Diapositiva {indice + 1} de {total}"
        )

    # Limpiar resultados anteriores
    frame = _widgets["contenido_frame"]
    if not frame:
        return
    for w in frame.winfo_children():
        w.destroy()

    # Cargar resultados simulados para esta diapositiva
    resultados = _obtener_resultados_simulados(indice)
    _renderizar_resultados(frame, resultados)


def _renderizar_resultados(parent, resultados: list):
    """Dibuja las tarjetas de resultados en el panel."""
    for resultado in resultados:
        _build_resultado_card(parent, resultado)


def _build_resultado_card(parent, resultado: dict):
    """
    Tarjeta individual de resultado.
    resultado = {
        "titulo":     str,
        "valor":      str,
        "descripcion": str,
        "color":      str,   # color del indicador lateral
    }
    """
    card = ctk.CTkFrame(
        parent,
        fg_color="#F8FAFC",
        corner_radius=10,
        border_width=1,
        border_color="#E8ECF2",
    )
    card.pack(fill="x", pady=(0, 8))

    # Indicador de color lateral
    ctk.CTkFrame(
        card,
        width=4,
        fg_color=resultado["color"],
        corner_radius=2,
    ).pack(side="left", fill="y", padx=(0, 0), pady=8)

    content = ctk.CTkFrame(card, fg_color="transparent")
    content.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    # Título del resultado
    ctk.CTkLabel(
        content,
        text=resultado["titulo"],
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#334155",
        anchor="w",
    ).pack(fill="x")

    # Valor destacado
    ctk.CTkLabel(
        content,
        text=resultado["valor"],
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=resultado["color"],
        anchor="w",
    ).pack(fill="x")

    # Descripción
    if resultado.get("descripcion"):
        ctk.CTkLabel(
            content,
            text=resultado["descripcion"],
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#94A3B8",
            anchor="w",
            wraplength=240,
            justify="left",
        ).pack(fill="x", pady=(2, 0))


# ---------------------------------------------------------------------------
# Datos simulados — se reemplazarán con lógica real de análisis
# ---------------------------------------------------------------------------

def _obtener_resultados_simulados(indice: int) -> list:
    """
    Genera resultados de ejemplo para la diapositiva indicada.
    Placeholder hasta que se implemente el análisis real.
    """
    import random
    random.seed(indice)  # Seed fijo por diapositiva para que sean consistentes

    densidad   = random.randint(10, 95)
    complejidad = random.randint(5, 80)

    color_densidad    = _color_por_valor(densidad)
    color_complejidad = _color_por_valor(complejidad)

    return [
        {
            "titulo":      "Densidad de texto",
            "valor":       f"{densidad}%",
            "descripcion": _descripcion_densidad(densidad),
            "color":       color_densidad,
        },
        {
            "titulo":      "Complejidad léxica",
            "valor":       f"{complejidad}%",
            "descripcion": _descripcion_complejidad(complejidad),
            "color":       color_complejidad,
        },
        {
            "titulo":      "Elementos visuales",
            "valor":       f"{random.randint(0, 8)}",
            "descripcion": "Imágenes, gráficas y formas detectadas.",
            "color":       COLOR_ORO,
        },
    ]


def _color_por_valor(valor: int) -> str:
    if valor < 40:  return "#22C55E"   # Verde — bajo
    if valor < 70:  return COLOR_ORO   # Oro  — medio
    return "#EF4444"                    # Rojo — alto


def _descripcion_densidad(valor: int) -> str:
    if valor < 40:  return "Diapositiva con poco texto. Buena legibilidad."
    if valor < 70:  return "Cantidad de texto moderada."
    return "Demasiado texto. Se recomienda reducir el contenido."


def _descripcion_complejidad(valor: int) -> str:
    if valor < 40:  return "Vocabulario accesible para el público."
    if valor < 70:  return "Complejidad léxica moderada."
    return "Vocabulario muy técnico. Considera simplificar."