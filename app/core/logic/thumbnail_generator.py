import aspose.slides as slides

def generar_miniatura_aspose(ruta_pptx, ruta_salida_png):
    """
    Convierte la primera diapositiva a imagen PNG usando la API actualizada de Aspose.
    """
    try:
        with slides.Presentation(ruta_pptx) as pres:
            if len(pres.slides) > 0:
                slide = pres.slides[0]

                # get_image() devuelve un objeto de imagen — se guarda directo con la ruta
                img = slide.get_image(0.5, 0.5)
                img.save(ruta_salida_png)  # ✅ El formato PNG se infiere del .png en la ruta
                img.dispose()             # Buena práctica: liberar recursos

                return True
        return False
    except Exception as e:
        print(f"Error al generar miniatura con Aspose: {e}")
        return False