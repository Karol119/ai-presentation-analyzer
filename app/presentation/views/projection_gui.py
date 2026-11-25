# app/presentation/views/projection_gui.py
"""
Ventana de proyección (salida al dispositivo del alumno).

- crear_ventana_proyeccion: proyección REAL a pantalla completa en el monitor
  secundario/proyector elegido. Bloquea Alt+F4/Esc y se cierra con F11
  (salida temporal del modo DEMO; retirar para la versión final).

La ventana SOLO sigue a la vista del docente (capturar_teclas=False):
los atajos globales quedan reservados al visor del docente.
"""
import customtkinter as ctk


def _adjuntar_visor(ventana, ruta_pdf, capturar_teclas=False, **estilos):
    """Crea el visor sincronizado dentro de la ventana de proyección."""
    from app.presentation.widgets.presentation_mode.slides_viewer_panel import crear_visor_diapositivas

    ventana.visor = crear_visor_diapositivas(
        ventana,
        ruta_pdf=ruta_pdf,
        capturar_teclas=capturar_teclas,
        **estilos
    )
    ventana.visor.pack(fill="both", expand=True)
    ventana.after(300, ventana.visor.renderizar_slide_actual)

    def sincronizar_pagina(numero_pagina):
        if hasattr(ventana, 'visor'):
            ventana.visor.pagina_actual = numero_pagina
            ventana.visor.renderizar_slide_actual()

    ventana.sincronizar_pagina = sincronizar_pagina


def crear_ventana_proyeccion(master, ruta_pdf, pos_x=0, pos_y=0, ancho=800, alto=600, on_close=None, **kwargs):
    ventana = ctk.CTkToplevel(master, **kwargs)
    ventana.title("Proyección de Clase")

    ventana.geometry(f"{ancho}x{alto}+{pos_x}+{pos_y}")
    ventana.update_idletasks()

    # Simular pantalla completa nativa sin bordes ni barra de tareas superior
    ventana.overrideredirect(True)

    # 1. BLOQUEAR ALT+F4 en la ventana de proyección
    ventana.protocol("WM_DELETE_WINDOW", lambda: print("Bloqueado: Usa el panel de control para salir."))

    # 2. BLOQUEAR ESCAPE en la ventana de proyección
    ventana.bind("<Escape>", lambda e: "break")

    # --- [DEMO] Salida temporal: al proyectar en la pantalla principal, esta
    # ventana fullscreen tapa los controles de la app (y Esc/Alt+F4 están
    # bloqueados). F11 permite cerrar la proyección. Retirar para la versión final.
    ventana.bind("<F11>", lambda e: cerrar_ventana())

    _adjuntar_visor(ventana, ruta_pdf, fg_color="black", corner_radius=0, border_width=0)

    def cerrar_ventana(event=None):
        if hasattr(ventana, 'visor') and ventana.visor:
            ventana.visor.cerrar_documento()
        ventana.destroy()
        if on_close:
            on_close()

    ventana.cerrar = cerrar_ventana

    return ventana

