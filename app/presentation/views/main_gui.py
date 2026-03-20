# app/presentation/views/main_gui.py
import customtkinter as ctk

# 1. Importaciones de Lógica y Datos
from app.core.controller.presentation_controller import orquestar_proceso_completo
from app.data.queries import (
    obtener_presentaciones_por_materia,
    obtener_todas_las_materias, 
    obtener_materias_disponibles,
    actualizar_estado_materia,
    obtener_id_materia_por_nombre
)

# 2. Importación del Estado Central
from app.presentation.views.ui_state import estado, ui

# 3. Importación de los Componentes (Widgets)
from app.presentation.widgets.topbar import build_topbar
from app.presentation.widgets.sidebar import build_left_sidebar, refresh_sidebar_styles
from app.presentation.widgets.content_panel import build_content_area, show_panel
from app.presentation.widgets.right_panel import build_right_panel, refresh_right_panel

# Configuración de Colores Institucionales IPN
COLOR_GUINDA = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO = "#BC955C"
COLOR_ORO_HOVER = "#9E7C4A"
COLOR_GRIS_FONDO = "#F1F5F9"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# =========================================================
# LÓGICA DE EVENTOS (Callbacks)
# =========================================================

def _toggle_right_panel():
    """Alterna la visibilidad del panel derecho de contenido."""
    if estado["right_panel_visible"]:
        ui["right_panel"].pack_forget()
        ui["toggle_btn"].configure(
            fg_color="transparent", 
            text_color="#64748B", 
            border_color="#CBD5E1", 
            text="☰   Contenido"
        )
    else:
        ui["right_panel"].pack(side="right", fill="y")
        ui["toggle_btn"].configure(
            fg_color=COLOR_ORO, 
            text_color="white", 
            border_color=COLOR_ORO, 
            text="✕   Ocultar"
        )
    estado["right_panel_visible"] = not estado["right_panel_visible"]

def _actualizar_boton_analizar():
    """Habilita o deshabilita el botón de análisis según si hay archivos cargados."""
    has_files = bool(estado["subject_files"].get(estado["active"]))
    ui["analyze_btn"].configure(
        state="normal" if has_files else "disabled",
        fg_color=COLOR_GUINDA if has_files else "#94A3B8",
        hover_color=COLOR_GUINDA_HOVER if has_files else "#64748B",
    )

def _seleccionar_materia(name: str):
    """Sincroniza el estado con la BD y cambia la vista a la materia seleccionada."""
    estado["active"] = name
    id_materia = obtener_id_materia_por_nombre(name)
    
    # Sincronización de aislamiento: Solo cargar archivos de ESTA materia
    if id_materia:
        estado["subject_files"][name] = obtener_presentaciones_por_materia(id_materia)
    
    refresh_sidebar_styles()
    show_panel(name)
    _actualizar_boton_analizar()
    refresh_right_panel(name)

def _eliminar_materia(name: str):
    """Desactiva la materia en la BD y limpia la interfaz."""
    if len(estado["subjects"]) == 1: return
    
    # Persistencia: Marcar activa=0 en la base de datos
    actualizar_estado_materia(name, False)
    
    estado["subjects"].remove(name)
    if name in estado["subject_files"]:
        del estado["subject_files"][name]
        
    ui["sidebar_btns"].pop(name).destroy()
    p = ui["panels"].pop(name, None)
    if p: p.destroy()
    
    if estado["active"] == name:
        estado["active"] = estado["subjects"][0]
        refresh_sidebar_styles()
        
    show_panel(estado["active"])
    _actualizar_boton_analizar()

def _abrir_modal_agregar_materia():
    """Muestra el modal IPN para activar nuevas materias de la BD."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Agregar materia - IPN")
    win.geometry("420x340")
    win.resizable(False, False)
    win.grab_set()
    win.configure(fg_color="white")

    ctk.CTkLabel(
        win, text="Agregar materia", 
        font=ctk.CTkFont(size=18, weight="bold"), 
        text_color=COLOR_GUINDA
    ).pack(pady=(28, 4), padx=28, anchor="w")
    
    ctk.CTkLabel(
        win, text="Materias disponibles en el catálogo ESCOM:", 
        font=ctk.CTkFont(size=11), 
        text_color="#64748B"
    ).pack(pady=(0, 20), padx=28, anchor="w")

    available = obtener_materias_disponibles()

    if not available:
        ctk.CTkLabel(win, text="No hay más materias disponibles.", font=ctk.CTkFont(size=12), text_color=COLOR_GUINDA).pack(pady=20)
        ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color="#64748B").pack()
        return

    selected_var = ctk.StringVar(value=available[0])
    
    ctk.CTkOptionMenu(
        win, values=available, variable=selected_var, 
        fg_color="white", button_color=COLOR_GUINDA, 
        button_hover_color=COLOR_GUINDA_HOVER, text_color="#0F172A",
        dropdown_hover_color="#F4E7EA", corner_radius=8, width=360, height=42
    ).pack(padx=28, pady=(6, 30))

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(fill="x", padx=28)

    def confirm():
        name = selected_var.get()
        if name:
            actualizar_estado_materia(name, True)
            estado["subjects"].append(name)
            estado["subject_files"][name] = []
            
            from app.presentation.widgets.sidebar import create_sidebar_item
            from app.presentation.widgets.content_panel import create_panel
            
            create_sidebar_item(name, _seleccionar_materia, _eliminar_materia)
            create_panel(name, _actualizar_boton_analizar)
            _seleccionar_materia(name)
        win.destroy()

    ctk.CTkButton(
        btn_row, text="Cancelar", command=win.destroy, 
        fg_color="transparent", text_color="#64748B", 
        border_width=1, border_color="#CBD5E1", width=160, height=36
    ).pack(side="left")

    ctk.CTkButton(
        btn_row, text="Agregar materia", command=confirm, 
        fg_color=COLOR_GUINDA, hover_color=COLOR_GUINDA_HOVER, 
        text_color="white", width=160, height=36
    ).pack(side="right")

def _analyze():
    """Ejecuta el análisis y muestra resultados en un modal institucional."""
    subject = estado["active"]
    id_materia_real = obtener_id_materia_por_nombre(subject)
    
    if not id_materia_real: return

    resultados = []
    for nombre, ruta_completa in estado["subject_files"][subject]:
        if ruta_completa:
            exito, mensaje = orquestar_proceso_completo(ruta_completa, id_materia_real)
            icono = "✅" if exito else "❌"
            resultados.append(f"{icono} {nombre}:\n   {mensaje}")

    mensaje_final = "\n\n".join(resultados) if resultados else "Cargue una presentación para analizar."

    win = ctk.CTkToplevel(ui["root"])
    win.title("Resultados del Análisis - ESCOM")
    win.geometry("500x400")
    win.grab_set()
    win.configure(fg_color="white")

    ctk.CTkLabel(
        win, text=f"Análisis: {subject}", 
        font=ctk.CTkFont(size=16, weight="bold"), 
        text_color=COLOR_GUINDA
    ).pack(pady=(28, 12))

    scroll = ctk.CTkScrollableFrame(win, fg_color="#F8FAFC", height=180, border_width=1, border_color="#E2E8F0")
    scroll.pack(fill="both", expand=True, padx=30)
    
    ctk.CTkLabel(
        scroll, text=mensaje_final, font=ctk.CTkFont(size=12), 
        text_color="#334155", justify="left", wraplength=380
    ).pack(anchor="w", padx=10, pady=10)

    ctk.CTkButton(
        win, text="Finalizar", command=win.destroy, 
        fg_color=COLOR_GUINDA, hover_color=COLOR_GUINDA_HOVER, 
        corner_radius=8, width=120
    ).pack(pady=24)

# =========================================================
# PUNTO DE ARRANQUE (INICIALIZACIÓN)
# =========================================================

def iniciar_aplicacion():
    ui["root"] = ctk.CTk()
    ui["root"].title("AI Presentation Analyzer - IPN ESCOM")
    ui["root"].geometry("1240x720")
    ui["root"].minsize(1000, 600)
    ui["root"].configure(fg_color=COLOR_GRIS_FONDO)

    # 1. Carga de datos persistentes
    all_active_subjects = obtener_todas_las_materias()
    estado["subjects"] = all_active_subjects
    
    # Sincronización de archivos por materia al iniciar
    estado["subject_files"] = {}
    for s in estado["subjects"]:
        id_materia = obtener_id_materia_por_nombre(s)
        estado["subject_files"][s] = obtener_presentaciones_por_materia(id_materia)

    estado["active"] = estado["subjects"][0] if estado["subjects"] else ""

    # 2. Construir Interfaz Base
    build_topbar(_toggle_right_panel, _analyze)

    ui["body"] = ctk.CTkFrame(ui["root"], fg_color="transparent", corner_radius=0)
    ui["body"].pack(fill="both", expand=True)

    # 3. Construir Widgets inyectando dependencias
    build_left_sidebar(_abrir_modal_agregar_materia, _seleccionar_materia, _eliminar_materia)
    build_content_area(_actualizar_boton_analizar)
    build_right_panel()
    
    # 4. Seleccionar materia inicial
    if estado["active"]:
        _seleccionar_materia(estado["active"])

    ui["root"].mainloop()