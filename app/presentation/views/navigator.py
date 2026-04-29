# app/presentation/views/navigator.py
"""
Orquestador de navegación entre vistas.

Regla de oro: ninguna vista importa a otra vista directamente.
Toda transición de pantalla pasa por este módulo.

Vistas registradas:
  - main_gui     → pantalla principal (sidebar + content + right panel)
  - analysis_gui → pantalla de análisis (presentation_panel + results_panel)
  - history_gui  → pantalla de historial de versiones
"""

from app.presentation.views.ui_state import ui
from app.presentation.widgets.topbar import set_modo_analisis, set_modo_principal

# Estado interno del navegador
_estado_navegador = {
    "vista_actual":         "main",   # "main" | "analysis" | "history"
    "subject":              None,
    "nombre_presentacion":  None,
    "ruta_pdf":             None,
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def ir_a_historial(subject: str, nombre_presentacion: str):
    """
    Transición: vista principal → vista de historial.
    """
    if _estado_navegador["vista_actual"] == "history":
        return

    _estado_navegador["vista_actual"] = "history"
    _estado_navegador["subject"] = subject
    _estado_navegador["nombre_presentacion"] = nombre_presentacion

    # 1. Ocultar vista principal
    ui["body"].pack_forget()

    # 2. Configurar el topbar para mostrar el título y botón de volver
    set_modo_analisis(f"Historial: {nombre_presentacion}", on_back=ir_a_principal)

    # 3. Construir y mostrar la vista de historial
    from app.presentation.views.history_gui import mostrar_vista_historial
    mostrar_vista_historial(subject, nombre_presentacion)


def ir_a_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Transición: vista principal/historial → vista de análisis.
    """
    if _estado_navegador["vista_actual"] == "analysis":
        return 

    # Si venimos del historial, ocultamos sus componentes primero
    if _estado_navegador["vista_actual"] == "history":
        from app.presentation.views.history_gui import ocultar_vista_historial
        ocultar_vista_historial()

    _estado_navegador["vista_actual"]       = "analysis"
    _estado_navegador["subject"]            = subject
    _estado_navegador["nombre_presentacion"]= nombre_presentacion
    _estado_navegador["ruta_pdf"]           = ruta_pdf

    # Ocultar body principal (si es que no estaba ya oculto)
    ui["body"].pack_forget()

    # Cambiar topbar
    set_modo_analisis(nombre_presentacion, on_back=ir_a_principal)

    # Construir y mostrar la vista de análisis
    from app.presentation.views.analysis_gui import mostrar_vista_analisis
    mostrar_vista_analisis(subject, nombre_presentacion, ruta_pdf)


def ir_a_principal():
    """
    Transición: cualquier vista → vista principal.
    """
    if _estado_navegador["vista_actual"] == "main":
        return

    # 1. Identificar qué vista destruir
    if _estado_navegador["vista_actual"] == "analysis":
        from app.presentation.views.analysis_gui import ocultar_vista_analisis
        ocultar_vista_analisis()
    elif _estado_navegador["vista_actual"] == "history":
        from app.presentation.views.history_gui import ocultar_vista_historial
        ocultar_vista_historial()

    _estado_navegador["vista_actual"] = "main"

    # 2. Restaurar topbar
    set_modo_principal()

    # 3. Mostrar body principal
    ui["body"].pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Consultas de estado
# ---------------------------------------------------------------------------

def vista_actual() -> str:
    """Retorna 'main', 'analysis' o 'history'."""
    return _estado_navegador["vista_actual"]


def get_contexto_analisis() -> dict:
    """
    Retorna el contexto completo de la sesión activa.
    """
    return {
        "subject":              _estado_navegador["subject"],
        "nombre_presentacion":  _estado_navegador["nombre_presentacion"],
        "ruta_pdf":             _estado_navegador["ruta_pdf"],
    }