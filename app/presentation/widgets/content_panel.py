# app/presentation/widgets/content_panel.py
import customtkinter as ctk
from tkinter import filedialog
import os
from PIL import Image
from typing import Callable

# Estado y UI
from app.presentation.views.ui_state import estado, ui

# Controladores (Capa de Negocio)
from app.core.controller.presentation_controller import (
    orquestar_proceso_completo,
    orquestar_eliminacion_presentacion,
    orquestar_analisis_ia,
    orquestar_actualizacion_presentacion  # <-- Esta es la nueva
)

from app.core.controller.subject_controller import (
    obtener_id_materia, 
    obtener_archivos_materia
)

# Utilidades y Widgets de Presentación (Capa de Presentación)
from app.presentation.widgets.dialogs import (
    mostrar_modal_cargando, 
    advertir_presentacion_existente,
    mostrar_modal_advertencia
)
from app.presentation.utils.thread_manager import ejecutar_tarea_asincrona
from app.presentation.views import navigator

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"

CARD_W = 175
CARD_H = 270

def build_content_area(comando_actualizar_boton):
    """Construye el contenedor principal y limpia registros previos."""
    ui["content_area"] = ctk.CTkFrame(
        ui["body"],
        fg_color="white",
        corner_radius=14,
        border_width=1,
        border_color="#E8ECF2",
    )
    ui["content_area"].pack(
        side="left", fill="both", expand=True, padx=(0, 10), pady=12
    )
    
    ui["panels"] = {} 
    
    for s in estado["subjects"]:
        create_panel(s, comando_actualizar_boton)

def create_panel(name: str, comando_actualizar_boton):
    """Crea el panel de una materia pero NO lo posiciona aún."""
    panel = ctk.CTkFrame(ui["content_area"], fg_color="transparent", corner_radius=0)

    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=26, pady=(22, 0))
    ctk.CTkLabel(
        header, text=name,
        font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(side="left")

    sub_header = ctk.CTkFrame(panel, fg_color="transparent")
    sub_header.pack(fill="x", padx=26, pady=(6, 0))
    ctk.CTkLabel(
        sub_header, text="📄   Mis Presentaciones",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#475569",
    ).pack(side="left")

    ctk.CTkFrame(panel, height=1, fg_color="#F1F5F9").pack(fill="x", padx=26, pady=(10, 0))

    cards_scroll = ctk.CTkScrollableFrame(
        panel, fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    cards_scroll.pack(fill="both", expand=True, padx=26, pady=(16, 24))

    panel._cards_scroll = cards_scroll
    ui["panels"][name]   = panel
    rebuild_cards(name, comando_actualizar_boton)

def show_panel(name: str):
    for n, p in ui["panels"].items():
        if n == name:
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            p.place_forget()

def show_empty_state():
    """Muestra una vista de bienvenida cuando no hay materias activas."""
    # Ocultamos todos los paneles actuales
    for p in ui["panels"].values():
        p.place_forget()
        
    # Creamos o recuperamos el panel de estado vacío
    if "empty_view" not in ui:
        view = ctk.CTkFrame(ui["content_area"], fg_color="white", corner_radius=14)
        ui["empty_view"] = view
        
        container = ctk.CTkFrame(view, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icono o Ilustración
        ctk.CTkLabel(
            container, text="📚", font=ctk.CTkFont(size=60)
        ).pack(pady=10)
        
        ctk.CTkLabel(
            container, 
            text="¡Bienvenido al Analizador!",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_GUINDA
        ).pack()
        
        ctk.CTkLabel(
            container, 
            text="Aún no tienes materias activas.\nPresiona '+ Agregar materia' en el panel izquierdo para comenzar.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#64748B",
            justify="center"
        ).pack(pady=10)

    ui["empty_view"].place(relx=0, rely=0, relwidth=1, relheight=1)

def rebuild_cards(subject: str, comando_actualizar_boton):
    """Reconstruye la cuadrícula de tarjetas de presentaciones en formato rectangular."""
    panel = ui["panels"].get(subject)
    if not panel: return

    scroll = panel._cards_scroll
    # Limpieza total de los widgets previos para redibujar
    for w in scroll.winfo_children():
        w.destroy()

    # Contenedor principal que permite la expansión horizontal
    wrap = ctk.CTkFrame(scroll, fg_color="transparent")
    wrap.pack(fill="x", expand=True, anchor="nw")

    # Configuración de flujo de la cuadrícula
    MAX_COLUMNS = 4
    current_row = 0
    current_col = 0

    # 1. Generar tarjetas de archivos existentes
    for datos in estado["subject_files"].get(subject, []):
        nombre, ruta_thumb, ya_analizada, ruta_pdf = datos[0], datos[2], bool(datos[3]), datos[4]
        card_widget = _make_file_card(wrap, subject, nombre, ruta_thumb, ya_analizada, ruta_pdf, comando_actualizar_boton)
        # Lo posicionamos usando la cuadrícula del padre
        card_widget.grid(row=current_row, column=current_col, padx=(0, 18), pady=8, sticky="nw")
        
        current_col += 1
        if current_col >= MAX_COLUMNS:
            current_col = 0
            current_row += 1

    # 2. Generar tarjeta de "Subir presentación" al final de la lista
    upload_card = _make_upload_card(wrap, subject, comando_actualizar_boton)
    upload_card.grid(row=current_row, column=current_col, padx=(0, 18), pady=8, sticky="nw")


def _make_file_card(parent, subject: str, name: str, ruta_thumb, ya_analizada: bool, ruta_pdf: str, comando_actualizar_boton):
    """Crea y retorna el widget de tarjeta de archivo (sin posicionarlo)."""
    outer = ctk.CTkFrame(parent, fg_color="transparent", width=CARD_W, height=CARD_H)
    outer.pack_propagate(False)

    card = ctk.CTkFrame(
        outer, width=CARD_W - 6, height=CARD_H - 6,
        fg_color="white", border_width=1, border_color="#E2E8F0", corner_radius=16,
    )
    card.place(x=3, y=3)
    card.pack_propagate(False)

    # Cara Preview
    face_prev = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
    face_prev.place(relx=0, rely=0, relwidth=1, relheight=1)

    try:
        if ruta_thumb and os.path.exists(ruta_thumb):
            img = Image.open(ruta_thumb)
            img_ctk = ctk.CTkImage(light_image=img, size=(130, 84))
            ctk.CTkLabel(face_prev, image=img_ctk, text="").pack(pady=(36, 0))
        else: raise FileNotFoundError
    except:
        icon_bg = ctk.CTkFrame(face_prev, fg_color="#FDF2F4", corner_radius=12, width=90, height=68)
        icon_bg.pack(pady=(36, 0))
        ctk.CTkLabel(icon_bg, text="📊", font=ctk.CTkFont(size=36), text_color=COLOR_GUINDA).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(face_prev, text=name, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                 text_color="#1E293B", wraplength=148, justify="center").pack(padx=8, pady=(8, 0), fill="x", expand=True)

    # Cara Menú
    face_menu = ctk.CTkFrame(card, fg_color="white", corner_radius=16)

    def toggle_menu(abrir=True):
        if abrir:
            face_prev.place_forget()
            face_menu.place(relx=0, rely=0, relwidth=1, relheight=1)
            card.configure(border_color=COLOR_ORO)
        else:
            face_menu.place_forget()
            face_prev.place(relx=0, rely=0, relwidth=1, relheight=1)
            card.configure(border_color="#E2E8F0")

    ctk.CTkButton(face_prev, text="☰   Ver opciones", height=30, fg_color="#F8FAFC", 
                  text_color="#475569", font=ctk.CTkFont(size=11, weight="bold"),
                  command=lambda: toggle_menu(True)).pack(fill="x", padx=12, pady=(0, 12), side="bottom")

    menu_header = ctk.CTkFrame(face_menu, fg_color=COLOR_GUINDA, height=42, corner_radius=0)
    menu_header.pack(fill="x")
    menu_header.pack_propagate(False)
    
    ctk.CTkLabel(menu_header, text="Opciones", text_color="white", font=ctk.CTkFont(size=10, weight="bold")).place(x=12, rely=0.5, anchor="w")
    ctk.CTkButton(menu_header, text="←", width=28, height=28, fg_color="transparent", text_color="white",
                  command=lambda: toggle_menu(False)).place(relx=1.0, x=-6, rely=0.5, anchor="e")

    items_frame = ctk.CTkFrame(face_menu, fg_color="transparent")
    items_frame.pack(fill="both", expand=True, padx=6, pady=(8, 4))

    texto_analisis = "📊   Ver análisis" if ya_analizada else "🔍   Analizar presentación"
    cmd_analisis   = (lambda: _ver_analisis(subject, name, ruta_pdf, toggle_menu)) if ya_analizada else (lambda: _iniciar_analisis(subject, name, ruta_pdf, toggle_menu, comando_actualizar_boton))

    opciones = [
        ("🖥   Presentar clase",          "#1E293B", lambda: _presentar_clase_ui(subject, name, ruta_pdf, toggle_menu)),
        (texto_analisis,                  "#1E293B", cmd_analisis),
        ("🔄   Actualizar presentación",   "#1E293B", lambda: _actualizar_presentacion_ui(subject, name, toggle_menu, comando_actualizar_boton)),
        ("🕓   Ver historial",            "#1E293B", lambda: _ver_historial(subject, name, toggle_menu)),
        ("📈   Ver rendimiento",          "#1E293B", lambda: _ver_rendimiento_ui(subject, ruta_pdf, name, toggle_menu)),
    ]

    for label, color, cmd in opciones:
        _menu_item(items_frame, label, color, cmd)

    ctk.CTkFrame(face_menu, height=1, fg_color="#F1F5F9").pack(fill="x", padx=10)

    def on_delete():
        toggle_menu(False)
        _remove_file(subject, name, comando_actualizar_boton)

    ctk.CTkButton(face_menu, text="🗑   Eliminar", fg_color="transparent", text_color="#EF4444", 
                  hover_color="#FEF2F2", font=ctk.CTkFont(size=11, weight="bold"),
                  anchor="w", command=on_delete).pack(fill="x", padx=6, pady=(4, 8), side="bottom")

    return outer 

def _ver_rendimiento_ui(subject: str, ruta_pdf: str, nombre_presentacion: str, toggle_menu):
    """Navega a la vista de análisis de rendimiento y tiempos."""
    toggle_menu(False)
    navigator.ir_a_rendimiento(subject, nombre_presentacion, ruta_pdf)


def _presentar_clase_ui(subject: str, name: str, ruta_pdf: str, toggle_menu):
    """Cierra la cara del menú y ordena al navegador cargar el modo presentación."""
    toggle_menu(False)
    navigator.ir_a_presentacion(subject, name, ruta_pdf)


def _actualizar_presentacion_ui(subject: str, nombre_presentacion: str, toggle_menu, comando_actualizar_boton):
    """
    Abre el cuadro de diálogo para seleccionar el nuevo archivo .pptx,
    bloquea la UI, ejecuta la orquestación en hilo secundario y refresca la vista.
    """
    if estado.get("bloqueo_ui"): return
    toggle_menu(False) 
    
    file_path = filedialog.askopenfilename(filetypes=[("PPTX", "*.pptx")])
    if not file_path: return
    
    estado["bloqueo_ui"] = True
    loading_modal = mostrar_modal_cargando(ui["root"], "Actualizando versión...")
    subject_id = obtener_id_materia(subject)

    def update_task():
        return orquestar_actualizacion_presentacion(file_path, nombre_presentacion, subject_id)

    def finalize_update(resultado_tupla):
        exito, mensaje = resultado_tupla
        if loading_modal.winfo_exists():
            ui["root"].after(100, loading_modal.destroy)
        
        if exito:
            estado["subject_files"][subject] = obtener_archivos_materia(subject_id)
            rebuild_cards(subject, comando_actualizar_boton)
            comando_actualizar_boton()
        else:
            advertir_presentacion_existente(ui["root"], mensaje)
            
        estado["bloqueo_ui"] = False

    ejecutar_tarea_asincrona(target_task=update_task, on_finished_callback=finalize_update)


def _menu_item(parent, text: str, color: str, command):
    """Crea un botón de opción dentro del menú de la tarjeta."""
    ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        fg_color="transparent",
        hover_color="#F8FAFC",
        text_color=color,
        corner_radius=8,
        height=30,
        anchor="w",
        command=command,
    ).pack(fill="x", pady=1)


def _placeholder():
    pass


def _iniciar_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str, toggle_menu, comando_actualizar_boton):
    """
    Inicia el flujo real de análisis de IA.
    1. Bloquea la UI y cierra el menú de la tarjeta.
    2. Obtiene la ruta del PPTX (necesaria para el análisis).
    3. Ejecuta el orquestador en un hilo secundario.
    """
    if estado.get("bloqueo_ui"): return
    estado["bloqueo_ui"] = True
    toggle_menu(False)
    
    loading_modal = mostrar_modal_cargando(ui["root"], "Analizando presentación...")

    def update_status_console(msg):
        print(f"[UI-STATUS] {msg}")

    def tarea_analisis():
        id_materia = obtener_id_materia(subject)
        archivos = estado["subject_files"].get(subject, [])
        ruta_pptx = next((f[1] for f in archivos if f[0] == nombre_presentacion), None)
        
        if not ruta_pptx:
            return False, "No se encontró la ruta del archivo original."
        return orquestar_analisis_ia(ruta_pptx, nombre_presentacion, id_materia, status_cb=update_status_console)

    def finalizar(resultado_tupla):
        exito, contenido = resultado_tupla
        if loading_modal.winfo_exists():
            ui["root"].after(100, loading_modal.destroy)
            
        if exito:
            id_materia = obtener_id_materia(subject)
            estado["subject_files"][subject] = obtener_archivos_materia(id_materia)
            rebuild_cards(subject, comando_actualizar_boton)
            comando_actualizar_boton()
            estado["bloqueo_ui"] = False 
            navigator.ir_a_analisis(subject, nombre_presentacion, ruta_pdf)
        else:
            estado["bloqueo_ui"] = False
            print(f"Error en el análisis: {contenido}")
            from app.presentation.widgets.dialogs import mostrar_modal_advertencia
            mostrar_modal_advertencia(ui["root"], contenido, "Error de Conexión IA")

    ejecutar_tarea_asincrona(target_task=tarea_analisis, on_finished_callback=finalizar)


def _ver_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str, toggle_menu):
    """Navega directamente a la vista de análisis sin simular carga ni actualizar BD."""
    toggle_menu(False)
    navigator.ir_a_analisis(subject, nombre_presentacion, ruta_pdf)


def _ver_historial(subject: str, nombre_presentacion: str, toggle_menu):
    """Navega a la vista del historial de versiones."""
    toggle_menu(False)
    navigator.ir_a_historial(subject, nombre_presentacion)


def _make_upload_card(parent, subject, comando_actualizar_boton):
    """Crea y retorna la tarjeta de carga (sin posicionarla)."""
    card = ctk.CTkFrame(parent, width=CARD_W, height=CARD_H, fg_color="#FAFBFD", 
                        border_width=2, border_color="#E2E8F0", corner_radius=16, cursor="hand2")
    card.pack_propagate(False)

    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(inner, text="＋", font=ctk.CTkFont(size=24), text_color=COLOR_ORO).pack()
    ctk.CTkLabel(inner, text="Subir presentación", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748B").pack()

    def pick(e=None): _pick_files(subject, comando_actualizar_boton)
    card.bind("<Button-1>", pick)
    for w in inner.winfo_children(): w.bind("<Button-1>", pick)
    return card


def _pick_files(subject: str, comando_actualizar_boton: Callable):
    if estado.get("bloqueo_ui"): return
    estado["bloqueo_ui"] = True

    file_path = filedialog.askopenfilename(filetypes=[("PPTX", "*.pptx")])
    if not file_path:
        estado["bloqueo_ui"] = False
        return
    
    loading_modal = mostrar_modal_cargando(ui["root"], "Cargando presentación...")
    subject_id = obtener_id_materia(subject)

    def processing_task() -> dict:
        resultados = {"duplicado": None, "pesado": None}
        success, message = orquestar_proceso_completo(file_path, subject_id)
        if not success:
            nombre = os.path.basename(file_path)
            if "ya ha sido procesada" in message or "hash" in message:
                resultados["duplicado"] = nombre
            elif "demasiado pesado" in message:
                resultados["pesado"] = nombre
        return resultados

    def finalize_ui_update(resultados_procesamiento: dict):
        if loading_modal.winfo_exists():
            ui["root"].after(500, loading_modal.destroy)
        
        duplicado = resultados_procesamiento["duplicado"]
        pesado = resultados_procesamiento["pesado"]
        
        if duplicado:
            alert_msg = f"La presentación '{duplicado}' ya se encuentra registrada."
            advertir_presentacion_existente(ui["root"], alert_msg)
        elif pesado:
            alert_msg = f"La presentación '{pesado}' supera el límite de 30MB y no fue cargada."
            mostrar_modal_advertencia(ui["root"], alert_msg, "Límite de tamaño excedido")
        
        estado["subject_files"][subject] = obtener_archivos_materia(subject_id)
        rebuild_cards(subject, comando_actualizar_boton)
        comando_actualizar_boton()
        estado["bloqueo_ui"] = False

    ejecutar_tarea_asincrona(target_task=processing_task, on_finished_callback=finalize_ui_update)


def _remove_file(subject, name, comando_actualizar_boton):
    """Ejecuta la confirmación y orquestación de eliminación."""
    from app.presentation.views.main_gui import confirmar_eliminacion
    def on_confirm():
        id_m = obtener_id_materia(subject)
        if orquestar_eliminacion_presentacion(name, id_m):
            estado["subject_files"][subject] = obtener_archivos_materia(id_m)
            rebuild_cards(subject, comando_actualizar_boton)
            comando_actualizar_boton()
    confirmar_eliminacion(name, subject, on_confirm)