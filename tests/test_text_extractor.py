from app.core.controller.presentation_controller import orquestar_carga_presentacion

def probar_flujo_completo():
    print("--- Iniciando Prueba de Carga ---")
    
    # El test solo maneja las salidas (éxito o error)
    exito, mensaje = orquestar_carga_presentacion()
    
    if exito:
        print(f"✅ TEST PASADO: {mensaje}")
    else:
        print(f"❌ TEST FALLIDO: {mensaje}")

if __name__ == "__main__":
    probar_flujo_completo()