# app/infrastructure/ollama/ollama_service.py
import requests
import subprocess
import time

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "mistral"
TIMEOUT_SEG = 15

_TIPOS_VALIDOS = {"portada", "indice", "referencias", "cierre", "contenido"}

_PROMPT = """Eres un clasificador de diapositivas académicas universitarias.

Clasifica la diapositiva en EXACTAMENTE UNO de estos tipos:
  portada     → portada principal, título del curso, datos del autor
  indice      → lista de temas, agenda, tabla de contenido
  referencias → bibliografía, fuentes, webgrafía, citas
  cierre      → cierre, gracias, preguntas, conclusiones
  contenido   → contenido educativo real del tema

Responde ÚNICAMENTE con una de esas cinco palabras, en minúsculas, sin explicación.

Título: {titulo}
Contenido: {contenido}

Tipo:"""


def clasificar_tipo_diapositiva(slide_data):
    titulo   = slide_data.get("title", "").strip() or "(sin título)"
    contenido = " | ".join(slide_data.get("content", []))[:500]

    prompt = _PROMPT.format(
        titulo=titulo,
        contenido=contenido or "(sin contenido)"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 10}
            },
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        tipo_raw = response.json().get("response", "").strip().lower()
        return _parsear_tipo(tipo_raw)

    except requests.exceptions.ConnectionError:
        print("[ollama] No disponible")
        return None
    except Exception as e:
        print(f"[ollama] Error: {e}")
        return None


def verificar_conexion():
    try:
        r = requests.get("http://localhost:11434/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _parsear_tipo(respuesta):
    limpio = respuesta.strip().strip(".,;:\"'").lower()
    if limpio in _TIPOS_VALIDOS:
        return limpio
    for tipo in _TIPOS_VALIDOS:
        if tipo in limpio:
            return tipo
    return None

def verificar_conexion():
    """Verifica si el servicio de Ollama ya está corriendo en el puerto 11434."""
    try:
        r = requests.get("http://localhost:11434/", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def iniciar_ollama_background():
    """
    Verifica si Ollama está activo. Si no lo está, lo arranca en un proceso 
    secundario oculto y espera a que esté listo.
    Retorna True si logró conectar, False si falló catastróficamente.
    """
    if verificar_conexion():
        print("[ollama] El servicio ya estaba activo en segundo plano.")
        return True

    print("[ollama] Servicio apagado. Intentando arrancar Ollama automáticamente...")
    try:
        # Ejecuta 'ollama serve' en segundo plano, suprimiendo las salidas de la consola
        subprocess.Popen(
            ["ollama", "serve"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            # shell=True # (Opcional: Solo si en Windows tira error de archivo no encontrado)
        )
        
        # Le damos unos segundos para que levante el servidor HTTP local
        intentos = 0
        while intentos < 15:
            time.sleep(1)
            if verificar_conexion():
                print("[ollama] ¡Servicio iniciado con éxito por el programa!")
                return True
            intentos += 1
            
        print("[ollama] Timeout: Ollama tardó demasiado en iniciar.")
        return False
        
    except FileNotFoundError:
        print("[ollama] Error Crítico: Ollama no está instalado en este equipo o no está en las variables de entorno.")
        return False