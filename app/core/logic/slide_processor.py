# app/core/logic/slide_processor.py
import os
import comtypes.client
import aspose.slides as slides


def generar_miniatura(ruta_pptx: str, ruta_salida_png: str) -> bool:
    """Genera un PNG de la primera diapositiva usando Aspose."""
    try:
        with slides.Presentation(ruta_pptx) as pres:
            if len(pres.slides) == 0:
                return False
            img = pres.slides[0].get_image(0.5, 0.5)
            img.save(ruta_salida_png)
            # dispose() no existe en esta versión de Aspose — no llamar
        return True
    except Exception as e:
        print(f"Error al generar miniatura: {e}")
        return False


def generar_pdf(ruta_pptx: str, ruta_salida_pdf: str) -> bool:
    """
    Convierte PPTX a PDF usando PowerPoint COM.
    Requiere Microsoft Office instalado.
    PowerPoint COM requiere Visible = True — la ventana aparece brevemente.
    ppSaveAsPDF = 32
    """
    powerpoint = None
    deck       = None
    try:
        ruta_pptx_abs = os.path.abspath(ruta_pptx)
        ruta_pdf_abs  = os.path.abspath(ruta_salida_pdf)

        powerpoint         = comtypes.client.CreateObject("Powerpoint.Application")
        powerpoint.Visible = True   # Requerido por COM — no se puede ocultar

        deck = powerpoint.Presentations.Open(ruta_pptx_abs, WithWindow=False)
        deck.SaveAs(ruta_pdf_abs, 32)

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