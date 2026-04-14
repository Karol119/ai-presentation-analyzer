# app/presentation/views/navigator.py
"""
Orquestador de navegación entre vistas.

Regla de oro: ninguna vista importa a otra vista directamente.
Toda transición de pantalla pasa por este módulo.

Vistas registradas:
  - main_gui     → pantalla principal (sidebar + content + right panel)
  - analysis_gui → pantalla de análisis (presentation_panel + results_panel)
"""

from app.presentation.views.ui_state import ui
from app.presentation.widgets.topbar import set_modo_analisis, set_modo_principal

# Estado interno del navegador
_estado_navegador = {
    "vista_actual":         "main",   # "main" | "analysis"
    "subject":              None,
    "nombre_presentacion":  None,
    "ruta_pdf":             None,
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def ir_a_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Transición: vista principal → vista de análisis.

    1. Oculta el body principal
    2. Cambia el topbar al modo análisis
    3. Construye y muestra la vista de análisis
    """
    if _estado_navegador["vista_actual"] == "analysis":
        return  # Evitar transiciones duplicadas

    _estado_navegador["vista_actual"]       = "analysis"
    _estado_navegador["subject"]            = subject
    _estado_navegador["nombre_presentacion"]= nombre_presentacion
    _estado_navegador["ruta_pdf"]           = ruta_pdf

    # 1. Ocultar vista principal
    ui["body"].pack_forget()

    # 2. Cambiar topbar
    set_modo_analisis(nombre_presentacion, on_back=ir_a_principal)

    # 3. Construir y mostrar la vista de análisis
    #    Import local para evitar dependencias circulares en el arranque
    from app.presentation.views.analysis_gui import mostrar_vista_analisis
    mostrar_vista_analisis(subject, nombre_presentacion, ruta_pdf)


def ir_a_principal():
    """
    Transición: vista de análisis → vista principal.

    1. Destruye la vista de análisis
    2. Restaura el topbar al modo principal
    3. Muestra de nuevo el body principal
    """
    if _estado_navegador["vista_actual"] == "main":
        return  # Evitar transiciones duplicadas

    _estado_navegador["vista_actual"] = "main"

    # 1. Destruir vista de análisis
    from app.presentation.views.analysis_gui import ocultar_vista_analisis
    ocultar_vista_analisis()

    # 2. Restaurar topbar
    set_modo_principal()

    # 3. Mostrar body principal
    ui["body"].pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Consultas de estado
# ---------------------------------------------------------------------------

def vista_actual() -> str:
    """Retorna 'main' o 'analysis'."""
    return _estado_navegador["vista_actual"]


def get_contexto_analisis() -> dict:
    """
    Retorna el contexto completo de la sesión de análisis activa.
    Usado por presentation_panel y results_panel para obtener sus datos.
    """
    return {
        "subject":              _estado_navegador["subject"],
        "nombre_presentacion":  _estado_navegador["nombre_presentacion"],
        "ruta_pdf":             _estado_navegador["ruta_pdf"],
    }