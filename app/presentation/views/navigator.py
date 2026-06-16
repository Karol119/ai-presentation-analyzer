# app/presentation/views/navigator.py
"""
Orquestador de navegación entre vistas.

Regla de oro: ninguna vista importa a otra vista directamente.
Toda transición de pantalla pasa por este módulo.

Vistas registradas:
  - main_gui         → pantalla principal (sidebar + content + right panel)
  - analysis_gui     → pantalla de análisis (presentation_panel + results_panel)
  - history_gui      → pantalla de historial de versiones
  - presentation_gui → pantalla de modo presentación de clase (TT2)
  - performance_gui  → pantalla de rendimiento / desviaciones de tiempo (TT2)
"""

from app.presentation.views.ui_state import ui
from app.presentation.widgets.topbar import set_modo_analisis, set_modo_principal

# Estado interno del navegador extendido para TT2
_estado_navegador = {
    "vista_actual":         "main",   # "main" | "analysis" | "history" | "presentation" | "performance"
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

    # Ocultar body principal
    ui["body"].pack_forget()

    # Cargar vista dinámicamente
    from app.presentation.views.history_gui import mostrar_vista_historial
    mostrar_vista_historial(subject, nombre_presentacion)


def ir_a_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Transición: vista principal → vista de análisis detallado.
    """
    if _estado_navegador["vista_actual"] == "analysis":
        return

    _estado_navegador["vista_actual"] = "analysis"
    _estado_navegador["subject"] = subject
    _estado_navegador["nombre_presentacion"] = nombre_presentacion
    _estado_navegador["ruta_pdf"] = ruta_pdf

    # Ocultar body principal
    ui["body"].pack_forget()

    # Cambiar diseño de la barra superior
    set_modo_analisis(nombre_presentacion, ir_a_principal)

    # Cargar vista de análisis
    from app.presentation.views.analysis_gui import mostrar_vista_analisis
    mostrar_vista_analisis(subject, nombre_presentacion, ruta_pdf)


def ir_a_presentacion(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Transición: cualquier vista → modo presentación de clase (TT2).
    """
    if _estado_navegador["vista_actual"] == "presentation":
        return

    _estado_navegador["vista_actual"] = "presentation"
    _estado_navegador["subject"] = subject
    _estado_navegador["nombre_presentacion"] = nombre_presentacion
    _estado_navegador["ruta_pdf"] = ruta_pdf

    # Desempaquetar el cuerpo principal actual para limpiar la interfaz
    ui["body"].pack_forget()

    # Opcional: Modificamos la barra superior para reflejar que estamos dictando clase
    set_modo_analisis(f"Presentando: {nombre_presentacion}", ir_a_principal)

    # Carga perezosa de la nueva vista de presentación
    from app.presentation.views.presentation_gui import mostrar_vista_presentacion
    mostrar_vista_presentacion(ui["root"], subject, nombre_presentacion, ruta_pdf)


def ir_a_rendimiento(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Transición: cualquier vista → vista de rendimiento (desviaciones de tiempo).
    Mismo patrón que ir_a_presentacion: oculta el body, ajusta la topbar y
    delega en performance_gui mediante carga perezosa.
    """
    if _estado_navegador["vista_actual"] == "performance":
        return

    _estado_navegador["vista_actual"] = "performance"
    _estado_navegador["subject"] = subject
    _estado_navegador["nombre_presentacion"] = nombre_presentacion
    _estado_navegador["ruta_pdf"] = ruta_pdf

    # Ocultar body principal
    ui["body"].pack_forget()

    # Topbar en modo secundario con botón de regreso
    set_modo_analisis(f"Rendimiento: {nombre_presentacion}", ir_a_principal)

    # Carga perezosa de la vista de rendimiento
    from app.presentation.views.rendimiento_gui import mostrar_vista_rendimiento
    mostrar_vista_rendimiento(ui["root"], subject, nombre_presentacion, ruta_pdf)


def ir_a_principal():
    """
    Transición: cualquier vista secundaria → restauración de la vista principal.
    """
    # --- CANDADO DE SEGURIDAD PARA LA BARRA SUPERIOR ---
    # Si la proyección está activa, bloqueamos el botón de volver al inicio
    if ui.get("proyeccion_activa", False):
        print("[BLOQUEADO] No puedes regresar al menú mientras estás proyectando.")
        return
    # ---------------------------------------------------

    if _estado_navegador["vista_actual"] == "main":
        return

    # 1. Identificar qué vista activa destruir limpiamente
    if _estado_navegador["vista_actual"] == "analysis":
        from app.presentation.views.analysis_gui import ocultar_vista_analisis
        ocultar_vista_analisis()
    elif _estado_navegador["vista_actual"] == "history":
        from app.presentation.views.history_gui import ocultar_vista_historial
        ocultar_vista_historial()
    elif _estado_navegador["vista_actual"] == "presentation":
        from app.presentation.views.presentation_gui import ocultar_vista_presentacion
        ocultar_vista_presentacion()
    elif _estado_navegador["vista_actual"] == "performance":
        from app.presentation.views.rendimiento_gui import ocultar_vista_rendimiento
        ocultar_vista_rendimiento()

    _estado_navegador["vista_actual"] = "main"

    # 2. Restaurar topbar original
    set_modo_principal()

    # 3. Re-mostrar el body principal de la app
    ui["body"].pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Consultas de estado
# ---------------------------------------------------------------------------

def vista_actual() -> str:
    """Retorna la vista activa actual en el sistema."""
    return _estado_navegador["vista_actual"]


def get_contexto_analisis() -> dict:
    """Retorna el contexto completo de la sesión activa."""
    return {
        "subject": _estado_navegador["subject"],
        "nombre_presentacion": _estado_navegador["nombre_presentacion"],
        "ruta_pdf": _estado_navegador["ruta_pdf"]
    }