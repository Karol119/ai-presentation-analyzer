# app/infrastructure/ollama/ollama_client.py
import requests
import subprocess
import time

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
OLLAMA_PULL_URL = f"{OLLAMA_HOST}/api/pull"

MODELO_POR_DEFECTO = "mistral"
TIMEOUT_CARGA = 60

def verificar_conexion() -> bool:
    """Verifica si el servicio de Ollama ya está corriendo."""
    try:
        r = requests.get(OLLAMA_HOST, timeout=2)
        return r.status_code == 200
    except requests.RequestException:
        return False

def arrancar_ollama_background() -> bool:
    """Intenta arrancar Ollama en segundo plano."""
    if verificar_conexion():
        return True

    try:
        subprocess.Popen(
            ["ollama", "serve"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        for _ in range(15):
            time.sleep(1)
            if verificar_conexion():
                return True
        return False
    except FileNotFoundError:
        return False

def modelo_esta_instalado(modelo: str = MODELO_POR_DEFECTO) -> bool:
    """Verifica si el modelo específico ya está descargado en Ollama."""
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=5)
        response.raise_for_status()
        modelos_instalados = response.json().get("models", [])
        # Ollama a veces guarda el modelo como "mistral:latest"
        for m in modelos_instalados:
            if m.get("name", "").startswith(modelo):
                return True
        return False
    except requests.RequestException:
        return False

def instalar_modelo(modelo: str = MODELO_POR_DEFECTO) -> bool:
    """Descarga el modelo. Esto puede tardar varios minutos dependiendo del internet."""
    try:
        # stream=False bloquea hasta que termine la descarga. 
        # Si la GUI se congela, se puede adaptar a stream=True en el futuro.
        response = requests.post(
            OLLAMA_PULL_URL,
            json={"model": modelo},
            stream=False,
            timeout=600 # 10 minutos de timeout para descargas pesadas
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False

def inicializar_motor_llm(ask_install_callback=None) -> bool:
    """
    Orquesta el encendido y validación del modelo.
    ask_install_callback: Función que retorna un bool. La GUI la inyecta para preguntar al usuario.
    """
    if not arrancar_ollama_background():
        return False

    if not modelo_esta_instalado(MODELO_POR_DEFECTO):
        if ask_install_callback:
            # Preguntamos al usuario a través del callback (la GUI mostrará un popup)
            quiere_instalar = ask_install_callback(MODELO_POR_DEFECTO)
            if quiere_instalar:
                return instalar_modelo(MODELO_POR_DEFECTO)
            else:
                return False # El usuario canceló la instalación
        return False # No está instalado y no hay forma de preguntar

    return True

def generar_respuesta(prompt: str, formato: str = None, options: dict = None, timeout: int = 35) -> requests.Response:
    """
    Cliente centralizado para hacer peticiones a Ollama.
    Retorna el objeto Response de requests.
    """
    payload = {
        "model": MODELO_POR_DEFECTO,
        "prompt": prompt,
        "stream": False
    }
    if formato:
        payload["format"] = formato
    if options:
        payload["options"] = options

    return requests.post(
        OLLAMA_GENERATE_URL,
        json=payload,
        timeout=timeout
    )