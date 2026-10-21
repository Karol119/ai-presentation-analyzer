# tests/e2e/run_e2e_real.py
"""
Pruebas E2E contra el SERVICIO REAL de Gemini (sin dobles de IA).

Requiere:
  * Un archivo `.env` en la raiz del repositorio con `GEMINI_API_KEY`
    (y opcionalmente `GEMINI_MODEL`).
  * Conexion a internet.

Aislamiento:
  * Se copia `.env` al sandbox (SOLO LECTURA del original; el original nunca se
    modifica).
  * La base de datos y los archivos usados son los del sandbox temporal; el
    repositorio y la base de datos del usuario no se tocan.
  * PowerPoint/COM SI se simula (no hay Office garantizado), por lo que la
    carga fisica de miniatura/PDF es local; el ANALISIS DE IA es real.

Uso (desde la raiz del repositorio):

    python -m tests.e2e.run_e2e_real
"""

from __future__ import annotations

import datetime
import io
import json
import shutil
import sys
import traceback
from pathlib import Path

from tests.e2e import sandbox

RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIAS = RAIZ / "docs" / "prototipo_final" / "evidencias"

sandbox.bootstrap()

# Copiar .env al sandbox ANTES de importar el codigo productivo.
_env_origen = RAIZ / ".env"
if _env_origen.exists():
    shutil.copyfile(_env_origen, sandbox.raiz() / ".env")

from tests.e2e.fakes import offimatica_simulada  # noqa: E402
from app.infrastructure.ai import llm_provider  # noqa: E402


def _linea(consola, texto=""):
    print(texto)
    consola.append(texto)


def main() -> int:
    carpeta = EVIDENCIAS / (datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_real")
    carpeta.mkdir(parents=True, exist_ok=True)
    consola: list[str] = []

    _linea(consola, "===== PRUEBAS E2E CONTRA SERVICIO REAL (Gemini) =====")
    _linea(consola, f"fecha        : {datetime.datetime.now().isoformat(timespec='seconds')}")
    _linea(consola, f"modelo       : {llm_provider.MODELO_GEMINI}")
    _linea(consola, f"api key      : presente={bool(llm_provider.CLAVE_API_GEMINI)} "
                    f"longitud={len(llm_provider.CLAVE_API_GEMINI)}")
    _linea(consola, "")

    estado = {}

    # R-01: verificar conectividad (funcion real del producto).
    _linea(consola, "--- R-01 verificar_conexion_ia() ---")
    try:
        llm_provider.verificar_conexion_ia()
        estado["R-01"] = "APROBADO"
        _linea(consola, "Resultado: servidor alcanzable (sin excepcion).")
    except Exception as e:
        estado["R-01"] = "FALLIDO"
        _linea(consola, f"Resultado: EXCEPCION {type(e).__name__}: {e}")
    _linea(consola, "")

    # R-02: listar modelos disponibles con la clave real.
    _linea(consola, "--- R-02 listar_modelos_disponibles() ---")
    modelos = []
    try:
        modelos = llm_provider.listar_modelos_disponibles()
        disponible = llm_provider.MODELO_GEMINI in modelos
        estado["R-02"] = "APROBADO" if disponible else "FALLIDO"
        _linea(consola, f"Modelos con generateContent: {len(modelos)}")
        _linea(consola, f"Modelo configurado '{llm_provider.MODELO_GEMINI}' "
                        f"disponible: {disponible}")
        if modelos:
            _linea(consola, "Muestra: " + ", ".join(modelos[:15]))
    except Exception as e:
        estado["R-02"] = "FALLIDO"
        _linea(consola, f"Resultado: EXCEPCION {type(e).__name__}: {e}")
    _linea(consola, "")

    # R-03: generacion minima real.
    _linea(consola, "--- R-03 consultar_modelo() (1 frase) ---")
    try:
        respuesta = llm_provider.consultar_modelo("Responde unicamente con la palabra OK.")
        estado["R-03"] = "APROBADO"
        _linea(consola, f"Respuesta: {respuesta!r}")
    except Exception as e:
        estado["R-03"] = "FALLIDO"
        _linea(consola, f"Resultado: EXCEPCION {type(e).__name__}: {str(e)[:500]}")
    _linea(consola, "")

    # R-04: analisis real de extremo a extremo sobre una presentacion sintetica.
    _linea(consola, "--- R-04 orquestar_analisis_ia() con IA REAL ---")
    from app.core.controller.presentation_controller import (
        orquestar_proceso_completo,
        orquestar_analisis_ia,
    )
    from app.core.controller.subject_controller import obtener_archivos_materia
    try:
        sandbox.reset_db()
        origen = sandbox.raiz() / "real" / "presentacion_real.pptx"
        sandbox.crear_pptx(origen, n_slides=3, titulo="Redes de computadoras")
        with offimatica_simulada():
            exito_carga, msg_carga = orquestar_proceso_completo(str(origen), sandbox.ID_MATERIA)
        _linea(consola, f"Carga (Office simulado): {exito_carga} - {msg_carga}")
        fila = obtener_archivos_materia(sandbox.ID_MATERIA)[0]
        nombre, ruta_pptx = fila[0], fila[1]

        exito, contenido = orquestar_analisis_ia(ruta_pptx, nombre, sandbox.ID_MATERIA)
        if exito:
            estado["R-04"] = "APROBADO"
            data = contenido if isinstance(contenido, dict) else {}
            score = (data.get("score_global_presentacion") or {}).get("score_global")
            conn = sandbox.conectar()
            fila_db = conn.execute(
                "SELECT analisis, calificacion_presentacion, recomendacion_presentacion "
                "FROM Historial_de_Versiones"
            ).fetchone()
            n_analisis = conn.execute("SELECT COUNT(*) FROM Analisis").fetchone()[0]
            conn.close()
            _linea(consola, "Analisis REAL: exito=True")
            _linea(consola, f"score_global_presentacion.score_global: {score}")
            _linea(consola, f"claves del JSON: {sorted(data.keys())[:15]}")
            _linea(consola, f"BD -> analisis={fila_db[0]}, calificacion={fila_db[1]}, "
                            f"zona={fila_db[2]!r}, filas_Analisis={n_analisis}")
        else:
            estado["R-04"] = "FALLIDO"
            _linea(consola, "Analisis REAL: exito=False")
            _linea(consola, f"Mensaje: {str(contenido)[:500]}")
    except Exception as e:
        estado["R-04"] = "FALLIDO"
        _linea(consola, f"EXCEPCION {type(e).__name__}: {str(e)[:500]}")
        _linea(consola, traceback.format_exc())
    _linea(consola, "")

    # R-05: sin conexion / sin clave -> mensaje controlado y sin parciales.
    _linea(consola, "--- R-05 fallo controlado sin resultados parciales ---")
    _linea(consola, "Se evalua que un fallo de la IA no deje resultados parciales.")
    try:
        from app.core.controller.presentation_controller import orquestar_analisis_ia as _an
        # Forzamos el escenario sin conexion sustituyendo la verificacion SOLO aqui.
        from unittest import mock
        import app.core.controller.analyzer_controller as ac
        sandbox.reset_db()
        origen2 = sandbox.raiz() / "real" / "p2.pptx"
        sandbox.crear_pptx(origen2, n_slides=2)
        with offimatica_simulada():
            orquestar_proceso_completo(str(origen2), sandbox.ID_MATERIA)
        f2 = obtener_archivos_materia(sandbox.ID_MATERIA)[0]
        with mock.patch.object(ac, "verificar_conexion_ia",
                               side_effect=RuntimeError("SIN CONEXIÓN A INTERNET: prueba")):
            exito, mensaje = _an(f2[1], f2[0], sandbox.ID_MATERIA)
        conn = sandbox.conectar()
        analisis = conn.execute("SELECT COUNT(*) FROM Analisis").fetchone()[0]
        conn.close()
        ok = (not exito) and analisis == 0
        estado["R-05"] = "APROBADO" if ok else "FALLIDO"
        _linea(consola, f"exito={exito} mensaje={mensaje!r} filas_analisis={analisis}")
    except Exception as e:
        estado["R-05"] = "FALLIDO"
        _linea(consola, f"EXCEPCION {type(e).__name__}: {str(e)[:300]}")
    _linea(consola, "")

    # R-06: verificar_conexion_ia() solo comprueba alcanzabilidad, no credenciales.
    _linea(consola, "--- R-06 validacion de credenciales en verificar_conexion_ia() ---")
    try:
        import google.generativeai as genai
        genai.configure(api_key="CLAVE_INVALIDA_PARA_PRUEBA")
        try:
            llm_provider.verificar_conexion_ia()
            alcanzable = True
            msg = "(sin excepcion)"
        except Exception as e:
            alcanzable = False
            msg = f"{type(e).__name__}: {str(e)[:200]}"
        try:
            llm_provider.consultar_modelo("Di OK")
            genero = True
        except Exception as e:
            genero = False
            err_gen = f"{type(e).__name__}: {str(e)[:200]}"
        estado["R-06_verificacion_pasa_con_clave_invalida"] = alcanzable
        _linea(consola, f"verificar_conexion_ia con clave invalida -> alcanzable={alcanzable} {msg}")
        _linea(consola, f"consultar_modelo con clave invalida -> genero={genero} "
                        f"({'' if genero else err_gen})")
        estado["R-06"] = "OBSERVACION" if alcanzable and not genero else "REVISAR"
    finally:
        genai.configure(api_key=llm_provider.CLAVE_API_GEMINI)
    _linea(consola, "")

    _linea(consola, "===== RESUMEN SERVICIO REAL =====")
    for k, v in estado.items():
        _linea(consola, f"  {k}: {v}")
    _linea(consola, "=================================")

    (carpeta / "real_gemini.txt").write_text("\n".join(consola) + "\n", encoding="utf-8")
    print(f"\nEvidencia real guardada en: {carpeta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
