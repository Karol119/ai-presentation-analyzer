# app/presentation/widgets/history_evaluation.py
import customtkinter as ctk
import json
import os
from app.presentation.views.ui_state import ui

COLOR_GUINDA = "#6A1B31"
COLOR_ORO    = "#BC955C"

def mostrar_modal_evaluacion_json(ruta_pdf, version_num):
    """
    Lee el archivo JSON de análisis y muestra las métricas, 
    calificaciones y feedback de cada diapositiva en un modal.
    """
    # 1. Armar la ruta del JSON basándonos en el PDF de la versión
    directorio = os.path.dirname(ruta_pdf)
    nombre_base = os.path.splitext(os.path.basename(ruta_pdf))[0]
    ruta_json = os.path.join(directorio, f"{nombre_base}_analysis.json")
    
    # 2. Cargar el archivo JSON
    if not os.path.exists(ruta_json):
        _mostrar_alerta(f"No se encontró el archivo de análisis en:\n{ruta_json}")
        return
        
    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            datos_ia = json.load(f)
    except Exception as e:
        _mostrar_alerta(f"Error al leer el archivo JSON:\n{e}")
        return
        
    # 3. Construir la UI del Modal
    modal = ctk.CTkToplevel(ui["root"])
    modal.title(f"Evaluación de Métricas - Versión {version_num}")
    modal.geometry("560x680")
    modal.grab_set()
    modal.focus_force()
    modal.configure(fg_color="white")
    modal.resizable(False, False)

    # Franja decorativa superior
    ctk.CTkFrame(modal, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    ctk.CTkLabel(
        modal, text=f"Evaluación y Métricas (Versión {version_num})",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=COLOR_GUINDA
    ).pack(pady=(25, 10))

    # Contenedor con Scroll
    scroll = ctk.CTkScrollableFrame(
        modal, fg_color="#F8FAFC", border_width=1, border_color="#E2E8F0", corner_radius=12
    )
    scroll.pack(fill="both", expand=True, padx=25, pady=10)

    # 4. Extraer y mostrar las diapositivas
    slides = datos_ia.get("slides", [])
    
    for slide in slides:
        num_slide = slide.get("slide_number", "?")
        
        # Título de la diapositiva
        ctk.CTkLabel(
            scroll, text=f"📌 Diapositiva {num_slide}", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#1E293B", anchor="w"
        ).pack(fill="x", padx=10, pady=(15, 5))

        # Si fue omitida, se indica y se salta a la siguiente
        if slide.get("omitida", False):
            ctk.CTkLabel(
                scroll, text="Diapositiva omitida del análisis detallado.", 
                font=("Inter", 12, "italic"), text_color="#64748B", anchor="w"
            ).pack(fill="x", padx=20, pady=(0, 10))
            continue

        # Contenedor de la evaluación de esta diapositiva
        f = ctk.CTkFrame(scroll, fg_color="white", border_width=1, border_color="#CBD5E1", corner_radius=8)
        f.pack(fill="x", padx=10, pady=5)

        # Barra de Score y Zona (Igual al results_panel)
        score = slide.get("score_slide", "N/A")
        zona = slide.get("zona_slide", "N/A")
        
        header_frame = ctk.CTkFrame(f, fg_color="#F1F5F9", corner_radius=8)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(header_frame, text=f"Score Slide: {score}", font=("Inter", 13, "bold"), text_color="#1E293B").pack(side="left", padx=10, pady=8)
        color_zona = COLOR_ORO if str(zona).lower() != "pobre" else "#EF4444"
        ctk.CTkLabel(header_frame, text=str(zona).upper(), font=("Inter", 11, "bold"), text_color=color_zona).pack(side="right", padx=10)

        # Rendimiento de cada métrica
        metricas = slide.get("metricas", {})
        for nombre, info in metricas.items():
            if not info: continue
            
            m_frame = ctk.CTkFrame(f, fg_color="transparent")
            m_frame.pack(fill="x", padx=15, pady=(5, 8))

            header_txt = f"{nombre.upper()}: {info.get('valor', 0)}  |  {info.get('estado', 'N/A')}"
            ctk.CTkLabel(m_frame, text=header_txt, font=("Inter", 11, "bold"), anchor="w", text_color="#1E293B").pack(fill="x")
            
            ctk.CTkLabel(
                m_frame, text=info.get('feedback', ''), font=("Inter", 11),
                text_color="#64748B", wraplength=420, justify="left", anchor="w"
            ).pack(fill="x", pady=(2, 0))

    ctk.CTkButton(
        modal, text="Cerrar", command=modal.destroy,
        fg_color=COLOR_GUINDA, hover_color="#4D1324",
        width=130, height=36, corner_radius=10
    ).pack(pady=20)

def _mostrar_alerta(mensaje):
    modal = ctk.CTkToplevel(ui["root"])
    modal.title("Aviso")
    modal.geometry("450x220")
    modal.grab_set()
    modal.configure(fg_color="white")
    ctk.CTkFrame(modal, fg_color="#EF4444", height=6, corner_radius=0).pack(fill="x")
    ctk.CTkLabel(modal, text=mensaje, font=("Segoe UI", 12), text_color="#1E293B", wraplength=400, justify="center").pack(expand=True, padx=20)
    ctk.CTkButton(modal, text="Aceptar", command=modal.destroy, fg_color=COLOR_GUINDA, width=120).pack(pady=20)