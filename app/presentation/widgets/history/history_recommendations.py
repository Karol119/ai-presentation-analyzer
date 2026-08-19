# app/presentation/widgets/history_recommendations.py
import customtkinter as ctk
import json
import os
from app.presentation.views.ui_state import ui

COLOR_GUINDA = "#6A1B31"
COLOR_ORO    = "#BC955C"

def mostrar_modal_recomendaciones_json(ruta_pdf, version_num):
    """
    Lee el archivo JSON de análisis asociado a esta versión y muestra
    las recomendaciones de reestructuración en un modal interactivo.
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
    modal.title(f"Recomendaciones de IA - Versión {version_num}")
    modal.geometry("560x650")
    modal.grab_set()
    modal.focus_force()
    modal.configure(fg_color="white")
    modal.resizable(False, False)

    # Franja decorativa superior
    ctk.CTkFrame(modal, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    ctk.CTkLabel(
        modal, text=f"Mejoras Sugeridas (Versión {version_num})",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=COLOR_GUINDA
    ).pack(pady=(25, 10))

    # Contenedor con Scroll para leer todo cómodamente
    scroll = ctk.CTkScrollableFrame(
        modal, fg_color="#F8FAFC", border_width=1, border_color="#E2E8F0", corner_radius=12
    )
    scroll.pack(fill="both", expand=True, padx=25, pady=10)

    # 4. Extraer las recomendaciones directamente del JSON
    hay_recomendaciones = False
    slides = datos_ia.get("slides", [])
    
    for slide in slides:
        reest = slide.get("reestructuracion")
        if reest and reest.get("diapositivas_generadas"):
            hay_recomendaciones = True
            num_slide = slide.get("slide_number", "?")
            sugerencias = reest["diapositivas_generadas"]
            num_sugerencias = len(sugerencias)
            
            # Encabezado de la diapositiva original
            ctk.CTkLabel(
                scroll, text=f"📌 Diapositiva {num_slide} original:", 
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color="#1E293B", anchor="w"
            ).pack(fill="x", padx=10, pady=(20, 5))
            
            # ---> CONTEXTO AGREGADO: Texto de sugerencia igual al results_panel <---
            texto_rec = (f"Se recomienda dividir la diapositiva en {num_sugerencias} diapositivas:" 
                         if num_sugerencias > 1 else 
                         "Se recomienda redactar el contenido de la siguiente manera:")

            ctk.CTkLabel(
                scroll, text=texto_rec, 
                font=("Inter", 13, "bold"), text_color=COLOR_GUINDA,
                wraplength=450, justify="left", anchor="w"
            ).pack(fill="x", padx=15, pady=(5, 10))
            # -----------------------------------------------------------------------
            
            # Renderizar las diapositivas generadas (Opciones de mejora)
            for i, sug in enumerate(sugerencias, 1):
                f = ctk.CTkFrame(scroll, fg_color="white", border_width=1, border_color="#CBD5E1", corner_radius=8)
                f.pack(fill="x", padx=10, pady=6)
                
                titulo = sug.get('titulo_sugerido', 'Sin título')
                contenido = sug.get('contenido_optimizado', '')
                
                # Ajuste de títulos internos para igualar a results_panel
                lbl_tit = f"Diapositiva {i}: {titulo}" if num_sugerencias > 1 else f"Contenido Optimizado: {titulo}"
                
                ctk.CTkLabel(f, text=lbl_tit, font=("Inter", 12, "bold"), text_color=COLOR_GUINDA, anchor="w").pack(fill="x", padx=15, pady=(10, 5))
                ctk.CTkLabel(f, text=contenido, font=("Inter", 11), wraplength=420, justify="left", text_color="#475569").pack(fill="x", padx=15, pady=(0, 15))

    if not hay_recomendaciones:
        ctk.CTkLabel(
            scroll, text="No hay sugerencias de reestructuración para esta versión.\nLa presentación tiene un nivel óptimo.",
            font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"), text_color="#64748B", justify="center"
        ).pack(pady=60)

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