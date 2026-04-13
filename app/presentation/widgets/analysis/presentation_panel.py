# app/presentation/widgets/analysis/presentation_panel.py
"""
Panel izquierdo de la vista de análisis.
Renderiza el PDF de la presentación página por página usando PyMuPDF.
Permite navegar con botones < > o teclado.
"""

import fitz  # PyMuPDF
import customtkinter as ctk
from PIL import Image
import io

from app.presentation.views.ui_state import ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

# Estado interno del visor — vive mientras analysis_body existe
_visor = {
    "doc":          None,   # fitz.Document abierto
    "pagina_actual": 0,
    "total_paginas": 0,
    "label_imagen": None,
    "label_contador": None,
    "on_pagina_cambiada": None,  # Callback para notificar a results_panel
}


def build_presentation_panel(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Construye el panel izquierdo con el visor de diapositivas.
    """
    _visor["on_pagina_cambiada"] = None

    panel = ctk.CTkFrame(
        ui["analysis_body"],
        fg_color="white",
        corner_radius=14,
        border_width=1,
        border_color="#E8ECF2",
    )
    panel.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)
    ui["presentation_panel"] = panel

    # Abrir el PDF
    _abrir_pdf(ruta_pdf)

    if _visor["doc"] is None:
        _build_error_state(panel, ruta_pdf)
        return

    # Construir layout
    _build_header(panel, nombre_presentacion)
    _build_slide_area(panel)
    _build_navigation(panel)

    # Mostrar primera diapositiva
    _mostrar_pagina(0)


# ---------------------------------------------------------------------------
# API pública para sincronización con results_panel
# ---------------------------------------------------------------------------

def set_on_pagina_cambiada(callback):
    """
    Registra un callback que se llama cada vez que el usuario navega.
    results_panel lo usa para actualizar los resultados de la diapositiva activa.
    callback(indice: int)
    """
    _visor["on_pagina_cambiada"] = callback


def get_pagina_actual() -> int:
    return _visor["pagina_actual"]


def get_total_paginas() -> int:
    return _visor["total_paginas"]


# ---------------------------------------------------------------------------
# Construcción del layout
# ---------------------------------------------------------------------------

def _build_header(parent, nombre_presentacion: str):
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", padx=20, pady=(18, 10))

    ctk.CTkLabel(
        header,
        text=nombre_presentacion,
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color=COLOR_GUINDA,
        anchor="w",
    ).pack(side="left")

    ctk.CTkFrame(parent, height=1, fg_color="#F1F5F9").pack(fill="x", padx=20)


def _build_slide_area(parent):
    """Área central donde se renderiza la diapositiva activa."""
    slide_container = ctk.CTkFrame(parent, fg_color="#F8FAFC", corner_radius=10)
    slide_container.pack(fill="both", expand=True, padx=20, pady=(16, 0))

    _visor["label_imagen"] = ctk.CTkLabel(slide_container, text="")
    _visor["label_imagen"].place(relx=0.5, rely=0.5, anchor="center")


def _build_navigation(parent):
    """Barra inferior con botones < > y contador de páginas."""
    nav = ctk.CTkFrame(parent, fg_color="transparent")
    nav.pack(pady=16)

    btn_prev = ctk.CTkButton(
        nav,
        text="<",
        width=38, height=38,
        corner_radius=19,
        fg_color="white",
        hover_color=COLOR_GUINDA_SUAVE,
        text_color=COLOR_GUINDA,
        border_width=1,
        border_color="#E8ECF2",
        font=ctk.CTkFont(size=14, weight="bold"),
        command=_pagina_anterior,
    )
    btn_prev.pack(side="left", padx=(0, 12))

    _visor["label_contador"] = ctk.CTkLabel(
        nav,
        text="",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#475569",
        width=70,
    )
    _visor["label_contador"].pack(side="left")

    btn_next = ctk.CTkButton(
        nav,
        text=">",
        width=38, height=38,
        corner_radius=19,
        fg_color=COLOR_GUINDA,
        hover_color="#4D1324",
        text_color="white",
        font=ctk.CTkFont(size=14, weight="bold"),
        command=_pagina_siguiente,
    )
    btn_next.pack(side="left", padx=(12, 0))

    # Navegación por teclado mientras la vista de análisis esté activa
    ui["root"].bind("<Left>",  lambda e: _pagina_anterior())
    ui["root"].bind("<Right>", lambda e: _pagina_siguiente())


def _build_error_state(parent, ruta_pdf: str):
    """Muestra un mensaje de error si el PDF no pudo cargarse."""
    ctk.CTkLabel(
        parent,
        text=f"⚠️  No se pudo abrir el archivo:\n{ruta_pdf}",
        font=ctk.CTkFont(family="Segoe UI", size=13),
        text_color="#EF4444",
        justify="center",
    ).place(relx=0.5, rely=0.5, anchor="center")


# ---------------------------------------------------------------------------
# Lógica de navegación y renderizado
# ---------------------------------------------------------------------------

def _abrir_pdf(ruta_pdf: str):
    """Abre el documento PDF y registra el total de páginas."""
    try:
        _visor["doc"]          = fitz.open(ruta_pdf)
        _visor["total_paginas"] = len(_visor["doc"])
        _visor["pagina_actual"] = 0
    except Exception as e:
        print(f"Error al abrir PDF: {e}")
        _visor["doc"] = None


def _mostrar_pagina(indice: int):
    """Renderiza la página indicada y la muestra en el label."""
    doc   = _visor["doc"]
    label = _visor["label_imagen"]

    if doc is None or label is None:
        return

    # Obtener dimensiones del contenedor para escalar correctamente
    label.update_idletasks()
    container = label.master
    ancho_max = max(container.winfo_width()  - 40, 400)
    alto_max  = max(container.winfo_height() - 40, 300)

    # Renderizar página con PyMuPDF
    page   = doc[indice]
    matriz = fitz.Matrix(2.0, 2.0)          # Escala 2x para buena resolución
    pixmap = page.get_pixmap(matrix=matriz)

    # Convertir a PIL Image
    img_pil = Image.open(io.BytesIO(pixmap.tobytes("png")))

    # Escalar manteniendo proporción
    img_pil.thumbnail((ancho_max, alto_max), Image.LANCZOS)

    img_ctk = ctk.CTkImage(light_image=img_pil, size=img_pil.size)
    label.configure(image=img_ctk, text="")
    label._image = img_ctk  # Evitar garbage collection

    # Actualizar contador
    total = _visor["total_paginas"]
    if _visor["label_contador"]:
        _visor["label_contador"].configure(
            text=f"{indice + 1} / {total}"
        )

    # Notificar a results_panel si hay callback registrado
    if _visor["on_pagina_cambiada"]:
        _visor["on_pagina_cambiada"](indice)


def _pagina_anterior():
    if _visor["pagina_actual"] > 0:
        _visor["pagina_actual"] -= 1
        _mostrar_pagina(_visor["pagina_actual"])


def _pagina_siguiente():
    if _visor["pagina_actual"] < _visor["total_paginas"] - 1:
        _visor["pagina_actual"] += 1
        _mostrar_pagina(_visor["pagina_actual"])

def cerrar_pdf():
    """
    Cierra el documento PDF activo para liberar el archivo de la memoria 
    y permitir que Windows lo pueda eliminar o modificar después.
    """
    if _visor["doc"] is not None:
        _visor["doc"].close()
        _visor["doc"] = None