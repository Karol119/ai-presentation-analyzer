from app.core.controller.presentation_controller import orquestar_proceso_completo

if __name__ == "__main__":
    exito, mensaje = orquestar_proceso_completo()
    print(mensaje)