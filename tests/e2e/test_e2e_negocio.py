# tests/e2e/test_e2e_negocio.py
"""
Pruebas de integración de negocio y persistencia (sin interfaz gráfica).

Ejercitan el código productivo real (controladores + persistencia + consultas)
sobre una base de datos y un almacenamiento aislados (ver sandbox.py).

Gemini se sustituye por dobles de prueba (fakes.py). PowerPoint/COM se sustituye
por equivalentes locales deterministas. En el informe se distingue entre servicio
simulado y real.
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from tests.e2e import sandbox
from tests.e2e.fakes import ia_simulada, offimatica_simulada

sandbox.bootstrap()

# El código productivo se importa DESPUÉS del bootstrap para que resuelva a la copia.
from app.core.controller.presentation_controller import (  # noqa: E402
    orquestar_proceso_completo,
    orquestar_eliminacion_presentacion,
    orquestar_analisis_ia,
    orquestar_actualizacion_presentacion,
    orquestar_guardado_tiempos,
    orquestar_obtener_reporte_tiempo,
    orquestar_ocultar_presentacion,
    orquestar_mostrar_presentacion,
)
from app.core.controller.subject_controller import orquestar_desactivacion_materia  # noqa: E402
from app.core.logic.text_extractor import contar_diapositivas  # noqa: E402
from app.core.logic.hash_generator import generar_hash_archivo  # noqa: E402
from app.core.logic.file_validator import validar_tamano_archivo  # noqa: E402
from app.data.queries import (  # noqa: E402
    obtener_presentaciones_por_materia,
    obtener_historial_presentacion,
    obtener_id_materia,
    existe_hash_en_db,
)


ID_MATERIA = sandbox.ID_MATERIA
NOMBRE_MATERIA = sandbox.NOMBRE_MATERIA


def _contar(tabla: str, where: str = "", args=()) -> int:
    conn = sandbox.conectar()
    try:
        sql = f"SELECT COUNT(*) FROM {tabla}"
        if where:
            sql += f" WHERE {where}"
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


class BaseE2E(unittest.TestCase):
    def setUp(self):
        sandbox.reset_db()
        self._tmp = sandbox.raiz() / "origenes"
        if self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
        self._tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._borrar_tmp)

    def _borrar_tmp(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _cargar(self, nombre="prueba.pptx", n=4):
        ruta = sandbox.crear_pptx(self._tmp / nombre, n_slides=n)
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(ruta), ID_MATERIA)
        self.assertTrue(exito, msj)
        return str(ruta)

    def _analizar(self):
        fila = obtener_presentaciones_por_materia(ID_MATERIA)[0]
        nombre, ruta_pptx = fila[0], fila[1]
        with ia_simulada():
            exito, contenido = orquestar_analisis_ia(ruta_pptx, nombre, ID_MATERIA)
        self.assertTrue(exito, contenido if not exito else "")
        return nombre, ruta_pptx, contenido


class CargaYVersionadoE2E(BaseE2E):
    def test_pcv_carga_persistencia(self):
        """N-01 (HP-01): carga válida registra Presentacion, v1 y archivos físicos."""
        ruta = self._cargar()
        self.assertEqual(_contar("Presentacion"), 1)
        self.assertEqual(_contar("Historial_de_Versiones", "numero_version=1"), 1)
        self.assertTrue(existe_hash_en_db(generar_hash_archivo(ruta)))
        filas = obtener_presentaciones_por_materia(ID_MATERIA)
        self.assertEqual(len(filas), 1)
        _nombre, ruta_pptx, ruta_thumb, analisis, ruta_pdf = filas[0]
        self.assertTrue(Path(ruta_pptx).exists(), "El .pptx copiado debe existir")
        self.assertTrue(Path(ruta_thumb).exists(), "La miniatura debe existir")
        self.assertTrue(Path(ruta_pdf).exists(), "La copia PDF debe existir")
        self.assertEqual(analisis, 0)

    def test_pcv_validacion_tamano(self):
        """N-02: archivo > 30 MB se rechaza antes de registrar nada."""
        pesado = sandbox.crear_archivo_pesado(self._tmp / "pesado.pptx", mb=31)
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(pesado), ID_MATERIA)
        self.assertFalse(exito)
        self.assertIn("demasiado pesado", msj)
        self.assertEqual(_contar("Presentacion"), 0)

    def test_pcv_pptx_corrupto_o_vacio(self):
        """N-03: .pptx ilegible se rechaza sin registrar y sin excepción."""
        corrupto = self._tmp / "corrupto.pptx"
        corrupto.write_bytes(b"esto no es un pptx")
        self.assertEqual(contar_diapositivas(str(corrupto)), 0)
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(corrupto), ID_MATERIA)
        self.assertFalse(exito)
        self.assertIn("No se pudo leer", msj)
        self.assertEqual(_contar("Presentacion"), 0)

    def test_uhp04_duplicado_misma_materia(self):
        """UHP-04: carga duplicada por hash se rechaza y no crea registros."""
        ruta = self._cargar()
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(ruta), ID_MATERIA)
        self.assertFalse(exito)
        self.assertIn("ya ha sido procesada", msj)
        self.assertEqual(_contar("Presentacion"), 1)
        self.assertEqual(_contar("Historial_de_Versiones"), 1)

    def test_uhp04_duplicado_entre_materias(self):
        """AÑADIDO: el hash es global; el duplicado se bloquea también en otra materia."""
        ruta = self._cargar()
        conn = sandbox.conectar()
        try:
            conn.execute(
                "INSERT INTO Unidad_de_Aprendizaje VALUES (?, ?, ?)",
                ("ua-prueba-0002", "Otra Materia", 1),
            )
            conn.commit()
        finally:
            conn.close()
        id_otra = "ua-prueba-0002"
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(ruta), id_otra)
        self.assertFalse(exito)
        self.assertIn("ya ha sido procesada", msj)
        self.assertEqual(_contar("Presentacion", "id_unidad_aprendizaje=?", (id_otra,)), 0)

    def test_hp02_versionado(self):
        """HP-02: actualizar con un archivo distinto crea v2 sin alterar v1."""
        self._cargar()
        nombre = "prueba.pptx"
        ruta_v2 = sandbox.crear_pptx(self._tmp / "prueba_v2.pptx", n_slides=6, titulo="Versión mejorada")
        with offimatica_simulada():
            exito, msj = orquestar_actualizacion_presentacion(str(ruta_v2), nombre, ID_MATERIA)
        self.assertTrue(exito, msj)
        self.assertEqual(_contar("Presentacion"), 1, "No debe duplicar la Presentacion")
        self.assertEqual(_contar("Historial_de_Versiones"), 2)
        historial = obtener_historial_presentacion(nombre, ID_MATERIA)
        versiones = {f[1]: f for f in historial}
        self.assertIn(1, versiones)
        self.assertIn(2, versiones)
        self.assertEqual(versiones[1][3], 4)
        self.assertEqual(versiones[2][3], 6)
        self.assertEqual(versiones[2][4], 0, "v2 debe iniciar sin análisis")

        # Actualizar con el mismo archivo que v2 -> rechazado
        with offimatica_simulada():
            exito2, msj2 = orquestar_actualizacion_presentacion(str(ruta_v2), nombre, ID_MATERIA)
        self.assertFalse(exito2)
        self.assertIn("idéntico", msj2)
        self.assertEqual(_contar("Historial_de_Versiones"), 2)

    def test_ocultar_restaurar(self):
        """RF-01.7: ocultar y restaurar conserva datos y archivos."""
        self._cargar()
        nombre = "prueba.pptx"
        self.assertTrue(orquestar_ocultar_presentacion(nombre, ID_MATERIA))
        self.assertEqual(len(obtener_presentaciones_por_materia(ID_MATERIA)), 0)
        self.assertEqual(_contar("Presentacion", "visible=0"), 1)
        self.assertTrue(orquestar_mostrar_presentacion(nombre, ID_MATERIA))
        self.assertEqual(len(obtener_presentaciones_por_materia(ID_MATERIA)), 1)


class AnalisisYReporteE2E(BaseE2E):
    def test_hp01_analisis_persistencia(self):
        """HP-01: análisis simulado persiste JSON en BD y en disco y marca la versión."""
        self._cargar()
        nombre, ruta_pptx, contenido = self._analizar()
        self.assertIn("score_global_presentacion", contenido)
        self.assertEqual(_contar("Analisis"), 1)
        conn = sandbox.conectar()
        try:
            analisis, score = conn.execute(
                "SELECT analisis, calificacion_presentacion FROM Historial_de_Versiones"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(analisis, 1)
        self.assertIsNotNone(score)
        ruta_json = Path(ruta_pptx).with_name(Path(ruta_pptx).stem + "_analysis.json")
        self.assertTrue(ruta_json.exists(), "Debe escribirse el JSON de análisis en disco")

    def test_uhp07_fallo_gemini_no_deja_parciales(self):
        """UHP-07: si la IA falla, el análisis se cancela sin resultados parciales."""
        self._cargar()
        fila = obtener_presentaciones_por_materia(ID_MATERIA)[0]
        nombre, ruta_pptx = fila[0], fila[1]
        with ia_simulada(conectada=False):
            exito, msj = orquestar_analisis_ia(ruta_pptx, nombre, ID_MATERIA)
        self.assertFalse(exito)
        self.assertIn("SIN CONEXIÓN", msj)
        self.assertEqual(_contar("Analisis"), 0, "No debe haber análisis parcial")
        conn = sandbox.conectar()
        try:
            analisis = conn.execute("SELECT analisis FROM Historial_de_Versiones").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(analisis, 0)
        ruta_json = Path(ruta_pptx).with_name(Path(ruta_pptx).stem + "_analysis.json")
        self.assertFalse(ruta_json.exists())

    def test_reporte_tiempos_persistencia(self):
        """N-06: el reporte de tiempos se guarda y recupera desde la versión."""
        self._cargar()
        nombre = "prueba.pptx"
        reporte = {
            "archivo": nombre,
            "grupos": {
                "3CM2": {
                    "ultima_diapositiva": 3,
                    "tiempo_total_seg": 45,
                    "tiempos_por_slide": {"1": 15, "2": 20, "3": 10},
                    "historial_sesiones": {
                        "1": {"planeado_seg": 3600, "duracion_seg": 45,
                              "tiempos_slide": {"1": 15, "2": 20, "3": 10}}
                    },
                }
            },
        }
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(reporte)))
        recuperado = json.loads(orquestar_obtener_reporte_tiempo(nombre, ID_MATERIA))
        self.assertEqual(recuperado["grupos"]["3CM2"]["tiempo_total_seg"], 45)

    def test_metricas_locales_reales(self):
        """N-10: las métricas locales (ICD/WPS) se calculan sobre un PPTX real."""
        from app.core.controller.analyzer_controller import _ejecutar_metricas_locales
        from app.core.logic.text_extractor import extraer_datos_pptx
        ruta = self._cargar()
        datos = extraer_datos_pptx(ruta)
        res = _ejecutar_metricas_locales(datos["slides"])
        self.assertIn("icd", res)
        self.assertIn("wps", res)
        self.assertEqual(len(res["icd"]["resultados"]), 4)


class EliminacionE2E(BaseE2E):
    def test_eliminacion_presentacion_cascada(self):
        """RF-01.7: eliminar presentación borra versiones, análisis y archivos."""
        self._cargar()
        self._analizar()
        fila = obtener_presentaciones_por_materia(ID_MATERIA)[0]
        nombre, ruta_pptx, ruta_thumb, _a, ruta_pdf = fila
        self.assertTrue(orquestar_eliminacion_presentacion(nombre, ID_MATERIA))
        self.assertEqual(_contar("Presentacion"), 0)
        self.assertEqual(_contar("Historial_de_Versiones"), 0)
        self.assertEqual(_contar("Analisis"), 0)
        self.assertFalse(Path(ruta_pptx).exists())
        self.assertFalse(Path(ruta_thumb).exists())
        self.assertFalse(Path(ruta_pdf).exists())

    def test_uhp06_eliminacion_materia_cascada(self):
        """UHP-06: eliminar materia con datos deja 0 registros operativos y conserva el catálogo."""
        self._cargar()
        self._analizar()
        exito, msj = orquestar_desactivacion_materia(NOMBRE_MATERIA)
        self.assertTrue(exito, msj)
        self.assertEqual(_contar("Presentacion"), 0)
        self.assertEqual(_contar("Historial_de_Versiones"), 0)
        self.assertEqual(_contar("Analisis"), 0)
        # El catálogo institucional se conserva.
        self.assertGreater(_contar("Unidad"), 0)
        self.assertGreater(_contar("Temas"), 0)
        self.assertGreater(_contar("Subtema"), 0)

    @unittest.expectedFailure
    def test_uhp06b_eliminacion_materia_con_presentacion_subtema(self):
        """
        INT: con una fila en Presentacion_Subtema, el borrado de Presentacion falla
        porque la FK no declara ON DELETE CASCADE. Se documenta como defecto latente.

        Se marca como fallo esperado mientras el defecto exista.
        """
        self._cargar()
        conn = sandbox.conectar()
        try:
            id_pres = conn.execute("SELECT id_presentacion FROM Presentacion").fetchone()[0]
            id_subtema = conn.execute("SELECT id_subtema FROM Subtema").fetchone()[0]
            conn.execute("INSERT INTO Presentacion_Subtema VALUES (?, ?)", (id_pres, id_subtema))
            conn.commit()
        finally:
            conn.close()
        exito, msj = orquestar_desactivacion_materia(NOMBRE_MATERIA)
        # Comportamiento deseado (no observado hoy): borrado completo sin huérfanos.
        self.assertTrue(exito, f"Borrado falló con datos relacionados: {msj}")
        self.assertEqual(_contar("Presentacion_Subtema"), 0)

    # Documentamos la observación real del defecto en un test que sí pasa hoy.
    def test_uhp06b_observacion_defecto_fk(self):
        """Observa y registra el fallo actual cuando Presentacion_Subtema tiene filas."""
        self._cargar()
        conn = sandbox.conectar()
        try:
            id_pres = conn.execute("SELECT id_presentacion FROM Presentacion").fetchone()[0]
            id_subtema = conn.execute("SELECT id_subtema FROM Subtema").fetchone()[0]
            conn.execute("INSERT INTO Presentacion_Subtema VALUES (?, ?)", (id_pres, id_subtema))
            conn.commit()
        finally:
            conn.close()
        exito, msj = orquestar_desactivacion_materia(NOMBRE_MATERIA)
        # Evidencia del estado actual (defecto): el borrado no se completa.
        self.assertFalse(exito, "Si el borrado ya funciona, retirar esta observación.")
        self.assertEqual(_contar("Presentacion"), 1, "La Presentacion permanece por la FK sin CASCADE")
        self.assertEqual(_contar("Presentacion_Subtema"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
