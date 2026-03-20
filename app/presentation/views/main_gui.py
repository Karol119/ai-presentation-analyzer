# app/presentation/views/main_gui.py
import customtkinter as ctk

# 1. IMPORTACIÓN EXCLUSIVA DE CONTROLADORES (Capa de Negocio)
# La interfaz no conoce la base de datos ni el sistema de archivos directamente
from app.core.controller.presentation_controller import (
    orquestar_proceso_completo, 
    orquestar_eliminacion_presentacion
)
from app.core.controller.subject_controller import (
    obtener_catalogo_materias_activas,
    obtener_materias_para_agregar,
    activar_materia,
    desactivar_materia,
    obtener_id_materia,
    obtener_archivos_materia
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
    # Obtenemos el ID de la materia a través del controlador
    id_materia = obtener_id_materia(name)
    
    # Sincronización de aislamiento: Recupera (nombre, ruta_pptx, ruta_thumb) mediante el controlador
    if id_materia:
        estado["subject_files"][name] = obtener_archivos_materia(id_materia)
    
    refresh_sidebar_styles()
    show_panel(name)
    _actualizar_boton_analizar()
    refresh_right_panel(name)

def _eliminar_materia(name: str):
    """Desactiva la materia en la BD y limpia la interfaz delegando al controlador."""
    if len(estado["subjects"]) == 1: return
    
    # El controlador se encarga de actualizar el bit 'activa' en la BD
    if desactivar_materia(name):
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
    """Muestra el modal IPN para activar nuevas materias consumiendo el controlador."""
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

    # Obtenemos materias inactivas desde el controlador
    available = obtener_materias_para_agregar()

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
            # Activamos la materia a través del controlador
            if activar_materia(name):
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
    """Ejecuta el análisis y muestra resultados delegando al PresentationController."""
    subject = estado["active"]
    id_materia_real = obtener_id_materia(subject)
    
    if not id_materia_real: return

    resultados = []
    # Iteramos sobre la estructura de 3 valores: (nombre, ruta_pptx, ruta_thumb)
    for datos in estado["subject_files"][subject]:
        nombre, ruta_pptx = datos[0], datos[1]
        if ruta_pptx:
            exito, mensaje = orquestar_proceso_completo(ruta_pptx, id_materia_real)
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
# MODALES DE ESTADO (Éxito / Eliminación)
# =========================================================

def mostrar_modal_exito(mensaje):
    """Muestra un modal de confirmación con estilo IPN."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Éxito")
    win.geometry("400x240")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    ctk.CTkLabel(
        win, text="✔️", 
        font=ctk.CTkFont(size=50), 
        text_color=COLOR_ORO
    ).pack(pady=(20, 10))

    ctk.CTkLabel(
        win, text=mensaje, 
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color=COLOR_GUINDA,
        wraplength=350
    ).pack(pady=10)

    ctk.CTkButton(
        win, text="Cerrar", 
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        width=120, height=32,
        corner_radius=8
    ).pack(pady=(10, 20))

def confirmar_eliminacion(nombre, subject, callback_confirmar):
    """Muestra el modal institucional de advertencia para borrado en cascada."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Confirmar eliminación")
    win.geometry("450x280")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Icono de papelera en color de advertencia
    ctk.CTkLabel(win, text="🗑️", font=ctk.CTkFont(size=45), text_color="#EF4444").pack(pady=(20, 10))
    
    ctk.CTkLabel(
        win, text="¿Seguro que deseas borrar esta presentación?", 
        font=ctk.CTkFont(size=15, weight="bold"), 
        text_color=COLOR_GUINDA
    ).pack()

    ctk.CTkLabel(
        win, text=f"{nombre}", 
        font=ctk.CTkFont(size=12, slant="italic"), 
        text_color="#64748B"
    ).pack(pady=(2, 8))

    ctk.CTkLabel(
        win, text="Se borrarán todos los datos de esta presentación,\nincluyendo versiones anteriores y análisis previos.", 
        font=ctk.CTkFont(size=11), 
        text_color="#94A3B8", 
        justify="center"
    ).pack(padx=20, pady=5)

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=20)

    def proceder():
        callback_confirmar()
        win.destroy()

    ctk.CTkButton(
        btn_row, text="Aceptar", command=proceder, 
        fg_color="#EF4444", hover_color="#DC2626", 
        text_color="white", width=120, height=34, corner_radius=8
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        btn_row, text="Cancelar", command=win.destroy, 
        fg_color="transparent", text_color="#64748B", 
        border_width=1, border_color="#CBD5E1", 
        width=120, height=34, corner_radius=8
    ).pack(side="right", padx=10)

# =========================================================
# PUNTO DE ARRANQUE (INICIALIZACIÓN)
# =========================================================

def iniciar_aplicacion():
    ui["root"] = ctk.CTk()
    ui["root"].title("AI Presentation Analyzer - IPN ESCOM")
    ui["root"].geometry("1240x720")
    ui["root"].minsize(1000, 600)
    ui["root"].configure(fg_color=COLOR_GRIS_FONDO)

    # ✅ CARGA INICIAL DESDE CONTROLADORES
    all_active_subjects = obtener_catalogo_materias_activas()
    estado["subjects"] = all_active_subjects
    
    # Sincronización de archivos por materia al iniciar usando controladores
    estado["subject_files"] = {}
    for s in estado["subjects"]:
        id_materia = obtener_id_materia(s)
        estado["subject_files"][s] = obtener_archivos_materia(id_materia)

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