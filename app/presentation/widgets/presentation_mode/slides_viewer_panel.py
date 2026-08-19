# app/presentation/widgets/presentation_mode/slides_viewer_panel.py
import fitz
import customtkinter as ctk
from PIL import Image
import io

COLOR_GUINDA = "#6A1B31"

def crear_visor_diapositivas(master, ruta_pdf: str, **kwargs):
    # Extraer estilos o usar defaults
    bg_color = kwargs.pop("fg_color", "white")
    radius = kwargs.pop("corner_radius", 14)
    b_width = kwargs.pop("border_width", 1)
    b_color = kwargs.pop("border_color", "#E8ECF2")

    # Crear el contenedor base
    panel = ctk.CTkFrame(master, fg_color=bg_color, corner_radius=radius, border_width=b_width, border_color=b_color, **kwargs)
    
    # Simular estado adjuntando variables al panel
    panel.ruta_pdf = ruta_pdf
    panel.pagina_actual = 0
    panel.total_paginas = 0
    panel.doc = None
    panel._resize_after_id = None
    panel.on_pagina_cambiada = None 

    panel.label_imagen = ctk.CTkLabel(panel, text="Cargando diapositiva...", fg_color="transparent")
    panel.label_imagen.pack(fill="both", expand=True, padx=20, pady=20)

    # --- Lógica Interna ---
    try:
        panel.doc = fitz.open(panel.ruta_pdf)
        panel.total_paginas = len(panel.doc)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir el PDF en el visor: {e}")
        panel.label_imagen.configure(text="Error al cargar el archivo.")

    def renderizar_slide_actual():
        if not panel.doc or panel.pagina_actual >= panel.total_paginas:
            return

        panel.update_idletasks()
        ancho_max = panel.label_imagen.winfo_width() - 10
        alto_max  = panel.label_imagen.winfo_height() - 10

        if ancho_max < 50 or alto_max < 50:
            panel.after(100, renderizar_slide_actual)
            return

        try:
            page = panel.doc[panel.pagina_actual]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_pil = Image.open(io.BytesIO(pixmap.tobytes("png")))
            img_pil.thumbnail((ancho_max, alto_max), Image.LANCZOS)

            escala = ctk.ScalingTracker.get_widget_scaling(panel)
            ancho_logico = int(img_pil.width / escala)
            alto_logico = int(img_pil.height / escala)

            img_ctk = ctk.CTkImage(light_image=img_pil, size=(ancho_logico, alto_logico))
            panel.label_imagen.configure(image=img_ctk, text="")
            panel.label_imagen._image = img_ctk  
            
            if panel.on_pagina_cambiada:
                panel.on_pagina_cambiada(panel.pagina_actual)
        except Exception as e:
            print(f"[ERROR] Al renderizar diapositiva: {e}")

    def avanzar_pagina(event=None):
        if panel.pagina_actual < panel.total_paginas - 1:
            panel.pagina_actual += 1
            renderizar_slide_actual()
            return True
        return False

    def retroceder_pagina(event=None):
        if panel.pagina_actual > 0:
            panel.pagina_actual -= 1
            renderizar_slide_actual()
            return True
        return False

    def al_redimensionar(event):
        if event.width > 50 and event.height > 50:
            if panel._resize_after_id:
                panel.after_cancel(panel._resize_after_id)
            panel._resize_after_id = panel.after(60, renderizar_slide_actual)

    def cerrar_documento():
        if panel.doc:
            panel.doc.close()
            panel.doc = None

    # Exponer las funciones anexándolas al panel
    panel.renderizar_slide_actual = renderizar_slide_actual
    panel.avanzar_pagina = avanzar_pagina
    panel.retroceder_pagina = retroceder_pagina
    panel.cerrar_documento = cerrar_documento

    # Bindings
    panel.bind("<Configure>", al_redimensionar)
    panel.focus_set()
    panel.bind("<Left>", retroceder_pagina)
    panel.bind("<Right>", avanzar_pagina)

    return panel