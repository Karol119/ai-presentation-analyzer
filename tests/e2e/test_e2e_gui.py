# tests/e2e/test_e2e_gui.py
"""
Pruebas E2E con interfaz gráfica real (CustomTkinter).

Se arranca la aplicación con `iniciar_aplicacion()` y se disparan los
callbacks PRODUCTIVOS reales (menu de tarjeta, navegador, paneles). Solo se
sustituyen:

  * `CTk.mainloop`            -> no-op (no se entra al bucle de eventos).
  * `filedialog`              -> devuelve una ruta fija (no hay usuario real).
  * `ejecutar_tarea_asincrona`-> ejecucion sincrona determinista.
  * Gemini / PowerPoint COM   -> dobles de prueba (fakes.py).
  * Modales (`mostrar_modal_*`)-> registradores de llamadas, para poder
    afirmar QUÉ modal y QUÉ texto decidió mostrar el callback.

El renderizado de vistas (historial, análisis, presentación, rendimiento) SÍ es
real: se construyen los widgets y se procesan con `update()`.

Requiere un entorno con display (en Windows, sesión de escritorio). No modifica
la base de datos ni los archivos del usuario: todo ocurre en el sandbox.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from tests.e2e import sandbox
from tests.e2e.fakes import ia_simulada, offimatica_simulada

sandbox.bootstrap()

# --- Importaciones del código productivo (post-bootstrap) ---
import customtkinter as ctk  # noqa: E402
from app.presentation.views import navigator  # noqa: E402
from app.presentation.views.ui_state import ui, estado  # noqa: E402
from app.presentation.views import main_gui as mg  # noqa: E402
from app.presentation.widgets import content_panel as cp  # noqa: E402
from app.core.controller.presentation_controller import (  # noqa: E402
    orquestar_proceso_completo,
    orquestar_analisis_ia,
    orquestar_guardado_tiempos,
)
from app.core.controller.subject_controller import (  # noqa: E402
    obtener_id_materia,
    obtener_archivos_materia,
    obtener_catalogo_materias_activas,
)

ID_MATERIA = sandbox.ID_MATERIA
NOMBRE_MATERIA = sandbox.NOMBRE_MATERIA


# ---------------------------------------------------------------------------
# Utilidades de prueba
# ---------------------------------------------------------------------------

class _Recorder:
    """Registra las llamadas a un doble de modal (para afirmar text/ titulo)."""

    def __init__(self):
        self.llamadas = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))

    @property
    def titulos(self):
        return [a[2] if len(a) > 2 else None for a, _ in self.llamadas]

    @property
    def mensajes(self):
        return [a[1] if len(a) > 1 else None for a, _ in self.llamadas]

    def reiniciar(self):
        self.llamadas.clear()


class _ModalCargandoFalso:
    """Doble del modal de carga: nunca existe de verdad (no bloquea)."""

    def winfo_exists(self):
        return True

    def destroy(self):
        pass


def _contar(tabla: str, where: str = "", args=()) -> int:
    conn = sandbox.conectar()
    try:
        sql = f"SELECT COUNT(*) FROM {tabla}"
        if where:
            sql += f" WHERE {where}"
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


def _leer_uno(sql: str, args=()):
    conn = sandbox.conectar()
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


def _ejecutar_sincrono(target_task, on_finished_callback):
    """Reemplaza al thread_manager: ejecuta y entrega el resultado al callback."""
    resultado = target_task()
    on_finished_callback(resultado)


_APP = {"iniciada": False}


def _asegurar_app():
    """Arranca la aplicación una sola vez para todo el módulo de pruebas.

    Si un módulo anterior ya destruyó la ventana raíz (por ejemplo por su
    `tearDownModule`), la aplicación se vuelve a arrancar.
    """
    if _APP["iniciada"]:
        raiz = ui.get("root")
        try:
            viva = raiz is not None and bool(raiz.winfo_exists())
        except Exception:
            viva = False
        if viva:
            return
        _APP["iniciada"] = False

    sandbox.reset_db()  # las tablas deben existir antes de leer el catálogo
    mainloop_original = ctk.CTk.mainloop
    ctk.CTk.mainloop = lambda self, *a, **k: None
    try:
        mg.iniciar_aplicacion()  # no entra al mainloop gracias al parche
    finally:
        ctk.CTk.mainloop = mainloop_original
    _APP["iniciada"] = True


def tearDownModule():
    """Destruye la ventana raíz al terminar el módulo."""
    try:
        ui["root"].destroy()
    except Exception:
        pass


class BaseGUI(unittest.TestCase):
    """Arranca la GUI una sola vez y reinicia el estado lógico en cada prueba."""

    @classmethod
    def setUpClass(cls):
        _asegurar_app()

    def setUp(self):
        sandbox.reset_db()
        self._origenes = sandbox.raiz() / "origenes"
        shutil.rmtree(self._origenes, ignore_errors=True)
        self._origenes.mkdir(parents=True, exist_ok=True)
        self._limpiar_vistas()
        self._refrescar_estado()

    def tearDown(self):
        self._limpiar_vistas()
        shutil.rmtree(self._origenes, ignore_errors=True)

    # -- helpers ------------------------------------------------------------

    def _limpiar_vistas(self):
        """Devuelve la app a la vista principal y limpia vistas secundarias."""
        estado["bloqueo_ui"] = False
        ui["proyeccion_activa"] = False
        for ocultar in (
            "app.presentation.views.analysis_gui.ocultar_vista_analisis",
            "app.presentation.views.history_gui.ocultar_vista_historial",
            "app.presentation.views.presentation_gui.ocultar_vista_presentacion",
            "app.presentation.views.performance_gui.ocultar_vista_rendimiento",
        ):
            modulo, nombre = ocultar.rsplit(".", 1)
            try:
                import importlib
                getattr(importlib.import_module(modulo), nombre)()
            except Exception:
                pass
        navigator._estado_navegador.update(
            {"vista_actual": "main", "subject": None,
             "nombre_presentacion": None, "ruta_pdf": None}
        )
        try:
            if not ui["body"].winfo_manager():
                ui["body"].pack(fill="both", expand=True)
        except Exception:
            pass

    def _refrescar_estado(self):
        """Recarga el estado lógico desde la BD y reconstruye los paneles."""
        estado["subjects"] = obtener_catalogo_materias_activas()
        estado["subject_files"] = {}
        for s in estado["subjects"]:
            estado["subject_files"][s] = obtener_archivos_materia(obtener_id_materia(s))
        estado["active"] = estado["subjects"][0] if estado["subjects"] else ""
        estado["bloqueo_ui"] = False
        for _n, panel in list(ui.get("panels", {}).items()):
            try:
                panel.destroy()
            except Exception:
                pass
        ui["panels"] = {}
        for s in estado["subjects"]:
            cp.create_panel(s, lambda: None)
        if estado["active"]:
            cp.show_panel(estado["active"])
        ui["root"].update()

    def _cargar(self, nombre=None, n=4):
        if nombre is None:
            self._contador = getattr(self, "_contador", 0) + 1
            nombre = f"prueba_{self._contador}_{id(self) % 10000}.pptx"
        ruta = sandbox.crear_pptx(self._origenes / nombre, n_slides=n)
        with offimatica_simulada():
            exito, msj = orquestar_proceso_completo(str(ruta), ID_MATERIA)
        self.assertTrue(exito, msj)
        return str(ruta)

    def _analizar(self):
        fila = obtener_archivos_materia(ID_MATERIA)[0]
        nombre, ruta_pptx = fila[0], fila[1]
        with ia_simulada():
            exito, contenido = orquestar_analisis_ia(ruta_pptx, nombre, ID_MATERIA)
        self.assertTrue(exito, "" if exito else contenido)
        return nombre, ruta_pptx

    def _primera_fila(self):
        return obtener_archivos_materia(ID_MATERIA)[0]


# ---------------------------------------------------------------------------
# UHP-01: bloqueo del módulo de exposición sin análisis previo
# ---------------------------------------------------------------------------

class ExposicionSinAnalisisGUI(BaseGUI):
    def test_uhp01_presentar_sin_analisis_muestra_modal_y_no_navega(self):
        self._cargar()
        nombre, ruta_pptx, _thumb, analisis, ruta_pdf = self._primera_fila()
        self.assertEqual(analisis, 0, "Precondición: la versión NO está analizada")

        rec_advert = _Recorder()
        rec_nav = _Recorder()
        with mock.patch.object(cp, "mostrar_modal_advertencia", rec_advert), \
             mock.patch.object(navigator, "ir_a_presentacion", rec_nav):
            cp._presentar_clase_ui(NOMBRE_MATERIA, nombre, ruta_pdf, False, lambda v: None)

        self.assertEqual(navigator.vista_actual(), "main", "No debe navegar")
        self.assertEqual(rec_nav.llamadas, [], "El navegador no debe ser invocado")
        self.assertEqual(len(rec_advert.llamadas), 1, "Debe mostrarse exactamente un modal")
        self.assertEqual(rec_advert.titulos[0], "Análisis requerido")
        self.assertIn("primero debes ejecutar el Análisis de IA", rec_advert.mensajes[0])

    def test_uhp01b_presentar_con_analisis_navega(self):
        self._cargar()
        self._analizar()
        self._refrescar_estado()
        nombre, ruta_pptx, _thumb, analisis, ruta_pdf = self._primera_fila()
        self.assertEqual(analisis, 1, "Precondición: la versión está analizada")

        cp._presentar_clase_ui(NOMBRE_MATERIA, nombre, ruta_pdf, True, lambda v: None)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "presentation")
        self.assertEqual(ui["body"].winfo_manager(), "", "El cuerpo principal se oculta")


# ---------------------------------------------------------------------------
# UHP-02: bloqueo del informe de rendimiento sin sesiones
# ---------------------------------------------------------------------------

class RendimientoSinSesionesGUI(BaseGUI):
    def test_uhp02_ver_rendimiento_sin_sesiones_muestra_modal(self):
        self._cargar()
        self._analizar()
        self._refrescar_estado()
        nombre, _ruta, _thumb, _a, ruta_pdf = self._primera_fila()

        rec_advert = _Recorder()
        rec_nav = _Recorder()
        with mock.patch.object(cp, "mostrar_modal_advertencia", rec_advert), \
             mock.patch.object(navigator, "ir_a_rendimiento", rec_nav):
            cp._ver_rendimiento_ui(NOMBRE_MATERIA, ruta_pdf, nombre, lambda v: None)

        self.assertEqual(navigator.vista_actual(), "main")
        self.assertEqual(rec_nav.llamadas, [])
        self.assertEqual(rec_advert.titulos[0], "Sin datos de rendimiento")
        self.assertIn("al menos una vez", rec_advert.mensajes[0])

    def test_uhp02b_ver_rendimiento_con_sesion_navega(self):
        self._cargar()
        self._analizar()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]
        reporte = {
            "archivo": nombre,
            "grupos": {"3CM2": {"ultima_diapositiva": 2, "tiempo_total_seg": 30,
                                "tiempos_por_slide": {"1": 30},
                                "historial_sesiones": {"1": {"planeado_seg": 3600,
                                                              "duracion_seg": 30,
                                                              "tiempos_slide": {"1": 30}}}}},
        }
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(reporte)))
        self._refrescar_estado()

        cp._ver_rendimiento_ui(NOMBRE_MATERIA, ruta_pdf, nombre, lambda v: None)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "performance")


# ---------------------------------------------------------------------------
# UHP-03: bloqueo de navegación durante la proyección activa
# ---------------------------------------------------------------------------

class BloqueoNavegacionGUI(BaseGUI):
    def _poner_en_rendimiento(self):
        self._cargar()
        self._analizar()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]
        navigator.ir_a_rendimiento(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "performance")

    def test_uhp03_proyeccion_activa_bloquea_regreso(self):
        self._poner_en_rendimiento()
        ui["proyeccion_activa"] = True
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "performance",
                         "Con proyección activa NO se debe regresar al panel principal")
        self.assertEqual(ui["body"].winfo_manager(), "",
                         "El cuerpo principal debe seguir oculto")

        # Al desactivar la proyección, el regreso debe funcionar.
        ui["proyeccion_activa"] = False
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")
        self.assertEqual(ui["body"].winfo_manager(), "pack")

    def test_uhp03b_bloqueo_ui_bloquea_regreso(self):
        self._poner_en_rendimiento()
        estado["bloqueo_ui"] = True
        navigator.ir_a_principal()
        self.assertEqual(navigator.vista_actual(), "performance",
                         "Con un proceso en curso NO se debe navegar")
        estado["bloqueo_ui"] = False
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")


# ---------------------------------------------------------------------------
# UHP-04: normalización de duplicado / archivo pesado / fallo silencioso
# ---------------------------------------------------------------------------

class CargaGUI(BaseGUI):
    def _config_pick(self, ruta_devuelta):
        return (
            mock.patch.object(cp.filedialog, "askopenfilename", return_value=str(ruta_devuelta)),
            mock.patch.object(cp, "ejecutar_tarea_asincrona", side_effect=_ejecutar_sincrono),
            mock.patch.object(cp, "mostrar_modal_cargando", lambda *a, **k: _ModalCargandoFalso()),
        )

    def test_uhp04_duplicado_muestra_modal_y_no_registra(self):
        ruta = Path(self._cargar())
        self._refrescar_estado()
        rec_dup = _Recorder()
        rec_adv = _Recorder()
        p1, p2, p3 = self._config_pick(ruta)
        with p1, p2, p3, \
             mock.patch.object(cp, "advertir_presentacion_existente", rec_dup), \
             mock.patch.object(cp, "mostrar_modal_advertencia", rec_adv):
            cp._pick_files(NOMBRE_MATERIA, lambda: None)

        self.assertEqual(len(rec_dup.llamadas), 1, "Debe avisarse del duplicado")
        self.assertIn("ya se encuentra registrada", rec_dup.mensajes[0])
        self.assertEqual(rec_adv.llamadas, [], "No debe usarse el modal genérico")
        self.assertEqual(_contar("Presentacion"), 1, "No debe crear otra presentación")
        self.assertEqual(_contar("Historial_de_Versiones"), 1)
        self.assertFalse(estado["bloqueo_ui"], "El candado debe liberarse")

    def test_uhp04b_archivo_pesado_muestra_modal(self):
        pesado = sandbox.crear_archivo_pesado(self._origenes / "pesado.pptx", mb=31)
        self._refrescar_estado()
        rec_adv = _Recorder()
        p1, p2, p3 = self._config_pick(pesado)
        with p1, p2, p3, mock.patch.object(cp, "mostrar_modal_advertencia", rec_adv):
            cp._pick_files(NOMBRE_MATERIA, lambda: None)

        self.assertEqual(len(rec_adv.llamadas), 1)
        self.assertEqual(rec_adv.titulos[0], "Límite de tamaño excedido")
        self.assertIn("supera el límite de 30MB", rec_adv.mensajes[0])
        self.assertEqual(_contar("Presentacion"), 0)

    def test_defecto_archivo_corrupto_sin_retroalimentacion(self):
        """
        DEFECTO OBSERVADO: un .pptx ilegible no es ni duplicado ni pesado, por lo
        que `_pick_files` no muestra NINGÚN modal. El usuario no recibe aviso.

        Este test documenta el estado actual (no lo corrige).
        """
        corrupto = self._origenes / "corrupto.pptx"
        corrupto.write_bytes(b"no es un pptx")
        self._refrescar_estado()
        rec_adv = _Recorder()
        rec_dup = _Recorder()
        p1, p2, p3 = self._config_pick(corrupto)
        with p1, p2, p3, \
             mock.patch.object(cp, "mostrar_modal_advertencia", rec_adv), \
             mock.patch.object(cp, "advertir_presentacion_existente", rec_dup):
            cp._pick_files(NOMBRE_MATERIA, lambda: None)

        # Evidencia del comportamiento actual: silencio total ante el error.
        self.assertEqual(rec_adv.llamadas, [], "Hoy no hay advertencia al usuario")
        self.assertEqual(rec_dup.llamadas, [])
        self.assertEqual(_contar("Presentacion"), 0, "Correctamente no se registra")
        self.assertFalse(estado["bloqueo_ui"])


# ---------------------------------------------------------------------------
# UHP-05: cierre inesperado durante la exposición (ausencia de autoguardado)
# ---------------------------------------------------------------------------

class CierreInesperadoGUI(BaseGUI):
    def test_uhp05_cierre_abrupto_no_persiste_avance(self):
        self._cargar()
        self._analizar()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]

        # Entramos al modo presentación (render real) y acumulamos avance.
        navigator.ir_a_presentacion(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        import app.presentation.views.presentation_gui as pg
        self.assertIsNotNone(pg._datos_panel, "Debe existir el panel de datos")
        pg._datos_panel.segundos_totales = 7
        pg._datos_panel.indice_slide_actual = 2
        pg._datos_panel.tiempos_por_slide = {0: 3, 1: 2, 2: 2}

        # Referencias para la limpieza de la PRUEBA (no forman parte del flujo).
        visor, contenedor = pg._visor_panel, pg._contenedor_presentacion

        # CIERRE ABRUPTO: la app pierde las referencias SIN ejecutar el guardado.
        pg._contenedor_presentacion = None
        pg._datos_panel = None
        pg._visor_panel = None

        reporte = _contar("Historial_de_Versiones", "reporte_tiempo IS NOT NULL")
        self.assertEqual(reporte, 0,
                         "Sin autoguardado, un cierre abrupto no conserva el avance")

        # Limpieza de la prueba: liberar el handle del PDF para no bloquearlo
        # (el handle queda abierto porque el flujo de cierre de producto no corrió).
        def _liberar():
            for obj, metodo in ((visor, "cerrar_documento"), (visor, "destroy"),
                                (contenedor, "destroy")):
                try:
                    getattr(obj, metodo)()
                except Exception:
                    pass
        self.addCleanup(_liberar)
        _liberar()

    def test_uhp05b_salida_ordenada_si_persiste(self):
        """Contraste: al abandonar la vista ordenadamente, el avance SÍ se guarda."""
        self._cargar()
        self._analizar()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]
        navigator.ir_a_presentacion(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        import app.presentation.views.presentation_gui as pg
        pg._datos_panel.segundos_totales = 7
        pg._datos_panel.indice_slide_actual = 2

        navigator.ir_a_principal()  # dispara generar_reporte_json
        ui["root"].update()
        self.assertEqual(_contar("Historial_de_Versiones", "reporte_tiempo IS NOT NULL"), 1)
        raw = _leer_uno("SELECT reporte_tiempo FROM Historial_de_Versiones")
        self.assertIn("historial_sesiones", raw)


# ---------------------------------------------------------------------------
# HP-01 / HP-03 / HP-05: cadena completa y transiciones de retorno
# ---------------------------------------------------------------------------

class CadenaCompletaGUI(BaseGUI):
    def test_hp01_hp05_cadena_completa_y_regreso(self):
        self._cargar()
        self._analizar()
        self._refrescar_estado()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]

        # 1) análisis
        navigator.ir_a_analisis(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "analysis")

        # 2) regreso al principal (HP-05)
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")
        self.assertEqual(ui["body"].winfo_manager(), "pack")

        # 3) modo presentación (HP-01 / HP-04)
        navigator.ir_a_presentacion(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "presentation")

        # 4) historial
        navigator.ir_a_principal()
        navigator.ir_a_historial(NOMBRE_MATERIA, nombre)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "history")

        # 5) rendimiento tras registrar una sesión
        navigator.ir_a_principal()
        reporte = {"archivo": nombre, "grupos": {"3CM2": {
            "ultima_diapositiva": 3, "tiempo_total_seg": 40,
            "tiempos_por_slide": {"1": 20, "2": 20},
            "historial_sesiones": {"1": {"planeado_seg": 3600, "duracion_seg": 40,
                                         "tiempos_slide": {"1": 20, "2": 20}}}}}}
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(reporte)))
        navigator.ir_a_rendimiento(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "performance")

        # 6) regreso final y reapertura sin estado residual (HP-05)
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")
        self.assertEqual(_contar("Historial_de_Versiones"), 1)
        self.assertEqual(_contar("Analisis"), 1)


# ---------------------------------------------------------------------------
# UHP-08: eliminación de un grupo con historial (lógica de persistencia)
# ---------------------------------------------------------------------------

class EliminacionGrupoGUI(BaseGUI):
    def test_uhp08_eliminacion_grupo_conserva_los_demas(self):
        """
        Reproduce la lógica de persistencia que ejecuta el modal de
        `presentation_gui` al confirmar la eliminación de un grupo: eliminar la
        clave del JSON y volver a guardar. La interacción del modal (Toplevel +
        wait_window) no se automatiza aquí.
        """
        self._cargar()
        self._analizar()
        nombre = self._primera_fila()[0]
        reporte = {"archivo": nombre, "grupos": {
            "3CM2": {"ultima_diapositiva": 4, "historial_sesiones": {"1": {}}},
            "3CM4": {"ultima_diapositiva": 1, "historial_sesiones": {"1": {}}},
        }}
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(reporte)))

        datos = json.loads(_leer_uno("SELECT reporte_tiempo FROM Historial_de_Versiones"))
        del datos["grupos"]["3CM2"]
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(datos)))

        restante = json.loads(_leer_uno("SELECT reporte_tiempo FROM Historial_de_Versiones"))
        self.assertNotIn("3CM2", restante["grupos"])
        self.assertIn("3CM4", restante["grupos"])
        self.assertEqual(restante["grupos"]["3CM4"]["ultima_diapositiva"], 1)


# ---------------------------------------------------------------------------
# HP-03 / HP-04: sesiones, reexposición y grupos independientes
# ---------------------------------------------------------------------------

class SesionesYReexposicionGUI(BaseGUI):
    def _entrar_presentacion(self):
        self._cargar()
        self._analizar()
        self._refrescar_estado()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]
        navigator.ir_a_presentacion(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        import app.presentation.views.presentation_gui as pg
        self.assertIsNotNone(pg._datos_panel)
        return pg, nombre, ruta_pdf

    def test_hp03_acumulacion_de_sesiones_y_reenudo(self):
        """HP-03: dos sesiones del mismo grupo se acumulan y la reexposición reanuda."""
        pg, nombre, ruta_pdf = self._entrar_presentacion()
        panel = pg._datos_panel
        panel.tiempo_estimado_seg = 3600

        # Sesión 1: termina en la diapositiva 3 (índice 2).
        panel.grupo_actual = "3CM2"
        panel.segundos_totales = 20
        panel.indice_slide_actual = 2
        panel.tiempos_por_slide = {0: 10, 1: 10}
        panel.generar_reporte_json()

        # Sesión 2: termina en la diapositiva 4 (índice 3).
        panel._reporte_guardado = False
        panel.segundos_totales = 15
        panel.indice_slide_actual = 3
        panel.tiempos_por_slide = {2: 15}
        panel.generar_reporte_json()

        datos = json.loads(_leer_uno("SELECT reporte_tiempo FROM Historial_de_Versiones"))
        grupo = datos["grupos"]["3CM2"]
        self.assertEqual(len(grupo["historial_sesiones"]), 2, "Dos sesiones acumuladas")
        self.assertEqual(grupo["ultima_diapositiva"], 4, "Guarda el cierre de la 2a sesión")
        self.assertEqual(grupo["tiempo_total_seg"], 35, "El tiempo se acumula")

        # Reexposición: debe reanudar en la diapositiva guardada (índice 3).
        conf = {"grupo": "3CM2", "tiempo": 60, "monitor_idx": 0, "cancelado": False}
        rec = _Recorder()
        with mock.patch.object(pg, "_obtener_configuracion_clase", return_value=conf), \
             mock.patch.object(pg, "_lanzar_proyeccion", rec):
            pg._seleccionar_monitor_y_proyectar(ui["root"], NOMBRE_MATERIA, nombre, ruta_pdf, 0)

        self.assertEqual(pg._visor_panel.pagina_actual, 3, "El visor reanuda en la diapositiva guardada")
        self.assertEqual(rec.llamadas[0][0][2], 3, "Se proyecta desde el índice reanudado")

    def test_hp04_grupos_independientes(self):
        """HP-04: dos grupos mantienen registros de sesión independientes."""
        pg, nombre, _ruta_pdf = self._entrar_presentacion()
        panel = pg._datos_panel
        panel.tiempo_estimado_seg = 3600

        panel.grupo_actual = "3CM2"
        panel.segundos_totales = 30
        panel.indice_slide_actual = 1
        panel.tiempos_por_slide = {0: 30}
        panel.generar_reporte_json()

        panel._reporte_guardado = False
        panel.grupo_actual = "3CM4"
        panel.segundos_totales = 12
        panel.indice_slide_actual = 0
        panel.tiempos_por_slide = {0: 12}
        panel.generar_reporte_json()

        datos = json.loads(_leer_uno("SELECT reporte_tiempo FROM Historial_de_Versiones"))
        self.assertEqual(set(datos["grupos"].keys()), {"3CM2", "3CM4"})
        self.assertEqual(datos["grupos"]["3CM2"]["tiempo_total_seg"], 30)
        self.assertEqual(datos["grupos"]["3CM4"]["tiempo_total_seg"], 12)
        self.assertEqual(len(datos["grupos"]["3CM2"]["historial_sesiones"]), 1)
        self.assertEqual(len(datos["grupos"]["3CM4"]["historial_sesiones"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
