from app.core.logic.text_extractor   import extraer_datos_pptx
from app.core.logic.slide_classifier  import clasificar_diapositiva
from app.infrastructure.ollama.ollama_service import (
    clasificar_tipo_diapositiva,
    verificar_conexion
)


def analizar_presentacion(ruta_pptx, usar_llm=True):
    llm_fn = None
    llm_disponible = False

    if usar_llm:
        llm_disponible = verificar_conexion()
        if llm_disponible:
            llm_fn = clasificar_tipo_diapositiva
            print("[analyzer] Ollama disponible")
        else:
            print("[analyzer] Ollama no disponible — solo reglas")

    datos = extraer_datos_pptx(ruta_pptx)
    print(f"[analyzer] {datos['total_slides']} diapositivas")

    conteo = {"contenido": 0, "excluidas": 0, "por_llm": 0, "inciertas": 0}

    for slide in datos["slides"]:
        clasificacion       = clasificar_diapositiva(slide, llm_fn=llm_fn)
        slide["clasificacion"] = clasificacion

        if clasificacion["excluir"]:
            conteo["excluidas"] += 1
        else:
            conteo["contenido"] += 1

        if clasificacion["metodo"] == "llm":
            conteo["por_llm"] += 1

        if clasificacion["confianza"] < 0.70:
            conteo["inciertas"] += 1

        print(f"  [{slide['slide_number']:02d}] {clasificacion['tipo']:<12} "
              f"conf:{clasificacion['confianza']:.2f} método:{clasificacion['metodo']}")

    datos["llm_disponible"]        = llm_disponible
    datos["resumen_clasificacion"] = conteo

    return datos


def obtener_slides_contenido(resultado):
    return [s for s in resultado["slides"] if not s["clasificacion"]["excluir"]]