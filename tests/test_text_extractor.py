from app.core.controller.presentation_controller import orquestar_subida

def test_flujo_logico():
    print("--- Test: Disparando evento de carga ---")
    
    # El test no manda nada, solo espera
    exito, mensaje = orquestar_subida()
    
    if exito:
        print(f"✅ TEST FINALIZADO: {mensaje}")
    else:
        print(f"❌ TEST FINALIZADO: {mensaje}")

if __name__ == "__main__":
    test_flujo_logico()