"""
app/infrastructure/llm_factory.py

Fábrica de funciones LLM.
Responsabilidad: leer la configuración del entorno y devolver el conjunto
de funciones de IA correspondiente al proveedor activo.

Regla de arquitectura:
  - Este módulo importa clientes de infraestructura (ollama_client, gemini_client).
  - Los servicios de dominio (coherencia_service, etc.) NO importan este módulo.
  - El controlador obtiene las funciones de aquí y las INYECTA en los servicios.
"""
import os
from functools import partial
from dotenv import load_dotenv

load_dotenv()


def get_llm_functions() -> dict:
    """
    Retorna un diccionario con las funciones de IA configuradas en .env.

    Claves del diccionario:
        inicializar : () → bool
        clasificar  : (slide_data) → str
        coherencia  : (titulo, contenido) → int | None
        narrativa   : (texto1, texto2) → int | None
        diagnostico : (slide_data, metricas, slide_prev, slide_next) → dict
        reestructurar: (slide_data, metricas, slide_prev, slide_next, progress_callback) → dict
        _raw_llm_fn : función primitiva de llamada HTTP (para inyectar en servicios Ollama)
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "gemini":
        return _build_gemini_functions()

    return _build_ollama_functions()


# ── Gemini ────────────────────────────────────────────────────────────────────

def _build_gemini_functions() -> dict:
    try:
        from app.infrastructure.gemini import gemini_client
    except ImportError:
        print("[llm_factory] gemini_client no disponible, usando Ollama como fallback.")
        return _build_ollama_functions()

    return {
        "inicializar":  gemini_client.inicializar_gemini,
        "clasificar":   gemini_client.clasificar_tipo_gemini,
        "coherencia":   gemini_client.verificar_coherencia_gemini,
        "narrativa":    gemini_client.verificar_hilo_gemini,
        "diagnostico":  gemini_client.generar_diagnostico_gemini,
        "reestructurar": gemini_client.reestructurar_slide_gemini,
        "_raw_llm_fn":  None,  # Gemini no usa la primitiva HTTP de Ollama
    }


# ── Ollama ────────────────────────────────────────────────────────────────────

def _build_ollama_functions() -> dict:
    from app.infrastructure.ollama import ollama_client
    from app.infrastructure.ollama import ollama_service
    from app.infrastructure.ollama import coherencia_service
    from app.infrastructure.ollama import narrativa_service
    from app.infrastructure.ollama import diagnostic_service
    from app.infrastructure.ollama import restructure_service

    # La primitiva HTTP: todos los servicios la reciben inyectada, no la importan.
    raw_fn = ollama_client.generar_respuesta

    return {
        "inicializar":  ollama_client.inicializar_motor_llm,

        # Usamos partial para pre-inyectar llm_fn y mantener la firma pública limpia
        "clasificar":   ollama_service.clasificar_tipo_diapositiva,

        "coherencia":   partial(coherencia_service.verificar_coherencia_titulo, llm_fn=raw_fn),
        "narrativa":    partial(narrativa_service.verificar_hilo_narrativo,     llm_fn=raw_fn),

        "diagnostico":  partial(diagnostic_service.generar_diagnostico_metrico, llm_fn=raw_fn),
        "reestructurar": partial(restructure_service.reestructurar_slide,       llm_fn=raw_fn),

        "_raw_llm_fn":  raw_fn,
    }