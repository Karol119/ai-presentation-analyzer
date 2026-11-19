# app/presentation/views/projection_gui.py
"""
Ventanas de proyección (salida al dispositivo del alumno).

- crear_ventana_proyeccion: proyección REAL a pantalla completa en el monitor
  secundario/proyector elegido. Bloquea Alt+F4/Esc y se cierra con F11
  (salida temporal del modo DEMO; retirar para la versión final).
- crear_mini_proyeccion: SIMULACIÓN de la salida de proyección en una sola
  pantalla: mini ventana flotante (siempre visible) que muestra la vista del
  alumno sincronizada, para demostrar/grabar la doble vista sin proyector.

Ambas ventanas SOLO siguen a la vista del docente (capturar_teclas=False):
los atajos globales quedan reservados al visor del docente.
"""
import customtkinter as ctk
import fitz  # PyMuPDF (solo para leer la proporción de las diapositivas)

COLOR_GUINDA = "#6A1B31"


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


def crear_mini_proyeccion(master, ruta_pdf, on_close=None, ancho_mini=380):
    """Mini ventana flotante que simula la salida de proyección (vista del alumno).

    - Siempre visible (topmost) para poder grabar la pantalla con ella encima.
    - Arrastrable por su barra de título y con cierre normal (X / Alt+F4).
    - Tamaño adaptado a la proporción real de las diapositivas.
    """
    # Proporción real de la presentación (soporta 4:3, 16:9, tamaños mixtos)
    try:
        with fitz.open(ruta_pdf) as doc:
            r = doc[0].rect
            proporcion = (r.height / r.width) if r.width > 0 else 9 / 16
    except Exception:
        proporcion = 9 / 16
    proporcion = max(0.4, min(proporcion, 1.2))  # evita ventanas extremas

    alto_header = 30
    ancho_total = ancho_mini
    alto_total = int(round(ancho_mini * proporcion)) + alto_header

    ventana = ctk.CTkToplevel(master)
    ventana.title("🖥 Proyección (simulada) — Vista del alumno")
    ventana.attributes("-topmost", True)  # permanece visible sobre la app

    # Posición inicial: borde derecho, centro vertical (no tapa controles clave;
    # puede arrastrarse libremente desde la barra de título)
    sw = master.winfo_screenwidth()
    sh = master.winfo_screenheight()
    pos_x = max(0, sw - ancho_total - 30)
    pos_y = max(60, (sh - alto_total) // 2 - 60)
    ventana.geometry(f"{ancho_total}x{alto_total}+{pos_x}+{pos_y}")
    ventana.update_idletasks()

    # Encabezado que identifica la ventana como la salida del proyector
    header = ctk.CTkFrame(ventana, fg_color=COLOR_GUINDA, corner_radius=0, height=alto_header)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(
        header,
        text="🖥 SALIDA DE PROYECCIÓN · Vista del alumno",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color="white",
    ).pack(expand=True)

    _adjuntar_visor(ventana, ruta_pdf, fg_color="black", corner_radius=0,
                    border_width=2, border_color=COLOR_GUINDA)

    def cerrar_ventana(event=None):
        if hasattr(ventana, 'visor') and ventana.visor:
            ventana.visor.cerrar_documento()
        ventana.destroy()
        if on_close:
            on_close()

    ventana.protocol("WM_DELETE_WINDOW", cerrar_ventana)
    ventana.cerrar = cerrar_ventana

    return ventana
