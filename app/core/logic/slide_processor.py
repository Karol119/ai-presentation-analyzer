# app/core/logic/slide_processor.py
import os
import comtypes.client

def generar_miniatura(ruta_pptx: str, ruta_salida_png: str) -> bool:
    """Genera un PNG de la primera diapositiva usando PowerPoint COM (comtypes)."""
    powerpoint = None
    deck = None
    try:
        ruta_pptx_abs = os.path.abspath(ruta_pptx)
        ruta_salida_png_abs = os.path.abspath(ruta_salida_png)

        # Iniciamos la instancia de PowerPoint en segundo plano
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        
        try:
            powerpoint.Visible = False
        except Exception:
            powerpoint.Visible = True
            try:
                powerpoint.WindowState = 2  
            except Exception:
                pass

        # Abrimos la presentación
        deck = powerpoint.Presentations.Open(ruta_pptx_abs, WithWindow=False)
        
        # Validamos que la presentación tenga al menos una diapositiva
        if len(deck.Slides) == 0:
            return False
            
        # Tomamos la primera diapositiva (en COM el índice empieza en 1)
        primera_diapositiva = deck.Slides(1)
        
        # Exportamos la diapositiva directamente a formato PNG
        # Los parámetros finales especifican el ancho y alto deseados de la imagen
        primera_diapositiva.Export(ruta_salida_png_abs, "PNG", ScaleWidth=960, ScaleHeight=540)
        
        return True

    except Exception as e:
        print(f"Error al generar miniatura con PowerPoint COM: {e}")
        return False

    finally:
        # Nos aseguramos de cerrar el archivo y quitar el proceso de PowerPoint
        if deck:
            try: deck.Close()
            except: pass
        if powerpoint:
            try: powerpoint.Quit()
            except: pass


def generar_pdf(ruta_pptx: str, ruta_salida_pdf: str) -> bool:
    powerpoint = None
    deck = None
    try:
        ruta_pptx_abs = os.path.abspath(ruta_pptx)
        ruta_pdf_abs  = os.path.abspath(ruta_salida_pdf)

        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")

        try:
            powerpoint.Visible = False
        except Exception:
            powerpoint.Visible = True
            try:
                powerpoint.WindowState = 2  
            except Exception:
                pass

        deck = powerpoint.Presentations.Open(ruta_pptx_abs, WithWindow=False)
        deck.SaveAs(ruta_pdf_abs, 32)  # ppSaveAsPDF
        return True

    except Exception as e:
        print(f"Error al generar PDF con PowerPoint COM: {e}")
        return False

    finally:
        if deck:
            try: deck.Close()
            except: pass
        if powerpoint:
            try: powerpoint.Quit()
            except: pass