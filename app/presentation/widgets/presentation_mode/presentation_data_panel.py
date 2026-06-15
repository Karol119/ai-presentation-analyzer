# app/presentation/widgets/presentation_mode/presentation_data_panel.py
import customtkinter as ctk
import json
from app.core.controller.presentation_controller import (
    orquestar_guardado_tiempos, 
    orquestar_obtener_reporte_tiempo, 
    orquestar_obtener_analisis
)
from app.core.controller.subject_controller import obtener_id_materia_controlador

COLOR_GUINDA = "#6A1B31"
COLOR_ORO = "#BC955C"
COLOR_TIEMPO = "#1E293B"

def crear_panel_datos(master, subject: str, nombre_presentacion: str, ruta_pdf: str, visor_referencia=None, cmd_toggle_proyeccion=None, tiempo_estimado=0, **kwargs):
    panel = ctk.CTkFrame(master, fg_color="white", corner_radius=14, width=320, border_width=1, border_color="#E8ECF2", **kwargs)
    panel.pack_propagate(False)
    
    # Guardamos los datos de contexto
    panel.subject = subject
    panel.nombre_presentacion = nombre_presentacion
    panel.visor = visor_referencia
    panel.cached_data = {}
    
    panel.grupo_actual = "GENERAL"
    panel.tiempo_estimado_seg = tiempo_estimado * 60
    panel.segundos_totales = 0
    panel.indice_slide_actual = 0
    panel.tiempos_por_slide = {}  
    panel.cronometro_id = None
    panel._reporte_guardado = False  

    # --- CARGA DEL ANÁLISIS DESDE LA BASE DE DATOS ---
    id_materia = obtener_id_materia_controlador(panel.subject)
    json_analisis_raw = orquestar_obtener_analisis(panel.nombre_presentacion, id_materia)
    
    if json_analisis_raw:
        try:
            panel.cached_data = json.loads(json_analisis_raw)
        except Exception as e: 
            print(f"Error parseando análisis: {e}")

    # --- HEADER ---
    header_frame = ctk.CTkFrame(panel, fg_color="transparent")
    header_frame.pack(fill="x", padx=16, pady=(18, 5))
    ctk.CTkLabel(header_frame, text="🎯 Apoyo de Clase", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=COLOR_GUINDA).pack(anchor="w")
    
    # --- CRONÓMETROS ---
    timer_box = ctk.CTkFrame(panel, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color="#E2E8F0")
    timer_box.pack(fill="x", padx=16, pady=5)

    total_frame = ctk.CTkFrame(timer_box, fg_color="transparent")
    total_frame.pack(fill="x", padx=10, pady=(10, 5))
    ctk.CTkLabel(total_frame, text="⏱ TOTAL (Sesión)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748B").pack(side="left")
    panel.label_timer_total = ctk.CTkLabel(total_frame, text="00:00", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color=COLOR_TIEMPO)
    panel.label_timer_total.pack(side="right")

    slide_frame = ctk.CTkFrame(timer_box, fg_color="transparent")
    slide_frame.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkLabel(slide_frame, text="📄 ESTA SLIDE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748B").pack(side="left")
    panel.label_timer_slide = ctk.CTkLabel(slide_frame, text="00:00", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color=COLOR_TIEMPO)
    panel.label_timer_slide.pack(side="right")

    # --- SCROLL CENTRAL ---
    scroll_frame = ctk.CTkScrollableFrame(panel, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True, padx=14, pady=5)

    # --- FOOTER DE NAVEGACIÓN ---
    footer = ctk.CTkFrame(panel, fg_color="#FAFBFD", height=150, corner_radius=12, border_width=1, border_color="#F1F5F9")
    footer.pack(fill="x", padx=12, pady=12, side="bottom")
    footer.pack_propagate(False)

    nav_box = ctk.CTkFrame(footer, fg_color="transparent")
    nav_box.pack(fill="x", padx=10, pady=(10, 5))

    panel._btn_lock = False

    def btn_retroceder_cmd():
        if getattr(panel, '_btn_lock', False): return
        if panel.visor:
            panel._btn_lock = True
            panel.visor.retroceder_pagina()
            panel.visor.focus_set()
            panel.after(400, lambda: setattr(panel, '_btn_lock', False))

    def btn_avanzar_cmd():
        if getattr(panel, '_btn_lock', False): return
        if panel.visor:
            panel._btn_lock = True
            panel.visor.avanzar_pagina()
            panel.visor.focus_set()
            panel.after(400, lambda: setattr(panel, '_btn_lock', False))

    btn_ant = ctk.CTkButton(nav_box, text="◀", width=35, height=28, fg_color=COLOR_GUINDA, hover_color="#4D1324", command=btn_retroceder_cmd)
    btn_ant.pack(side="left")
    
    nav_center = ctk.CTkFrame(nav_box, fg_color="transparent")
    nav_center.pack(side="left", fill="x", expand=True)

    panel.entry_pagina = ctk.CTkEntry(nav_center, width=35, height=26, justify="center", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
    panel.entry_pagina.pack(side="left", expand=True, anchor="e", padx=(0, 2))

    panel.label_paginas_total = ctk.CTkLabel(nav_center, text="/ -", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#334155")
    panel.label_paginas_total.pack(side="left", expand=True, anchor="w", padx=(2, 0))

    def saltar_pagina_cmd(event=None):
        if not panel.visor: return
        try:
            pag_objetivo = int(panel.entry_pagina.get()) - 1
            total = panel.visor.total_paginas
            if 0 <= pag_objetivo < total:
                panel.visor.pagina_actual = pag_objetivo
                panel.visor.renderizar_slide_actual()
                if hasattr(panel.visor, 'on_pagina_cambiada') and panel.visor.on_pagina_cambiada:
                    panel.visor.on_pagina_cambiada(pag_objetivo)
            else:
                raise ValueError
        except ValueError:
            panel.entry_pagina.delete(0, 'end')
            panel.entry_pagina.insert(0, str(panel.indice_slide_actual + 1))
        panel.focus_set()

    panel.entry_pagina.bind("<Return>", saltar_pagina_cmd)

    btn_sig = ctk.CTkButton(nav_box, text="▶", width=35, height=28, fg_color=COLOR_GUINDA, hover_color="#4D1324", command=btn_avanzar_cmd)
    btn_sig.pack(side="right")

    grid_box = ctk.CTkFrame(footer, fg_color="transparent")
    grid_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    grid_box.grid_columnconfigure(0, weight=1)

    # --- LÓGICA DE TIEMPO ---
    def formatear_tiempo(segundos):
        m, s = divmod(segundos, 60)
        return f"{int(m):02d}:{int(s):02d}"

    def actualizar_reloj():
        if not panel.winfo_exists() or panel.cronometro_id is None: 
            return
            
        panel.segundos_totales += 1
        idx = panel.indice_slide_actual
        if idx not in panel.tiempos_por_slide:
            panel.tiempos_por_slide[idx] = 0
        panel.tiempos_por_slide[idx] += 1
        
        panel.label_timer_total.configure(text=formatear_tiempo(panel.segundos_totales))
        panel.label_timer_slide.configure(text=formatear_tiempo(panel.tiempos_por_slide[idx]))
        
        if panel.tiempo_estimado_seg > 0 and panel.segundos_totales > panel.tiempo_estimado_seg:
            panel.label_timer_total.configure(text_color="#EF4444")
        else:
            panel.label_timer_total.configure(text_color=COLOR_TIEMPO)
                
        panel.cronometro_id = panel.after(1000, actualizar_reloj)

    # --- GENERADOR DE REPORTE JSON EN BD (BASE 1) ---
    def generar_reporte_json():
        if panel.segundos_totales <= 0: return
        if panel._reporte_guardado: return
        
        id_materia_db = obtener_id_materia_controlador(panel.subject)
        data = {"archivo": panel.nombre_presentacion, "grupos": {}}
        
        # Recuperamos el reporte actual crudo desde la BD
        json_raw = orquestar_obtener_reporte_tiempo(panel.nombre_presentacion, id_materia_db)
        
        if json_raw:
            try:
                data = json.loads(json_raw)
            except Exception: pass
            
        if panel.grupo_actual not in data["grupos"]: 
            data["grupos"][panel.grupo_actual] = {
                "ultima_diapositiva": 1,
                "tiempo_total_seg": 0,
                "tiempos_por_slide": {},
                "historial_sesiones": {}
            }
            
        g_data = data["grupos"][panel.grupo_actual]
        
        # Guardar en JSON sumando +1 (Humano)
        g_data["ultima_diapositiva"] = panel.indice_slide_actual + 1 
        g_data["tiempo_total_seg"] += panel.segundos_totales
        
        for idx, segs in panel.tiempos_por_slide.items():
            str_idx = str(idx + 1)
            g_data["tiempos_por_slide"][str_idx] = g_data["tiempos_por_slide"].get(str_idx, 0) + segs

        # Convertir el desglose de la sesión actual a base 1
        tiempos_slide_base_1 = {str(k + 1): v for k, v in panel.tiempos_por_slide.items()}

        sesiones = g_data["historial_sesiones"]
        num_sesion = str(len(sesiones) + 1)
        
        sesiones[num_sesion] = {
            "planeado_seg": panel.tiempo_estimado_seg,
            "duracion_seg": panel.segundos_totales,
            "tiempos_slide": tiempos_slide_base_1
        }
        
        # Empaquetamos y mandamos al controlador
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        exito = orquestar_guardado_tiempos(panel.nombre_presentacion, id_materia_db, json_str)
        
        if exito:
            panel._reporte_guardado = True

    # --- BOTONES Y BLOQUEO ANTI-MULTICLIC ---
    panel._is_toggling = False

    def safe_toggle():
        """Evita que el usuario haga múltiples clics rápidos (Anti-Multiclic)"""
        if panel._is_toggling: return
        panel._is_toggling = True
        
        btn_presentar.configure(state="disabled")
        btn_stop.configure(state="disabled")
        
        if cmd_toggle_proyeccion:
            cmd_toggle_proyeccion()
            
        panel.after(1000, lambda: setattr(panel, '_is_toggling', False))
        panel.after(1000, lambda: btn_presentar.configure(state="normal"))
        panel.after(1000, lambda: btn_stop.configure(state="normal"))

    btn_presentar = ctk.CTkButton(grid_box, text="📺 Presentar", height=35, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(weight="bold"), command=safe_toggle)
    btn_presentar.grid(row=0, column=0, sticky="nsew", pady=2)

    btn_stop = ctk.CTkButton(grid_box, text="⏹ Detener", height=35, fg_color="#EF4444", hover_color="#DC2626", font=ctk.CTkFont(weight="bold"), command=safe_toggle)

    def set_estado_proyeccion(activo: bool):
        if activo:
            panel._reporte_guardado = False 
            btn_presentar.grid_remove() # Ocultamos Presentar
            btn_stop.grid(row=0, column=0, sticky="nsew", pady=2) # Mostramos Detener en su mismo lugar
            panel.cronometro_id = panel.after(1000, actualizar_reloj)
        else:
            if panel.cronometro_id:
                panel.after_cancel(panel.cronometro_id)
                panel.cronometro_id = None
            
            generar_reporte_json()
            
            btn_stop.grid_remove() # Ocultamos Detener
            btn_presentar.grid(row=0, column=0, sticky="nsew", pady=2) # Volvemos a mostrar Presentar

    panel.set_estado_proyeccion = set_estado_proyeccion
    panel.generar_reporte_json = generar_reporte_json

    # --- REFRENDADO DE CONTENIDO (IA) ---
    def actualizar_contenido_por_slide(indice_slide):
        for widget in scroll_frame.winfo_children():
            widget.destroy()

        panel.indice_slide_actual = indice_slide
        if indice_slide not in panel.tiempos_por_slide:
            panel.tiempos_por_slide[indice_slide] = 0

        total = panel.visor.total_paginas if panel.visor else 1
        
        panel.entry_pagina.delete(0, 'end')
        panel.entry_pagina.insert(0, str(indice_slide + 1))
        panel.label_paginas_total.configure(text=f"/ {total}")
        
        panel.label_timer_slide.configure(text=formatear_tiempo(panel.tiempos_por_slide[indice_slide]))

        if panel.visor:
            btn_ant.configure(state="disabled" if indice_slide == 0 else "normal")
            btn_sig.configure(state="disabled" if indice_slide >= total - 1 else "normal")

        # --- EXTRACCIÓN BASADA EN TU JSON ---
        slide_data = {}
        if isinstance(panel.cached_data, dict) and "slides" in panel.cached_data:
            lista_slides = panel.cached_data["slides"]
            if indice_slide < len(lista_slides):
                slide_data = lista_slides[indice_slide]

        preguntas = slide_data.get("preguntas") or []
        datos_extra = slide_data.get("datos_curiosos") or []

        # --- PINTADO EN INTERFAZ ---
        if preguntas:
            card_p = ctk.CTkFrame(scroll_frame, fg_color="#F8FAFC", border_width=1, border_color="#E2E8F0", corner_radius=10)
            card_p.pack(fill="x", pady=6)
            ctk.CTkLabel(card_p, text="❓ Preguntas de Evaluación", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_GUINDA, anchor="w").pack(fill="x", padx=12, pady=(10, 4))
            for p in preguntas:
                ctk.CTkLabel(card_p, text=f"• {p}", font=ctk.CTkFont(size=11), text_color="#334155", wraplength=250, justify="left", anchor="w").pack(fill="x", padx=16, pady=3)

        if datos_extra:
            card_d = ctk.CTkFrame(scroll_frame, fg_color="#F8FAFC", border_width=1, border_color="#E2E8F0", corner_radius=10)
            card_d.pack(fill="x", pady=6)
            ctk.CTkLabel(card_d, text="💡 Datos Curiosos / Complementarios", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_ORO, anchor="w").pack(fill="x", padx=12, pady=(10, 4))
            for d in datos_extra:
                ctk.CTkLabel(card_d, text=f"• {d}", font=ctk.CTkFont(size=11), text_color="#334155", wraplength=250, justify="left", anchor="w").pack(fill="x", padx=16, pady=3)

        if not preguntas and not datos_extra:
            ctk.CTkLabel(scroll_frame, text="Sin anotaciones de IA para esta slide.", font=ctk.CTkFont(size=11, slant="italic"), text_color="#94A3B8").pack(pady=40)

    panel.actualizar_contenido_por_slide = actualizar_contenido_por_slide

    if panel.visor is not None:
        panel.visor.on_pagina_cambiada = panel.actualizar_contenido_por_slide
        panel.actualizar_contenido_por_slide(panel.visor.pagina_actual)

    return panel