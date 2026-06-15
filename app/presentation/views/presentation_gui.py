# app/presentation/views/presentation_gui.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
import json
import os
from app.presentation.views.ui_state import ui
from app.core.controller.presentation_controller import orquestar_obtener_reporte_tiempo
from app.core.controller.subject_controller import obtener_id_materia_controlador

_contenedor_presentacion = None
_visor_panel = None
_datos_panel = None
_ventana_proyeccion = None 
_watchdog_id = None

# --- FORMULARIO MODAL UNIFICADO ---
def _obtener_configuracion_clase(root, json_reporte_raw):
    resultado = {"grupo": None, "tiempo": 0, "monitor_idx": 0, "cancelado": True}

    dialogo = ctk.CTkToplevel(root)
    dialogo.title("Configuración de Sesión")
    dialogo.geometry("400x580")
    dialogo.attributes("-topmost", True)
    dialogo.transient(root)
    dialogo.grab_set()  

    ctk.CTkLabel(dialogo, text="⚙️ Iniciar Clase", font=ctk.CTkFont(size=20, weight="bold"), text_color="#005088").pack(pady=(20, 10))

    # Lectura desde el string JSON en memoria (desde la BD)
    grupos_existentes = []
    if json_reporte_raw:
        try:
            data = json.loads(json_reporte_raw)
            grupos_existentes = list(data.get("grupos", {}).keys())
        except Exception: pass

    frame_g = ctk.CTkFrame(dialogo, fg_color="transparent")
    frame_g.pack(fill="x", padx=30, pady=10)
    ctk.CTkLabel(frame_g, text="1. Grupo Escolar:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

    modo_inicial = "Seleccionar" if grupos_existentes else "Crear Nuevo"
    modo_var = ctk.StringVar(value=modo_inicial)
    
    opciones_combo = grupos_existentes if grupos_existentes else ["Sin grupos previos"]
    combo_grupos = ctk.CTkComboBox(frame_g, values=opciones_combo, state="readonly")
    if grupos_existentes:
        combo_grupos.set(grupos_existentes[0])
    
    entry_nuevo = ctk.CTkEntry(frame_g, placeholder_text="Ej. 3CM2 (Máx 5 letras/núm)")

    def on_modo_change(value):
        if value == "Seleccionar":
            entry_nuevo.pack_forget()
            combo_grupos.pack(fill="x", pady=5)
        else:
            combo_grupos.pack_forget()
            entry_nuevo.pack(fill="x", pady=5)

    seg_btn = ctk.CTkSegmentedButton(frame_g, values=["Seleccionar", "Crear Nuevo"], variable=modo_var, command=on_modo_change)
    seg_btn.pack(fill="x", pady=(5, 10))
    on_modo_change(modo_var.get())

    frame_t = ctk.CTkFrame(dialogo, fg_color="transparent")
    frame_t.pack(fill="x", padx=30, pady=10)
    ctk.CTkLabel(frame_t, text="2. Tiempo Estimado (Máx 90 min):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

    frame_input = ctk.CTkFrame(frame_t, fg_color="transparent")
    frame_input.pack(pady=5)
    
    entry_tiempo = ctk.CTkEntry(frame_input, width=80, height=40, justify="center", font=ctk.CTkFont(size=20, weight="bold"), text_color="#10B981")
    entry_tiempo.insert(0, "60")
    entry_tiempo.pack(side="left")
    
    ctk.CTkLabel(frame_input, text="minutos", font=ctk.CTkFont(size=14)).pack(side="left", padx=(10, 0))

    frame_m = ctk.CTkFrame(dialogo, fg_color="transparent")
    frame_m.pack(fill="x", padx=30, pady=10)
    ctk.CTkLabel(frame_m, text="3. Dispositivo de Salida:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

    try:
        from screeninfo import get_monitors
        monitores = get_monitors()
    except ImportError:
        monitores = []

    lista_monitores = []
    for i, m in enumerate(monitores):
        nombre = f"Pantalla {i+1} ({m.width}x{m.height})"
        nombre += " [Principal]" if m.x == 0 and m.y == 0 else " [Proyector/Ext]"
        lista_monitores.append(nombre)
        
    if not lista_monitores:
        lista_monitores = ["Pantalla 1 (Simulada)"]

    combo_monitores = ctk.CTkComboBox(frame_m, values=lista_monitores, state="readonly")
    # Forzamos a que intente seleccionar el proyector si existe
    if len(lista_monitores) > 1:
        combo_monitores.set(lista_monitores[1])
    else:
        combo_monitores.set(lista_monitores[0])
    combo_monitores.pack(fill="x", pady=5)

    lbl_error = ctk.CTkLabel(dialogo, text="", text_color="red", font=ctk.CTkFont(size=12, weight="bold"))
    lbl_error.pack(pady=5)

    def confirmar():
        if modo_var.get() == "Seleccionar":
            if not grupos_existentes:
                lbl_error.configure(text="Error: No hay grupos. Crea uno nuevo.")
                return
            grupo_final = combo_grupos.get()
        else:
            grupo_final = entry_nuevo.get().strip().upper()
            if not grupo_final:
                lbl_error.configure(text="Error: El campo de grupo no puede estar vacío.")
                return
            if len(grupo_final) > 5 or not grupo_final.isalnum():
                lbl_error.configure(text="Error: Grupo debe ser alfanumérico (máx 5 caracteres).")
                return

        try:
            t_val = int(entry_tiempo.get().strip())
            if t_val <= 0 or t_val > 90:
                lbl_error.configure(text="Error: El tiempo debe ser mayor a 0 y máximo 90 min.")
                return
        except ValueError:
            lbl_error.configure(text="Error: Ingresa un número entero válido para el tiempo.")
            return

        # --- NUEVA REGLA: Evitar que proyecte en su propia laptop ---
        monitor_seleccionado_str = combo_monitores.get()
        if "[Principal]" in monitor_seleccionado_str or "Simulada" in monitor_seleccionado_str:
            lbl_error.configure(text="Error: Seleccione el Proyector/Ext, no la pantalla principal.")
            return
        # ------------------------------------------------------------

        resultado["grupo"] = grupo_final
        resultado["tiempo"] = t_val
        resultado["monitor_idx"] = lista_monitores.index(monitor_seleccionado_str)
        resultado["cancelado"] = False
        
        dialogo.grab_release()
        dialogo.destroy()

    ctk.CTkButton(dialogo, text="Iniciar Proyección", fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(weight="bold"), height=40, command=confirmar).pack(pady=10)

    root.wait_window(dialogo)
    return resultado


def _lanzar_proyeccion(root, ruta_pdf, indice_actual, pos_x, pos_y, ancho, alto):
    global _ventana_proyeccion, _datos_panel, _watchdog_id
    if _ventana_proyeccion is not None:
        _ventana_proyeccion.cerrar()
    
    root.protocol("WM_DELETE_WINDOW", lambda: print("[BLOQUEADO] Termina la presentación primero."))
    root.bind("<Escape>", lambda e: "break")
    ui["proyeccion_activa"] = True

    def al_cerrar_proyeccion():
        global _ventana_proyeccion, _watchdog_id
        _ventana_proyeccion = None
        
        if _watchdog_id is not None:
            root.after_cancel(_watchdog_id)
            _watchdog_id = None
        
        root.protocol("WM_DELETE_WINDOW", "") 
        root.unbind("<Escape>")
        ui["proyeccion_activa"] = False

        if _datos_panel is not None and _datos_panel.winfo_exists():
            _datos_panel.set_estado_proyeccion(False)
            if _visor_panel is not None and _visor_panel.winfo_exists():
                _visor_panel.focus_set()

    from app.presentation.views.projection_gui import crear_ventana_proyeccion
    _ventana_proyeccion = crear_ventana_proyeccion(
        root, ruta_pdf=ruta_pdf, pos_x=pos_x, pos_y=pos_y, ancho=ancho, alto=alto, on_close=al_cerrar_proyeccion
    )
    _ventana_proyeccion.sincronizar_pagina(indice_actual)
    
    if _datos_panel is not None:
        _datos_panel.set_estado_proyeccion(True)

    def verificar_conexion():
        global _watchdog_id, _ventana_proyeccion
        
        if _ventana_proyeccion is None:
            return

        try:
            from screeninfo import get_monitors
            monitores_actuales = get_monitors()
            
            if len(monitores_actuales) < 2 and pos_x != 0:
                print("[ALERTA] Proyector desconectado. Abortando presentación por seguridad.")
                _ventana_proyeccion.cerrar() 
                messagebox.showwarning(
                    "Conexión Perdida", 
                    "Se ha desconectado el proyector o pantalla secundaria.\nLa presentación se ha detenido por seguridad."
                )
                return
        except Exception:
            pass

        _watchdog_id = root.after(2000, verificar_conexion)

    if pos_x != 0:
        _watchdog_id = root.after(2000, verificar_conexion)


def _seleccionar_monitor_y_proyectar(root, subject, nombre_presentacion, ruta_pdf, indice_actual):
    # 1. Traer datos desde BD a través del controlador
    id_materia = obtener_id_materia_controlador(subject)
    json_reporte_raw = orquestar_obtener_reporte_tiempo(nombre_presentacion, id_materia)

    conf = _obtener_configuracion_clase(root, json_reporte_raw)
    if conf["cancelado"]:
        return

    grupo_seleccionado = conf["grupo"]
    tiempo_min = conf["tiempo"]
    monitor_idx = conf["monitor_idx"]

    if _datos_panel is not None:
        _datos_panel.tiempo_estimado_seg = tiempo_min * 60
        _datos_panel.grupo_actual = grupo_seleccionado
        _datos_panel.segundos_totales = 0
        _datos_panel.tiempos_por_slide = {}
        if hasattr(_datos_panel, "sesion_actual_llave"):
            delattr(_datos_panel, "sesion_actual_llave")

    # --- LECTURA DIRECTA DE LA DIAPOSITIVA (JSON BASE 1 EN MEMORIA) ---
    slide_reanudada = indice_actual
    if json_reporte_raw:
        try:
            data = json.loads(json_reporte_raw)
            grupo_data = data.get("grupos", {}).get(grupo_seleccionado, {})
            
            # Leemos la diapositiva en base 1 (para humanos)
            slide_guardada = grupo_data.get("ultima_diapositiva", 1)
            
            # Le restamos 1 para que el sistema interno no se salte ninguna
            slide_reanudada = max(0, slide_guardada - 1)
        except Exception: pass
        
    if _visor_panel is not None:
        if slide_reanudada >= getattr(_visor_panel, 'total_paginas', 1):
            slide_reanudada = getattr(_visor_panel, 'total_paginas', 1) - 1
            
        _visor_panel.pagina_actual = slide_reanudada
        indice_actual = slide_reanudada
        _visor_panel.renderizar_slide_actual() 
        if hasattr(_visor_panel, 'on_pagina_cambiada') and _visor_panel.on_pagina_cambiada:
            _visor_panel.on_pagina_cambiada(slide_reanudada)

    try:
        from screeninfo import get_monitors
        monitores = get_monitors()
        if not monitores: raise ImportError
        m = monitores[monitor_idx]
        pos_x, pos_y, ancho, alto = m.x, m.y, m.width, m.height
    except Exception:
        pos_x, pos_y, ancho, alto = 0, 0, 800, 600

    _lanzar_proyeccion(root, ruta_pdf, indice_actual, pos_x, pos_y, ancho, alto)


def mostrar_vista_presentacion(root, subject: str, nombre_presentacion: str, ruta_pdf: str):
    global _contenedor_presentacion, _visor_panel, _datos_panel, _ventana_proyeccion

    _contenedor_presentacion = ctk.CTkFrame(master=root, fg_color="#EEF2F7", corner_radius=0)
    _contenedor_presentacion.pack(fill="both", expand=True)

    from app.presentation.widgets.presentation_mode.slides_viewer_panel import crear_visor_diapositivas
    from app.presentation.widgets.presentation_mode.presentation_data_panel import crear_panel_datos

    def cmd_toggle_proyeccion():
        if _ventana_proyeccion is not None and _ventana_proyeccion.winfo_exists():
            _ventana_proyeccion.cerrar()
        else:
            # --- NUEVA REGLA: Bloqueo si no hay proyector ---
            try:
                from screeninfo import get_monitors
                if len(get_monitors()) < 2:
                    messagebox.showwarning(
                        "Proyector no detectado", 
                        "No se puede iniciar la clase.\nDebe conectar un proyector o monitor secundario para presentar."
                    )
                    return # Abortamos antes de mostrar la modal
            except Exception as e:
                print(f"Error leyendo monitores (librería no disponible): {e}")
                pass 
            # ------------------------------------------------

            # Enviamos el subject y nombre de presentacion al orquestador de monitor
            _seleccionar_monitor_y_proyectar(root, subject, nombre_presentacion, ruta_pdf, _visor_panel.pagina_actual)

    # Inyectamos "subject" en crear_panel_datos
    _datos_panel = crear_panel_datos(
        master=_contenedor_presentacion,
        subject=subject,
        nombre_presentacion=nombre_presentacion,
        ruta_pdf=ruta_pdf,
        visor_referencia=None,
        cmd_toggle_proyeccion=cmd_toggle_proyeccion,
        tiempo_estimado=0
    )
    _datos_panel.pack(side="right", fill="y", padx=(6, 12), pady=12)

    _visor_panel = crear_visor_diapositivas(master=_contenedor_presentacion, ruta_pdf=ruta_pdf)
    _visor_panel.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)
    
    def evento_cambio_pagina(indice_slide):
        _datos_panel.actualizar_contenido_por_slide(indice_slide)
        if _ventana_proyeccion is not None and _ventana_proyeccion.winfo_exists():
            _ventana_proyeccion.sincronizar_pagina(indice_slide)

    _datos_panel.visor = _visor_panel
    _visor_panel.on_pagina_cambiada = evento_cambio_pagina

    root.after(300, _visor_panel.renderizar_slide_actual)


def ocultar_vista_presentacion():
    global _contenedor_presentacion, _visor_panel, _datos_panel, _ventana_proyeccion, _watchdog_id

    if _watchdog_id is not None and _contenedor_presentacion is not None:
        _contenedor_presentacion.after_cancel(_watchdog_id)
        _watchdog_id = None

    if _ventana_proyeccion is not None:
        _ventana_proyeccion.cerrar()
        _ventana_proyeccion = None

    if _datos_panel is not None and _datos_panel.winfo_exists():
        if hasattr(_datos_panel, "generar_reporte_json"):
            _datos_panel.generar_reporte_json()

    if _visor_panel is not None:
        _visor_panel.cerrar_documento()
        _visor_panel.destroy()
        _visor_panel = None

    if _datos_panel is not None:
        _datos_panel.destroy()
        _datos_panel = None

    if _contenedor_presentacion is not None:
        _contenedor_presentacion.destroy()
        _contenedor_presentacion = None