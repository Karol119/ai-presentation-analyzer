from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER

# Ruta de tu archivo
ruta = r'C:/Users/kgonz/Desktop/TT/Presentaciones/Tema_2_Normatividad_de_la_lengua_escrita.pptx'

try:
    prs = Presentation(ruta)

    for i, slide in enumerate(prs.slides):
        print(f"\n=== DIAPOSITIVA {i+1} ===")
        
        # 1. Buscar el título (si existe)
        if slide.shapes.title:
            print(f"TITULO: {slide.shapes.title.text.upper()}")
        else:
            print("TITULO: (Sin título definido)")

        # 2. Buscar el resto del contenido
        print("CONTENIDO:")
        for shape in slide.shapes:
            # Evitamos repetir el título que ya imprimimos arriba
            if shape == slide.shapes.title:
                continue
                
            if hasattr(shape, "text") and shape.text.strip():
                # Limpiamos el texto de saltos de línea innecesarios
                texto_limpio = shape.text.replace('\n', ' ').strip()
                print(f" - {texto_limpio}")

except Exception as e:
    print(f"Error: {e}")