# app/presentation/views/main_gui.py
import customtkinter as ctk

# 1. Importaciones de Lógica y Datos
from app.core.controller.presentation_controller import orquestar_proceso_completo
from app.data.queries import (
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

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# =========================================================
# LÓGICA DE EVENTOS (Callbacks)
# =========================================================

def _toggle_right_panel():
    """Alterna la visibilidad del panel derecho de contenido."""
    if estado["right_panel_visible"]:
        ui["right_panel"].pack_forget()
        ui["toggle_btn"].configure(fg_color="#F1F5F9", text_color="#64748B", border_color="#CBD5E1", text="☰  Contenido")
    else:
        ui["right_panel"].pack(side="right", fill="y")
        ui["toggle_btn"].configure(fg_color="#EFF6FF", text_color="#2563EB", border_color="#BFDBFE", text="✕  Ocultar")
    estado["right_panel_visible"] = not estado["right_panel_visible"]

def _actualizar_boton_analizar():
    """Habilita o deshabilita el botón de análisis según si hay archivos cargados."""
    has_files = bool(estado["subject_files"].get(estado["active"]))
    ui["analyze_btn"].configure(
        state="normal" if has_files else "disabled",
        fg_color="#2563EB" if has_files else "#94A3B8",
        hover_color="#1D4ED8" if has_files else "#64748B",
    )

def _seleccionar_materia(name: str):
    """Cambia la materia activa y refresca toda la interfaz."""
    estado["active"] = name
    refresh_sidebar_styles()
    show_panel(name)
    _actualizar_boton_analizar()
    refresh_right_panel(name)

def _eliminar_materia(name: str):
    """Desactiva la materia en la BD y la elimina de la vista actual."""
    if len(estado["subjects"]) == 1: return
    
    # 1. Persistencia: Cambiar bit 'activa' a 0 en la base de datos
    actualizar_estado_materia(name, False)
    
    # 2. Lógica de eliminación del estado visual
    estado["subjects"].remove(name)
    if name in estado["subject_files"]:
        del estado["subject_files"][name]
        
    ui["sidebar_btns"].pop(name).destroy()
    p = ui["panels"].pop(name, None)
    if p: p.destroy()
    
    # Si eliminamos la materia que estaba abierta, saltamos a la primera disponible
    if estado["active"] == name:
        estado["active"] = estado["subjects"][0]
        refresh_sidebar_styles()
        
    show_panel(estado["active"])
    _actualizar_boton_analizar()

def _abrir_modal_agregar_materia():
    """Muestra un modal con las materias de la BD que tienen activa=0."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Agregar materia")
    win.geometry("420x300")
    win.resizable(False, False)
    win.grab_set()
    win.configure(fg_color="white")

    ctk.CTkLabel(win, text="Agregar materia", font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A").pack(pady=(28, 4), padx=28, anchor="w")
    ctk.CTkLabel(win, text="Materias disponibles en la BD:", font=ctk.CTkFont(size=11), text_color="#64748B").pack(pady=(0, 14), padx=28, anchor="w")

    # FILTRO: Solo materias que están en la BD con activa=0
    available = obtener_materias_disponibles()

    if not available:
        ctk.CTkLabel(win, text="No hay más materias disponibles.", font=ctk.CTkFont(size=12), text_color="#EF4444").pack(pady=20)
        ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color="#64748B").pack()
        return

    selected_var = ctk.StringVar(value=available[0])
    ctk.CTkLabel(win, text="Seleccione una materia:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(anchor="w", padx=28)
    ctk.CTkOptionMenu(win, values=available, variable=selected_var, font=ctk.CTkFont(size=13), fg_color="white", button_color="#2563EB", button_hover_color="#1D4ED8", dropdown_fg_color="white", dropdown_hover_color="#EFF6FF", dropdown_text_color="#0F172A", text_color="#0F172A", corner_radius=8, width=360, height=40).pack(padx=28, pady=(6, 20))

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(fill="x", padx=28)

    def confirm():
        name = selected_var.get()
        if name:
            # 1. Persistencia: Cambiar bit 'activa' a 1 en la base de datos
            actualizar_estado_materia(name, True)
            
            # 2. Actualizar estado lógico
            estado["subjects"].append(name)
            estado["subject_files"][name] = []
            
            # 3. Inyectar nuevos widgets en la interfaz
            from app.presentation.widgets.sidebar import create_sidebar_item
            from app.presentation.widgets.content_panel import create_panel
            
            create_sidebar_item(name, _seleccionar_materia, _eliminar_materia)
            create_panel(name, _actualizar_boton_analizar)
            _seleccionar_materia(name)
            
        win.destroy()

    ctk.CTkButton(btn_row, text="Cancelar", command=win.destroy, fg_color="transparent", hover_color="#F1F5F9", text_color="#64748B", border_width=1, border_color="#CBD5E1", corner_radius=8, height=36, width=160).pack(side="left")
    ctk.CTkButton(btn_row, text="Agregar", command=confirm, fg_color="#2563EB", hover_color="#1D4ED8", text_color="white", corner_radius=8, height=36, width=160).pack(side="right")

def _analyze():
    """Ejecuta el proceso de análisis para los archivos de la materia activa."""
    subject = estado["active"]
    id_materia_real = obtener_id_materia_por_nombre(subject)
    
    if not id_materia_real:
        print(f"Error: No se encontró el ID de '{subject}' en la base de datos.")
        return

    resultados = []
    for nombre, ruta_completa in estado["subject_files"][subject]:
        if ruta_completa:
            exito, mensaje = orquestar_proceso_completo(ruta_completa, id_materia_real)
            icono = "✅" if exito else "❌"
            resultados.append(f"{icono} {nombre}:\n   {mensaje}")

    mensaje_final = "\n\n".join(resultados) if resultados else "No hay archivos válidos para procesar."

    # Modal de resultados
    win = ctk.CTkToplevel(ui["root"])
    win.title("Resultado del Análisis")
    win.geometry("500x350")
    win.grab_set()

    ctk.CTkLabel(win, text=f"Resultados de: {subject}", font=ctk.CTkFont(size=15, weight="bold"), text_color="#0F172A").pack(pady=(28, 8))
    scroll = ctk.CTkScrollableFrame(win, fg_color="transparent", height=150)
    scroll.pack(fill="both", expand=True, padx=24)
    ctk.CTkLabel(scroll, text=mensaje_final, font=ctk.CTkFont(size=12), text_color="#334155", justify="left", wraplength=400).pack(anchor="w")
    ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color="#2563EB", hover_color="#1D4ED8", corner_radius=8).pack(pady=24)

# =========================================================
# PUNTO DE ARRANQUE (INICIALIZACIÓN)
# =========================================================

def iniciar_aplicacion():
    ui["root"] = ctk.CTk()
    ui["root"].title("Prototipo 01. Cargar una presentación")
    ui["root"].geometry("1200x700")
    ui["root"].minsize(900, 560)
    ui["root"].resizable(True, True)
    ui["root"].configure(fg_color="#F1F5F9")

    # Carga inicial desde la BD (Solo materias con activa=1)
    all_active_subjects = obtener_todas_las_materias()
    estado["subjects"] = all_active_subjects
    estado["subject_files"] = {s: [] for s in estado["subjects"]}
    estado["active"] = estado["subjects"][0] if estado["subjects"] else ""

    # 1. Construir Topbar
    build_topbar(_toggle_right_panel, _analyze)

    ui["body"] = ctk.CTkFrame(ui["root"], fg_color="transparent", corner_radius=0)
    ui["body"].pack(fill="both", expand=True)

    # 2. Construir Sidebar, Content Area y Right Panel inyectando las dependencias
    build_left_sidebar(_abrir_modal_agregar_materia, _seleccionar_materia, _eliminar_materia)
    build_content_area(_actualizar_boton_analizar)
    build_right_panel()
    
    # Seleccionar la primera materia por defecto si existen
    if estado["active"]:
        _seleccionar_materia(estado["active"])

    ui["root"].mainloop()