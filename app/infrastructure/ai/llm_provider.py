# app/infrastructure/ai/llm_provider.py
import os
import re
import requests
from importlib import import_module
from pathlib import Path
from dotenv import load_dotenv

try:
    genai = import_module("google.generativeai")
except ImportError as e:
    raise RuntimeError(
        "Falta la dependencia de Gemini. Instala el paquete "
        "'google-generativeai' en el entorno activo."
    ) from e

ruta_actual = Path(__file__).resolve()
ruta_raiz = ruta_actual.parent.parent.parent.parent
ruta_env = ruta_raiz / ".env"

load_dotenv(dotenv_path=ruta_env, override=True)

# Valor de reserva SOLO si el .env no define GEMINI_MODEL. El nombre del
# modelo que se usa en realidad SIEMPRE proviene del archivo .env
# (variable GEMINI_MODEL) o de lo que el usuario configure en el panel.
_MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"


def _leer_config_env() -> dict:
    """
    Lee DIRECTAMENTE el archivo .env (no las variables del proceso) para que
    siempre refleje el estado real del archivo:
      - Toma la PRIMERA línea ACTIVA (sin '#') de cada clave.
      - Ignora líneas comentadas y duplicados.
    """
    try:
        lineas = ruta_env.read_text(encoding="utf-8").splitlines() if ruta_env.exists() else []
    except OSError:
        lineas = []

    api_key = None
    modelo = None
    for linea in lineas:
        if api_key is None:
            m = re.match(r"^\s*GEMINI_API_KEY\s*=\s*(.*)$", linea)
            if m:
                api_key = m.group(1).strip().strip('"').strip("'")
        if modelo is None:
            m = re.match(r"^\s*GEMINI_MODEL\s*=\s*(.*)$", linea)
            if m:
                modelo = m.group(1).strip().strip('"').strip("'")
    return {"api_key": api_key or "", "modelo": modelo or ""}


def _sincronizar_globales() -> None:
    """Sincroniza las variables del módulo con el .env (y el proceso)."""
    global CLAVE_API_GEMINI, MODELO_GEMINI
    cfg = _leer_config_env()
    CLAVE_API_GEMINI = cfg["api_key"] or os.getenv("GOOGLE_API_KEY", "")
    MODELO_GEMINI = cfg["modelo"] or _MODELO_POR_DEFECTO
    os.environ["GEMINI_API_KEY"] = CLAVE_API_GEMINI
    os.environ["GEMINI_MODEL"] = MODELO_GEMINI


_sincronizar_globales()

genai.configure(api_key=CLAVE_API_GEMINI)
print(f"\n[PROVEEDOR IA] Conectado a la NUBE: Google Gemini — Modelo: '{MODELO_GEMINI}'")


def actualizar_configuracion_ia(nueva_api_key: str, nuevo_modelo: str) -> None:
    """
    Actualiza la API Key y el modelo de Gemini en caliente:
    - Reconfigura el SDK sin reiniciar la app.
    - Actualiza las variables de entorno del proceso.
    - Persiste los valores en el archivo .env: crea la variable si no existe
      y si ya existe SOLO actualiza su valor (sin duplicar líneas, sin
      dejar variantes comentadas viejas).
    """
    global CLAVE_API_GEMINI, MODELO_GEMINI

    CLAVE_API_GEMINI = nueva_api_key.strip()
    MODELO_GEMINI = nuevo_modelo.strip() or _MODELO_POR_DEFECTO

    os.environ["GEMINI_API_KEY"] = CLAVE_API_GEMINI
    os.environ["GEMINI_MODEL"] = MODELO_GEMINI

    _actualizar_env({
        "GEMINI_API_KEY": CLAVE_API_GEMINI,
        "GEMINI_MODEL": MODELO_GEMINI,
    })

    genai.configure(api_key=CLAVE_API_GEMINI)
    print(f"[PROVEEDOR IA] Configuración actualizada — Modelo: '{MODELO_GEMINI}'")


def _actualizar_env(valores: dict) -> None:
    """
    Actualiza (o agrega) claves en el .env preservando comentarios y demás
    líneas. Reglas por cada clave:
      - La PRIMERA línea que coincida (activa o comentada) se convierte en la
        línea activa con el nuevo valor.
      - Cualquier coincidencia POSTERIOR (duplicado o comentario viejo) se
        elimina, evitando que el archivo acumule variantes de la misma clave.
      - Si la clave no existe en el archivo, se agrega al final.
    """
    try:
        lineas = ruta_env.read_text(encoding="utf-8").splitlines() if ruta_env.exists() else []
    except OSError:
        lineas = []

    patron_claves = {
        clave: re.compile(rf"^#?\s*{re.escape(clave)}\s*=")
        for clave in valores
    }

    vistas = set()
    nuevas_lineas = []
    for linea in lineas:
        reemplazo = None
        for clave, patron in patron_claves.items():
            if clave not in vistas and patron.match(linea):
                reemplazo = f"{clave}={valores[clave]}"
                vistas.add(clave)
                break
        if reemplazo is not None:
            nuevas_lineas.append(reemplazo)
            continue
        # ¿Es una coincidencia POSTERIOR de una clave ya asignada? (duplicado)
        if any(patron.match(linea) for patron in patron_claves.values()
               for clave in valores if clave in vistas):
            continue  # duplicado/comentario viejo → se descarta
        nuevas_lineas.append(linea)

    # Las claves que no estaban en el archivo se agregan al final
    for clave, valor in valores.items():
        if clave not in vistas:
            nuevas_lineas.append(f"{clave}={valor}")

    ruta_env.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")


def obtener_configuracion_ia() -> dict:
    """Devuelve la configuración vigente leyendo el .env (para precargar el
    formulario con lo que de verdad hay en el archivo)."""
    _sincronizar_globales()
    return {"api_key": CLAVE_API_GEMINI, "modelo": MODELO_GEMINI}


def listar_modelos_disponibles(api_key: str = "") -> list:
    """Devuelve los nombres de los modelos que soportan generateContent."""
    if api_key:
        genai.configure(api_key=api_key.strip())
    nombres = []
    try:
        for m in genai.list_models():
            metodos = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in metodos:
                # m.name viene como 'models/gemini-...'; nos quedamos con el nombre corto
                nombres.append(m.name.split("/")[-1])
    finally:
        # Restaurar la configuración vigente por defecto
        genai.configure(api_key=CLAVE_API_GEMINI)
    return sorted(nombres)


def verificar_conexion_ia():
    """Verifica la conectividad REAL ANTES de empezar a procesar la presentación."""
    try:
        requests.get("https://generativelanguage.googleapis.com", timeout=3)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            "SIN CONEXIÓN A INTERNET: No se puede alcanzar el servidor de Gemini. "
            "Verifica tu Wi-Fi e intenta de nuevo."
        ) from e


def consultar_modelo(prompt: str, system_instruction: str = "") -> str:
    """
    Envía una petición a Gemini.

    NOTA: A partir de gemini-3.5-flash-lite, los parámetros temperature, top_p
    y top_k están deprecados y son ignorados por la API. El determinismo se
    controla mediante system_instruction con reglas explícitas de formato.
    Fuente: Google AI release notes, julio 2026.

    Args:
        prompt: El prompt principal con los datos y las instrucciones de tarea.
        system_instruction: Instrucción de sistema que define el rol y el formato
                            de respuesta. Se procesa ANTES que el prompt y es
                            el mecanismo oficial de determinismo en Gemini 3.x.
    """
    return _consultar_gemini(prompt, system_instruction)

def _consultar_gemini(prompt: str, system_instruction: str) -> str:
    max_reintentos = 3

    for intento in range(max_reintentos):
        try:
            # Reconfigurar con la clave vigente (idempotente): garantiza que
            # la petición use SIEMPRE la configuración actual del .env/panel.
            genai.configure(api_key=CLAVE_API_GEMINI)

            # Si hay system_instruction, se inicializa el modelo con ella.
            if system_instruction:
                modelo = genai.GenerativeModel(
                    MODELO_GEMINI,
                    system_instruction=system_instruction
                )
            else:
                modelo = genai.GenerativeModel(MODELO_GEMINI)

            respuesta = modelo.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(),
                request_options={"retry": None}
            )

            return respuesta.text.strip()

        except Exception as e:
            error_str = str(e)

            # ---------------------------------------------------------
            # 1. Error temporal del servidor Gemini (503)
            # ---------------------------------------------------------
            if "503" in error_str or "unavailable" in error_str.lower():

                if intento < max_reintentos - 1:
                    tiempo_espera = 5 * (2 ** intento)

                    print(
                        f"[GEMINI] Servidor temporalmente no disponible. "
                        f"Reintentando en {tiempo_espera} segundos "
                        f"({intento + 1}/{max_reintentos})..."
                    )

                    import time
                    time.sleep(tiempo_espera)
                    continue

                raise RuntimeError(
                    "ERROR DE SERVIDOR: Gemini no está disponible temporalmente. "
                    "Se realizaron 3 intentos sin éxito. Intenta nuevamente."
                ) from e

            # ---------------------------------------------------------
            # 2. Problemas de conexión
            # ---------------------------------------------------------
            if (
                "Failed to establish" in error_str
                or "unreachable" in error_str
                or "aborted" in error_str
            ):
                raise RuntimeError(
                    "SE PERDIÓ LA CONEXIÓN A INTERNET durante el análisis. "
                    "Verifica tu red."
                ) from e

            # ---------------------------------------------------------
            # 3. Cuota / límite 429
            # ---------------------------------------------------------
            if (
                "Quota" in error_str
                or "429" in error_str
                or "exhausted" in error_str.lower()
            ):
                match_espera = re.search(
                    r"retry in (\d+(?:\.\d+)?)s",
                    error_str
                )

                tiempo_espera = (
                    f"{round(float(match_espera.group(1)))} segundos"
                    if match_espera
                    else "1 minuto"
                )

                tipo_cuota = "Límite general de uso"

                if "TokensPerMinute" in error_str or "TPM" in error_str:
                    tipo_cuota = "Tokens por Minuto (Se renueva en un minuto)"
                elif "PerDay" in error_str:
                    tipo_cuota = "Peticiones Diarias (Se renueva a la medianoche)"
                elif "PerMinute" in error_str:
                    tipo_cuota = "Peticiones por Minuto (Se renueva en un minuto)"

                raise RuntimeError(
                    f"LÍMITE DE CUOTA GEMINI: Se agotó tu cuota de "
                    f"'{tipo_cuota}'. Google solicita esperar exactamente "
                    f"{tiempo_espera} antes de reintentar."
                ) from e

            # ---------------------------------------------------------
            # 4. API Key inválida
            # ---------------------------------------------------------
            if "API_KEY_INVALID" in error_str or "not valid" in error_str:
                raise RuntimeError(
                    "CLAVE INVÁLIDA: La API Key de Gemini no es válida. "
                    "Abre la Configuración de IA (botón ⚙ de la barra superior) "
                    "e ingresa una API Key válida."
                ) from e

            # ---------------------------------------------------------
            # 5. Cualquier otro error
            # ---------------------------------------------------------
            raise RuntimeError(
                f"Error crítico con la IA de Google: {error_str}"
            ) from e

    raise RuntimeError("Gemini no pudo procesar la solicitud.")