# app/presentation/views/history_gui.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
import os
from app.presentation.views.ui_state import ui, estado
from app.presentation.views import navigator  
from app.data.queries import obtener_historial_presentacion, obtener_id_materia
from app.presentation.widgets.history.history_recommendations import mostrar_modal_recomendaciones_json
from app.presentation.widgets.history.history_evaluation import mostrar_modal_evaluacion_json
from app.core.controller.presentation_controller import orquestar_exportacion_historial
from app.presentation.utils.thread_manager import ejecutar_tarea_asincrona

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"
COLOR_ORO_HOVER    = "#9E7C4A"

def mostrar_vista_historial(subject: str, nombre_presentacion: str):
    """
    Construye y empaqueta la vista de historial de versiones.
    """
    ui["history_body"] = ctk.CTkFrame(
        ui["root"],
        fg_color="#EEF2F7",
        corner_radius=0,
    )
    ui["history_body"].pack(fill="both", expand=True)

    # --- Cabecera Interna ---
    header_frame = ctk.CTkFrame(ui["history_body"], fg_color="white", height=80, corner_radius=0)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    btn_volver = ctk.CTkButton(
        header_frame, text="← Volver a inicio",
        width=150, height=40, corner_radius=20,
        fg_color=COLOR_GUINDA, hover_color="#4D1324", text_color="white",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        command=navigator.ir_a_principal
    )
    btn_volver.pack(side="left", padx=(40, 20))

    ctk.CTkLabel(
        header_frame, 
        text=f"Historial: {nombre_presentacion}",
        font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        text_color=COLOR_GUINDA
    ).pack(side="left")

    # --- Contenedor de Tabla ---
    main_container = ctk.CTkFrame(ui["history_body"], fg_color="white", corner_radius=16)
    main_container.pack(fill="both", expand=True, padx=40, pady=30)

    # Encabezados
    headers_frame = ctk.CTkFrame(main_container, fg_color="transparent", height=45)
    headers_frame.pack(fill="x", padx=30, pady=(25, 10))
    
    # 7 Columnas ajustadas al 100% (1.0)
    cols = [
        ("VER", 0.08),
        ("FECHA", 0.15),
        ("LÁMINAS", 0.12),
        ("ANÁLISIS", 0.10),
        ("EVALUACIÓN", 0.16),
        ("RECOMENDACIONES", 0.22),
        ("EXPORTAR", 0.17)
    ]
    
    current_x = 0
    for text, width in cols:
        lbl = ctk.CTkLabel(
            headers_frame, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8"
        )
        lbl.place(relx=current_x + (width/2), rely=0.5, anchor="center")
        current_x += width

    ctk.CTkFrame(main_container, height=1, fg_color="#F1F5F9").pack(fill="x", padx=30)

    # --- Lista de Versiones (Scroll) ---
    scroll_area = ctk.CTkScrollableFrame(
        main_container, fg_color="transparent", scrollbar_button_color="#E2E8F0"
    )
    scroll_area.pack(fill="both", expand=True, padx=20, pady=10)

    id_materia = obtener_id_materia(subject)
    versiones = obtener_historial_presentacion(nombre_presentacion, id_materia)

    if not versiones:
        ctk.CTkLabel(
            scroll_area, text="No se encontraron versiones para esta presentación.",
            font=ctk.CTkFont(size=13), text_color="#64748B"
        ).pack(pady=60)
        return

    for v in versiones:
        _crear_fila_version(scroll_area, v, cols, subject, nombre_presentacion)

def _crear_fila_version(parent, data, cols_config, subject, nombre_presentacion):
    # Desempaquetado actualizado incluyendo id_version
    id_version, v_num, fecha, total_slides, analizada, ruta_pdf = data
    
    fila = ctk.CTkFrame(parent, fg_color="transparent", height=60)
    fila.pack(fill="x", pady=2)
    
    ctk.CTkFrame(parent, height=1, fg_color="#F8FAFC").pack(fill="x", padx=10)

    current_x = 0
    
    # 1. VER
    ctk.CTkLabel(fila, text=f"v{v_num}", font=("Segoe UI", 12, "bold"), text_color="#1E293B").place(relx=current_x + (cols_config[0][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[0][1]

    # 2. FECHA
    ctk.CTkLabel(fila, text=fecha, font=("Segoe UI", 12), text_color="#475569").place(relx=current_x + (cols_config[1][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[1][1]

    # 3. LÁMINAS
    ctk.CTkLabel(fila, text=f"{total_slides}", font=("Segoe UI", 12), text_color="#475569").place(relx=current_x + (cols_config[2][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[2][1]

    # 4. ANÁLISIS
    status_icon = "✅" if analizada else "❌"
    status_color = "#10B981" if analizada else "#94A3B8"
    ctk.CTkLabel(fila, text=status_icon, font=("Segoe UI", 14), text_color=status_color).place(relx=current_x + (cols_config[3][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[3][1]

    # 5. EVALUACIÓN
    if analizada and ruta_pdf:
        btn_eval = ctk.CTkButton(
            fila, text="Ver Evaluación",
            width=120, height=32, corner_radius=8,
            fg_color=COLOR_GUINDA, hover_color="#4D1324",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda p=ruta_pdf, v=v_num: mostrar_modal_evaluacion_json(p, v)
        )
        btn_eval.place(relx=current_x + (cols_config[4][1]/2), rely=0.5, anchor="center")
    else:
        ctk.CTkLabel(fila, text="---", font=("Segoe UI", 11, "italic"), text_color="#94A3B8").place(relx=current_x + (cols_config[4][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[4][1]

    # 6. RECOMENDACIONES
    if analizada and ruta_pdf:
        btn_rec = ctk.CTkButton(
            fila, text="Sugerencias IA",
            width=130, height=32, corner_radius=8,
            fg_color=COLOR_GUINDA, hover_color="#4D1324",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda p=ruta_pdf, v=v_num: mostrar_modal_recomendaciones_json(p, v)
        )
        btn_rec.place(relx=current_x + (cols_config[5][1]/2), rely=0.5, anchor="center")
    else:
        ctk.CTkLabel(fila, text="Sin análisis", font=("Segoe UI", 11, "italic"), text_color="#94A3B8").place(relx=current_x + (cols_config[5][1]/2), rely=0.5, anchor="center")
    current_x += cols_config[5][1]

    # 7. EXPORTAR (NUEVA COLUMNA)
    if analizada and ruta_pdf:
        btn_exp = ctk.CTkButton(
            fila, text="📥 Exportar",
            width=110, height=32, corner_radius=8,
            fg_color="#10B981", hover_color="#059669", text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: _exportar_version_gui(id_version, nombre_presentacion, subject, v_num, ruta_pdf)
        )
        btn_exp.place(relx=current_x + (cols_config[6][1]/2), rely=0.5, anchor="center")
    else:
        ctk.CTkLabel(fila, text="---", font=("Segoe UI", 11, "italic"), text_color="#94A3B8").place(relx=current_x + (cols_config[6][1]/2), rely=0.5, anchor="center")


def _exportar_version_gui(id_version, nombre_presentacion, subject, v_num, ruta_pdf):
    """Lanza la tarea en segundo plano para exportar el archivo a Documentos."""
    if estado.get("bloqueo_ui"): return
    estado["bloqueo_ui"] = True

    id_materia = obtener_id_materia(subject)

    def tarea():
        return orquestar_exportacion_historial(id_version, nombre_presentacion, id_materia, v_num, ruta_pdf)

    def al_terminar(resultado):
        estado["bloqueo_ui"] = False
        exito, mensaje = resultado
        if exito:
            messagebox.showinfo("Exportación Lista", mensaje)
        else:
            messagebox.showwarning("Aviso", mensaje)

    ejecutar_tarea_asincrona(target_task=tarea, on_finished_callback=al_terminar)

def ocultar_vista_historial():
    """Limpia los recursos de la vista de historial."""
    if "history_body" in ui and ui["history_body"].winfo_exists():
        ui["history_body"].destroy()
        del ui["history_body"]