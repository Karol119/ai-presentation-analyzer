# app/presentation/widgets/analysis/results_panel.py
import customtkinter as ctk
import json
import os
from app.presentation.views.ui_state import ui
from app.presentation.widgets.analysis.presentation_panel import set_on_pagina_cambiada
from app.presentation.views import navigator

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

_widgets = {
    "titulo_slide":    None,
    "contenido_frame": None,
    "cached_data":     None,
}

def build_results_panel(subject: str, nombre_presentacion: str):
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

    _cargar_datos_json(nombre_presentacion)
    _build_header(panel)
    
    _widgets["contenido_frame"] = ctk.CTkScrollableFrame(
        panel, fg_color="transparent", scrollbar_button_color="#E8ECF2"
    )
    _widgets["contenido_frame"].pack(fill="both", expand=True, padx=10, pady=5)

    set_on_pagina_cambiada(_on_pagina_cambiada)
    _on_pagina_cambiada(0)

def _cargar_datos_json(nombre_presentacion):
    try:
        contexto = navigator.get_contexto_analisis()
        ruta_pdf = contexto.get("ruta_pdf")
        directorio = os.path.dirname(ruta_pdf)
        nombre_base = os.path.splitext(nombre_presentacion)[0]
        ruta_json = os.path.join(directorio, f"{nombre_base}_analysis.json")

        if os.path.exists(ruta_json):
            with open(ruta_json, "r", encoding="utf-8") as f:
                _widgets["cached_data"] = json.load(f)
    except Exception as e:
        print(f"Error cargando JSON: {e}")
        _widgets["cached_data"] = None

def _on_pagina_cambiada(indice: int):
    if _widgets["titulo_slide"]:
        _widgets["titulo_slide"].configure(text=f"Diapositiva {indice + 1}")

    container = _widgets["contenido_frame"]
    for child in container.winfo_children():
        child.destroy()

    data = _widgets["cached_data"]
    if not data or "slides" not in data or indice >= len(data["slides"]):
        return

    slide_data = data["slides"][indice]

    # REGLA: Si omitida es True, no mostrar nada
    if slide_data.get("omitida", False):
        ctk.CTkLabel(container, text="Diapositiva omitida del análisis", 
                     font=("Inter", 12, "italic"), text_color="#64748B").pack(pady=40)
        return

    # 1. Etiqueta de Tipo
    _renderizar_tipo(container, slide_data)

    # 2. Apartado de Calificación (Score y Zona)
    _renderizar_calificacion(container, slide_data)

    # 3. Métricas (Diseño: métrica: valor | etiqueta: estado + feedback)
    _renderizar_metricas(container, slide_data)

    # 4. Botón de Reestructuración
    _renderizar_boton_reestructuracion(container, slide_data)

def _renderizar_tipo(parent, slide_data):
    tipo_raw = slide_data.get("tipo", "N/A")
    tipo_texto = tipo_raw.replace("_", " ").capitalize()
    
    # Solo mostrar una etiqueta
    lbl_tipo = ctk.CTkLabel(
        parent, text=tipo_texto, fg_color=COLOR_GUINDA, 
        text_color="white", corner_radius=6, font=("Inter", 11, "bold"), padx=10
    )
    lbl_tipo.pack(pady=(10, 5))

    if tipo_raw.lower() == "visual":
        alerta = ctk.CTkLabel(
            parent, text="⚠️ Actualmente la IA no es capaz de procesar imágenes.",
            text_color="#92400E", wraplength=250, font=("Inter", 10, "bold"),
            fg_color="#FEF3C7", corner_radius=4
        )
        alerta.pack(fill="x", pady=5)

def _renderizar_calificacion(parent, slide_data):
    score = slide_data.get("score_slide", "N/A")
    zona = slide_data.get("zona_slide", "N/A")

    frame = ctk.CTkFrame(parent, fg_color="#F1F5F9", corner_radius=8)
    frame.pack(fill="x", pady=10)

    ctk.CTkLabel(frame, text=f"Score Slide: {score}", font=("Inter", 13, "bold")).pack(side="left", padx=10, pady=8)
    
    color_zona = COLOR_ORO if str(zona).lower() != "pobre" else "#EF4444"
    ctk.CTkLabel(frame, text=str(zona).upper(), font=("Inter", 11, "bold"), text_color=color_zona).pack(side="right", padx=10)

def _renderizar_metricas(parent, slide_data):
    metricas = slide_data.get("metricas")
    if not metricas: return

    for nombre, info in metricas.items():
        if not info: continue
        
        m_frame = ctk.CTkFrame(parent, fg_color="transparent")
        m_frame.pack(fill="x", pady=8)

        # Diseño: metrica: valor | etiqueta: indica el estado
        header_txt = f"{nombre.upper()}: {info.get('valor', 0)}  |  {info.get('estado', 'N/A')}"
        ctk.CTkLabel(m_frame, text=header_txt, font=("Inter", 11, "bold"), anchor="w", text_color="#1E293B").pack(fill="x")
        
        # Feedback
        ctk.CTkLabel(
            m_frame, text=info.get('feedback', ''), font=("Inter", 11),
            text_color="#64748B", wraplength=260, justify="left"
        ).pack(fill="x", pady=(2, 0))

def _renderizar_boton_reestructuracion(parent, slide_data):
    reest = slide_data.get("reestructuracion")
    if reest and reest.get("diapositivas_generadas"):
        btn = ctk.CTkButton(
            parent, text="Ver sugerencias de reestructuración",
            fg_color=COLOR_GUINDA, hover_color="#4D1324",
            command=lambda: _abrir_modal_reestructuracion(reest["diapositivas_generadas"])
        )
        btn.pack(pady=20, fill="x", padx=10)

def _abrir_modal_reestructuracion(sugerencias, boton_disparador):
    """Abre una ventana modal bloqueando la interacción con el resto de la app."""
    if _widgets["modal_abierto"]:
        return

    _widgets["modal_abierto"] = True
    boton_disparador.configure(state="disabled")

    # Crear la ventana
    modal = ctk.CTkToplevel(ui["root"])
    modal.title("Sugerencias de Mejora")
    modal.geometry("500x600")
    
    # --- CONFIGURACIÓN MODAL (BLOQUEO) ---
    modal.transient(ui["root"])    # Se mantiene siempre encima de la ventana principal
    modal.grab_set()               # Bloquea interacción con otras ventanas
    modal.attributes("-topmost", True)
    modal.configure(fg_color="white")
    
    def al_cerrar():
        """Libera el bloqueo global y el del botón al cerrar."""
        _widgets["modal_abierto"] = False
        if boton_disparador.winfo_exists():
            boton_disparador.configure(state="normal")
        modal.grab_release()       # Libera los eventos para el resto de la app
        modal.destroy()

    # Capturar el cierre tanto por botón como por la "X" de la ventana
    modal.protocol("WM_DELETE_WINDOW", al_cerrar)

    # --- ENCABEZADO DINÁMICO ---
    num_sugerencias = len(sugerencias)
    texto_rec = (f"Se recomienda dividir la diapositiva en {num_sugerencias} diapositivas:" 
                 if num_sugerencias > 1 else 
                 "Se recomienda redactar el contenido de la siguiente manera:")

    ctk.CTkLabel(
        modal, text=texto_rec, 
        font=("Inter", 13, "bold"), text_color=COLOR_GUINDA,
        wraplength=450, justify="center"
    ).pack(pady=(20, 10), padx=20)

    # --- CONTENIDO ---
    scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    for i, sug in enumerate(sugerencias, 1):
        f = ctk.CTkFrame(scroll, fg_color="#F8FAFC", border_width=1, border_color="#E2E8F0")
        f.pack(fill="x", pady=10)
        
        titulo_label = f"Propuesta {i}" if num_sugerencias > 1 else "Contenido Optimizado"
        
        ctk.CTkLabel(f, text=f"{titulo_label}: {sug.get('titulo_sugerido', '')}", 
                     font=("Inter", 12, "bold"), text_color=COLOR_GUINDA, anchor="w").pack(fill="x", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(f, text=sug.get('contenido_optimizado', ''), font=("Inter", 11),
                     wraplength=400, justify="left").pack(fill="x", padx=15, pady=(0, 15))

    # Botón de cierre explícito dentro del modal
    ctk.CTkButton(modal, text="Entendido", command=al_cerrar, fg_color=COLOR_GUINDA, corner_radius=10).pack(pady=10)

def _build_header(parent):
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", padx=15, pady=(15, 10))
    
    ctk.CTkLabel(header, text="ANÁLISIS DE IA", font=("Inter", 10, "bold"), text_color=COLOR_ORO).pack(anchor="w")
    _widgets["titulo_slide"] = ctk.CTkLabel(header, text="Cargando...", font=("Inter", 18, "bold"), text_color="#1E293B")
    _widgets["titulo_slide"].pack(anchor="w")