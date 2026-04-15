import os
from dotenv import load_dotenv

load_dotenv()

def pedir_llm(prompt, json_mode=False, options=None):
    """
    Función de compatibilidad para servicios existentes.
    Utiliza importaciones locales para evitar ciclos infinitos.
    """
    # IMPORTACIÓN LOCAL (DENTRO) PARA ROMPER EL CICLO
    from app.infrastructure.llm_factory import get_llm_functions
    
    llm_functions = get_llm_functions()
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "gemini":
        from app.infrastructure.gemini.gemini_client import _llamar_gemini
        res_text = _llamar_gemini(prompt, json_mode=json_mode)
        
        class MockResponse:
            def __init__(self, text): self.text_val = text
            def json(self): return {"response": self.text_val}
            def raise_for_status(self): pass
        return MockResponse(res_text)
    
    else:
        from app.infrastructure.ollama.ollama_client import generar_respuesta
        return generar_respuesta(prompt, formato="json" if json_mode else None, options=options)