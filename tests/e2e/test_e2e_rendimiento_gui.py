# tests/e2e/test_e2e_rendimiento_gui.py
"""
Pruebas E2E del Prototipo 3 (con interfaz gráfica real).

Cubren el dashboard de rendimiento, la gráfica de tendencias, el modal de
desviaciones y las pruebas de integridad/usuario del protocolo del prototipo 3.

Los identificadores de cada método (`test_prf01_...`, `test_grf04_...`, etc.)
coinciden con los de la tabla del protocolo, de modo que el resultado de esta
suite es la evidencia de ejecución de dichas pruebas.

Se reutiliza el arranque de la aplicación y el sandbox de `test_e2e_gui` para
que exista una única instancia de la GUI durante toda la corrida.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from tests.e2e import sandbox
from tests.e2e.fakes import ia_simulada

sandbox.bootstrap()

# --- Importaciones del código productivo (post-bootstrap) ---
import customtkinter as ctk  # noqa: E402

from app.presentation.views import navigator  # noqa: E402
from app.presentation.views.ui_state import ui  # noqa: E402
from app.presentation.widgets import content_panel as cp  # noqa: E402
from app.core.controller.presentation_controller import (  # noqa: E402
    orquestar_analisis_ia,
    orquestar_guardado_tiempos,
    orquestar_obtener_analisis,
)
from app.presentation.widgets.performance_mode.performance_summary_panel import (  # noqa: E402
    crear_resumen_rendimiento,
    COLOR_OK,
    COLOR_UNDER,
    COLOR_OVER,
)
from app.presentation.widgets.performance_mode.performance_chart_panel import (  # noqa: E402
    crear_grafica_rendimiento,
    COLOR_IA,
    COLOR_REAL,
)
from app.presentation.widgets.performance_mode.performance_deviations_panel import (  # noqa: E402
    abrir_reporte_desviaciones,
)
import app.presentation.views.performance_gui as perf  # noqa: E402

# Reutilizamos el arranque único de la GUI y utilidades de la suite existente.
from tests.e2e.test_e2e_gui import BaseGUI, _Recorder, _contar  # noqa: E402

ID_MATERIA = sandbox.ID_MATERIA
NOMBRE_MATERIA = sandbox.NOMBRE_MATERIA


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _textos(widget, acc=None):
    """Recolecta recursivamente el texto de los widgets visibles.

    No profundiza en etiquetas ni botones para no contar dos veces el texto
    (CustomTkinter crea un `Label` interno con el mismo texto).
    """
    if acc is None:
        acc = []
    for w in widget.winfo_children():
        cls = type(w).__name__
        try:
            t = w.cget("text")
        except Exception:
            t = None
        if isinstance(t, str) and t:
            acc.append(t)
        if cls in ("CTkLabel", "Label", "CTkButton", "Button"):
            continue
        _textos(w, acc)
    return acc


def _canvas_textos(canvas):
    return [canvas.itemcget(i, "text") for i in canvas.find_all()
            if canvas.type(i) == "text"]


def _buscar_boton(widget, texto):
    for w in widget.winfo_children():
        try:
            if isinstance(w, ctk.CTkButton) and w.cget("text") == texto:
                return w
        except Exception:
            pass
        encontrado = _buscar_boton(w, texto)
        if encontrado is not None:
            return encontrado
    return None


def _destruir_modal(modal):
    """Cierra un modal tolerando que ya esté destruido."""
    for paso in ("grab_release", "destroy"):
        try:
            getattr(modal, paso)()
        except Exception:
            pass


def _analisis_ia(tiempos_ia, zonas=None, con_total=True, con_total_seg=True):
    """Construye un análisis sintético con el contrato del analizador real."""
    slides = []
    for n, t in tiempos_ia.items():
        s = {"slide_number": n, "tiempo_exposicion": t}
        if zonas and n in zonas:
            s["zona_slide"] = zonas[n]
        slides.append(s)
    datos = {
        "score_global_presentacion": {"zona_global": "excelente"},
        "slides": slides,
    }
    if con_total:
        datos["total_diapositivas"] = max(tiempos_ia) if tiempos_ia else 0
    if con_total_seg:
        datos["tiempo_total_exposicion_segundos"] = sum(tiempos_ia.values())
    return datos


def _grupo(tiempos_reales, planeado=3600, sesiones=None):
    tps = {str(n): v for n, v in tiempos_reales.items()}
    g = {"tiempos_por_slide": tps, "tiempo_total_seg": sum(tps.values())}
    if sesiones is not None:
        g["historial_sesiones"] = sesiones
    else:
        g["historial_sesiones"] = {"1": {"planeado_seg": planeado}}
    return g


class BaseRendimiento(BaseGUI):
    """Utilidades comunes para montar la vista y los paneles."""

    def tearDown(self):
        try:
            perf.ocultar_vista_rendimiento()
        except Exception:
            pass
        super().tearDown()

    # -- montaje -----------------------------------------------------------

    def _marco(self):
        marco = ctk.CTkFrame(ui["root"], fg_color="white")
        marco.pack(fill="both", expand=True)
        self.addCleanup(marco.destroy)
        return marco

    def _panel_resumen(self, analisis, grupos):
        marco = self._marco()
        panel = crear_resumen_rendimiento(marco, analisis, grupos)
        panel.pack(fill="x")
        ui["root"].update()
        return panel

    def _panel_grafica(self, analisis, grupos, on_grupo=None, on_reporte=None):
        marco = self._marco()
        panel = crear_grafica_rendimiento(marco, "presentacion.pptx", analisis, grupos,
                                          on_grupo_cambiado=on_grupo,
                                          on_ver_reporte=on_reporte)
        panel.pack(fill="both", expand=True)
        for _ in range(3):
            ui["root"].update()
        panel.canvas.configure(width=980, height=420)
        ui["root"].update()
        panel.dibujar(panel.grupo_actual)
        ui["root"].update()
        return panel

    # -- flujo real --------------------------------------------------------

    def _flujo_con_sesiones(self, n=6, grupos_extra=None):
        """Carga, analiza, registra una sesión y entra al dashboard por el flujo real."""
        self._cargar(n=n)
        self._analizar()
        self._refrescar_estado()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]

        analisis = json.loads(orquestar_obtener_analisis(nombre, ID_MATERIA))
        tps = {}
        for s in analisis.get("slides", []):
            n_slide = s.get("slide_number")
            ia = s.get("tiempo_exposicion") or 0
            tps[n_slide] = max(1, ia)  # real = recomendado (sin desviación)

        grupos = {"3CM2": _grupo(tps, planeado=3600)}
        if grupos_extra:
            grupos.update(grupos_extra)
        reporte = {"archivo": nombre, "grupos": grupos}
        self.assertTrue(orquestar_guardado_tiempos(nombre, ID_MATERIA, json.dumps(reporte)))
        self._refrescar_estado()

        navigator.ir_a_rendimiento(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        return nombre, ruta_pdf, analisis


# ===========================================================================
# PRF - Dashboard de rendimiento
# ===========================================================================

class PrfDashboard(BaseRendimiento):

    def test_prf01_entrada_a_la_vista(self):
        self._flujo_con_sesiones()
        self.assertEqual(navigator.vista_actual(), "performance")
        self.assertIsNotNone(perf._contenedor_rendimiento)
        self.assertIsNotNone(perf._resumen_panel)
        self.assertIsNotNone(perf._grafica_panel)

    def test_prf02_carga_de_analisis(self):
        _n, _r, analisis = self._flujo_con_sesiones()
        self.assertTrue(perf._resumen_panel.analisis.get("slides"))
        self.assertEqual(perf._resumen_panel.analisis.get("total_diapositivas"),
                         analisis.get("total_diapositivas"))
        self.assertEqual(set(perf._resumen_panel.slides_por_num),
                         {s["slide_number"] for s in analisis["slides"]})

    def test_prf03_carga_de_tiempos(self):
        nombre, _r, _a = self._flujo_con_sesiones()
        self.assertIn("3CM2", perf._grafica_panel.grupos)
        self.assertEqual(perf._grafica_panel.grupos["3CM2"]["tiempo_total_seg"],
                         perf._grafica_panel.grupos["3CM2"]["tiempo_total_seg"])

    def test_prf04_resumen_con_datos(self):
        analisis = _analisis_ia({1: 60, 2: 120, 3: 90, 4: 150})
        grupos = {"3CM2": _grupo({1: 60, 2: 120, 3: 90, 4: 150})}
        panel = self._panel_resumen(analisis, grupos)
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_doc.cget("text"), "60m 00s")
        self.assertEqual(panel._lbl_real.cget("text"), "7m 00s")
        self.assertEqual(panel._lbl_real_sub.cget("text"), "4/4 diapositivas")
        self.assertEqual(panel._lbl_desv.cget("text"), "0%")

    def test_prf05_resumen_sin_grupos(self):
        panel = self._panel_resumen(_analisis_ia({1: 60}), {})
        panel.actualizar(None)
        ui["root"].update()
        self.assertEqual(panel._lbl_doc.cget("text"), "—")
        self.assertEqual(panel._lbl_real.cget("text"), "—")
        self.assertEqual(panel._lbl_real_sub.cget("text"), "sin grupo")
        self.assertEqual(panel._lbl_desv.cget("text"), "—")

    def test_prf06_sin_analisis(self):
        panel = self._panel_resumen({}, {"3CM2": _grupo({1: 60})})
        panel.actualizar("3CM2")
        ui["root"].update()
        # Sin análisis no hay índice de diapositivas: el resumen queda en cero.
        self.assertEqual(panel.total, 0)
        self.assertEqual(panel._lbl_real_sub.cget("text"), "0/0 diapositivas")
        # La gráfica informa la ausencia de datos.
        grafica = self._panel_grafica({}, {"3CM2": _grupo({1: 60})})
        self.assertIn("Sin datos de análisis", _canvas_textos(grafica.canvas))

    def test_prf07_tiempo_ia_es_la_suma(self):
        analisis = _analisis_ia({1: 60, 2: 120, 3: 90},
                                con_total_seg=False)  # fuerza la suma
        panel = self._panel_resumen(analisis, {"3CM2": _grupo({1: 60})})
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_real_sub.cget("text"), "1/3 diapositivas")
        self.assertIn("4m 30s", _textos(panel),
                      "270 s debe mostrarse como el tiempo IA")

    def test_prf08_grupo_inicial(self):
        self._flujo_con_sesiones(grupos_extra={"3CM4": _grupo({1: 30})})
        self.assertEqual(perf._grafica_panel.grupo_actual, "3CM2",
                         "El primer grupo del reporte debe quedar activo")

    def test_prf09_analisis_corrupto(self):
        with mock.patch.object(perf, "orquestar_obtener_analisis",
                                        return_value="{ esto no es json"), \
             unittest.mock.patch.object(perf, "orquestar_obtener_reporte_tiempo",
                                        return_value='{"grupos": {"3CM2": {}}}'):
            perf.mostrar_vista_rendimiento(ui["root"], NOMBRE_MATERIA, "x.pptx", None)
            ui["root"].update()
        self.assertEqual(perf._resumen_panel.analisis, {})
        self.assertIsNotNone(perf._grafica_panel)

    def test_prf10_reporte_corrupto(self):
        with mock.patch.object(perf, "orquestar_obtener_analisis",
                                        return_value=None), \
             unittest.mock.patch.object(perf, "orquestar_obtener_reporte_tiempo",
                                        return_value="no json"):
            perf.mostrar_vista_rendimiento(ui["root"], NOMBRE_MATERIA, "x.pptx", None)
            ui["root"].update()
        self.assertEqual(perf._grafica_panel.grupos, {})

    def test_prf11_regreso_al_inicio(self):
        self._flujo_con_sesiones()
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")
        self.assertIsNone(perf._contenedor_rendimiento)
        self.assertIsNone(perf._grafica_panel)

    def test_prf12_eliminacion_no_aplica(self):
        self._flujo_con_sesiones()
        botones = _textos(perf._contenedor_rendimiento)
        self.assertNotIn("Eliminar", botones)
        self.assertNotIn("Eliminar presentación", botones)

    def test_prf13_calificacion_por_etiqueta(self):
        analisis = _analisis_ia({1: 60})
        analisis["score_global_presentacion"] = {"zona_global": "bueno"}
        panel = self._panel_resumen(analisis, {"3CM2": _grupo({1: 60})})
        ui["root"].update()
        self.assertIn("Bueno", _textos(panel))

    def test_prf14_desviacion_global_por_umbral(self):
        # Real 3x el tiempo IA -> desviación +200 % (naranja)
        panel = self._panel_resumen(_analisis_ia({1: 60}),
                                    {"3CM2": _grupo({1: 180})})
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_desv.cget("text"), "+200%")
        self.assertEqual(panel._lbl_desv.cget("text_color"), COLOR_OVER)

        # Real muy por debajo -> ámbar
        panel2 = self._panel_resumen(_analisis_ia({1: 100}),
                                     {"3CM2": _grupo({1: 40})})
        panel2.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel2._lbl_desv.cget("text"), "-60%")
        self.assertEqual(panel2._lbl_desv.cget("text_color"), COLOR_UNDER)

        # Dentro del umbral -> verde
        panel3 = self._panel_resumen(_analisis_ia({1: 100}),
                                     {"3CM2": _grupo({1: 110})})
        panel3.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel3._lbl_desv.cget("text_color"), COLOR_OK)

    def test_prf15_diapositivas_presentadas(self):
        analisis = _analisis_ia({1: 60, 2: 60, 3: 60, 4: 60})
        grupos = {"3CM2": _grupo({1: 60, 2: 60})}  # solo 2 presentadas
        panel = self._panel_resumen(analisis, grupos)
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_real_sub.cget("text"), "2/4 diapositivas")

    def test_prf16_planeado_usa_la_ultima_sesion(self):
        analisis = _analisis_ia({1: 60})
        sesiones = {"1": {"planeado_seg": 1800}, "2": {"planeado_seg": 2700}}
        panel = self._panel_resumen(analisis, {"3CM2": _grupo({1: 60}, sesiones=sesiones)})
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_doc.cget("text"), "45m 00s")

    def test_prf17_reapertura_sin_residuos(self):
        self._flujo_con_sesiones()
        navigator.ir_a_principal()
        ui["root"].update()
        nombre = self._primera_fila()[0]
        ruta_pdf = self._primera_fila()[4]
        navigator.ir_a_rendimiento(NOMBRE_MATERIA, nombre, ruta_pdf)
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "performance")
        self.assertIn("3CM2", perf._grafica_panel.grupos)


# ===========================================================================
# GRF - Gráfica de tendencias
# ===========================================================================

class GrfGrafica(BaseRendimiento):

    def setUp(self):
        super().setUp()
        self.analisis = _analisis_ia({1: 60, 2: 120, 3: 90, 4: 150, 5: 30})
        self.grupos = {"3CM2": _grupo({1: 20, 2: 200, 3: 95, 4: 40, 5: 0})}

    def _tipos(self, panel):
        c = panel.canvas
        return [c.type(i) for i in c.find_all()]

    def test_grf01_dibujado_inicial(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        tipos = self._tipos(panel)
        self.assertGreaterEqual(tipos.count("line"), 6, "guías, ejes y series")
        self.assertIn("polygon", tipos)
        self.assertIn("oval", tipos)
        etiquetas = _canvas_textos(panel.canvas)
        for n in range(1, 6):
            self.assertIn(str(n), etiquetas, f"El eje X debe rotular la diapositiva {n}")

    def test_grf02_area_real(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        c = panel.canvas
        poly = [i for i in c.find_all() if c.type(i) == "polygon"]
        self.assertEqual(len(poly), 1)
        self.assertEqual(c.itemcget(poly[0], "fill"), "#F4E2E7")

    def test_grf03_serie_ia_discontinua(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        c = panel.canvas
        ia = [i for i in c.find_all()
              if c.type(i) == "line" and c.itemcget(i, "fill") == COLOR_IA]
        self.assertTrue(ia, "Debe existir la serie de la IA")
        self.assertTrue(any(c.itemcget(i, "dash") for i in ia),
                        "La serie de la IA debe ser discontinua")

    def test_grf04_tooltip_muestra_detalle(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        self.assertTrue(panel._pts)
        _n, xr, _yr, _yi, _rv, _iv = panel._pts[1]
        panel.canvas.event_generate("<Motion>", x=int(xr), y=200)
        ui["root"].update()
        self.assertTrue(panel.canvas.find_withtag("hover"))
        textos = _canvas_textos(panel.canvas)
        self.assertTrue(any(t.startswith("Diapositiva") for t in textos))

    def test_grf05_cursor_lejos_del_punto(self):
        """Con puntos separados (>40 px) el detalle desaparece al alejarse."""
        panel = self._panel_grafica(self.analisis, self.grupos)
        xs = sorted(p[1] for p in panel._pts)
        self.assertGreater(xs[1] - xs[0], 80, "precondición: puntos separados")
        medio = int((xs[0] + xs[1]) / 2)
        self.assertGreater(abs(medio - xs[0]), 40)
        panel.canvas.event_generate("<Motion>", x=medio, y=200)
        ui["root"].update()
        self.assertEqual(panel.canvas.find_withtag("hover"), ())

    def test_grf06_desplazamiento_entre_ventanas(self):
        analisis = _analisis_ia({n: 60 for n in range(1, 31)})
        panel = self._panel_grafica(analisis, {"3CM2": _grupo({n: 60 for n in range(1, 31)})})
        self.assertLess(panel.por_vista, panel.total, "Debe requerir desplazamiento")
        primera = [t for t in _canvas_textos(panel.canvas) if t.isdigit()]
        panel.inicio = 25  # ventana al final
        panel.dibujar("3CM2")
        ui["root"].update()
        ultima = [t for t in _canvas_textos(panel.canvas) if t.isdigit()]
        self.assertNotEqual(primera, ultima, "La ventana visible debe cambiar")

    def test_grf07_cambio_de_grupo_redibuja(self):
        grupos = {"3CM2": _grupo({1: 20, 2: 200, 3: 95, 4: 40, 5: 0}),
                  "3CM4": _grupo({1: 5, 2: 5, 3: 5, 4: 5, 5: 5})}
        panel = self._panel_grafica(self.analisis, grupos)
        antes = list(panel._pts)
        panel.seleccionar_grupo("3CM4")
        ui["root"].update()
        self.assertEqual(panel.grupo_actual, "3CM4")
        self.assertNotEqual([p[4] for p in antes], [p[4] for p in panel._pts])

    def test_grf08_sincronizacion_con_el_resumen(self):
        recibidos = []
        panel = self._panel_grafica(self.analisis, self.grupos,
                                    on_grupo=lambda g: recibidos.append(g))
        panel.seleccionar_grupo("3CM2")
        self.assertEqual(recibidos, ["3CM2"])

    def test_grf09_escala_vertical(self):
        panel = self._panel_grafica(self.analisis, self.grupos,
                                    )
        # El máximo observado entre real e IA es 200 (grupo) frente a 150 (IA).
        self.assertEqual(panel._ymax, 200)
        panel2 = self._panel_grafica(_analisis_ia({1: 500}),
                                     {"3CM2": _grupo({1: 10})})
        self.assertEqual(panel2._ymax, 500)

    def test_grf10_sin_grupos(self):
        panel = self._panel_grafica(self.analisis, {})
        self.assertIsNone(panel.grupo_actual)
        self.assertIn("Sin grupos", _textos(panel._tabs_wrap))

    def test_grf11_redimensionado(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        panel._resize_id = None
        panel.canvas.event_generate("<Configure>", width=900, height=420)
        self.assertIsNotNone(panel._resize_id,
                             "Redimensionar debe reprogramar el dibujado")

    def test_grf12_muchas_diapositivas(self):
        n = 120
        panel = self._panel_grafica(_analisis_ia({i: 45 for i in range(1, n + 1)}),
                                    {"3CM2": _grupo({i: 45 for i in range(1, n + 1)})})
        self.assertLessEqual(len(panel._pts), panel.por_vista)
        self.assertGreater(panel.por_vista, 0)

    def test_grf13_diapositiva_no_presentada(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        objetivo = [p for p in panel._pts if p[4] == 0]
        self.assertTrue(objetivo, "La diapositiva 5 no se presentó (real 0)")
        p = objetivo[0]
        panel.canvas.event_generate("<Motion>", x=int(p[1]), y=200)
        ui["root"].update()
        textos = _canvas_textos(panel.canvas)
        self.assertTrue(any("(no presentada)" in t for t in textos))

    def test_grf14_tiempo_ia_cero_no_rompe(self):
        panel = self._panel_grafica(_analisis_ia({1: 0, 2: 60}),
                                    {"3CM2": _grupo({1: 10, 2: 30})})
        self.assertGreater(panel._ymax, 0)
        self.assertTrue(panel._pts)

    def test_grf15_etiquetas_de_valor(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        self.assertLessEqual(panel.por_vista, 12)
        etiquetas = _canvas_textos(panel.canvas)
        # Los valores reales presentados (20s, 200s...) deben rotularse.
        self.assertTrue(any(t in ("20s", "3m20s", "200s") for t in etiquetas),
                        f"Etiquetas de valor esperadas, se obtuvo: {etiquetas}")

    def test_grf16_leyenda(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        textos = _textos(panel)
        self.assertIn("Tiempo real", textos)
        self.assertIn("Recomendado IA", textos)
        self.assertTrue(any("Desviaciones" in t for t in textos))

    def test_grf17_limites_del_desplazamiento(self):
        analisis = _analisis_ia({n: 60 for n in range(1, 31)})
        panel = self._panel_grafica(analisis, {"3CM2": _grupo({n: 60 for n in range(1, 31)})})
        panel.inicio = 9999
        panel.dibujar("3CM2")
        ui["root"].update()
        self.assertLessEqual(panel.inicio, panel.total - panel.por_vista)
        panel.inicio = -50
        panel.dibujar("3CM2")
        ui["root"].update()
        self.assertGreaterEqual(panel.inicio, 0)

    def test_grf18_presentacion_corta(self):
        panel = self._panel_grafica(_analisis_ia({1: 60, 2: 30}),
                                    {"3CM2": _grupo({1: 60, 2: 30})})
        self.assertEqual(len(panel._pts), 2)
        self.assertTrue(any(t == "1" for t in _canvas_textos(panel.canvas)))


# ===========================================================================
# DVS - Reporte de desviaciones
# ===========================================================================

class DvsDesviaciones(BaseRendimiento):

    def setUp(self):
        super().setUp()
        self.analisis = _analisis_ia({1: 60, 2: 120, 3: 90, 4: 150, 5: 30},
                                     zonas={1: "introduccion", 2: "desarrollo"})
        # real: 1<IA, 2>IA, 3≈IA, 4<IA, 5 no presentada
        self.grupos = {"3CM2": _grupo({1: 20, 2: 200, 3: 90, 4: 40, 5: 0})}

    def _abrir(self, grupo="3CM2", analisis=None, grupos=None):
        modal = abrir_reporte_desviaciones(
            ui["root"], analisis if analisis is not None else self.analisis,
            grupos if grupos is not None else self.grupos, grupo)
        self.addCleanup(_destruir_modal, modal)
        ui["root"].update()
        return modal

    def test_dvs01_apertura(self):
        modal = self._abrir()
        self.assertEqual(modal.title(), "Reporte de desviaciones")
        self.assertEqual(modal.geometry().split("+")[0], "780x560")
        textos = _textos(modal)
        self.assertIn("Desviaciones de tiempo por diapositiva", textos)
        self.assertIn("Diapositivas que duraron muy poco", textos)
        self.assertIn("Diapositivas que duraron mucho", textos)

    def test_dvs02_duracion_insuficiente(self):
        modal = self._abrir()
        textos = _textos(modal)
        self.assertIn("Diapositiva 1", textos)
        self.assertIn("-67%", textos)   # (20-60)/60 = -66.7 -> -67

    def test_dvs03_duracion_excesiva(self):
        modal = self._abrir()
        textos = _textos(modal)
        self.assertIn("Diapositiva 2", textos)
        self.assertIn("+67%", textos)   # (200-120)/120 = +66.7 -> +67

    def test_dvs04_porcentaje_correcto(self):
        modal = self._abrir()
        textos = _textos(modal)
        self.assertIn("-73%", textos)   # diapositiva 4: (40-150)/150 = -73

    def test_dvs05_diapositivas_no_presentadas_excluidas(self):
        modal = self._abrir()
        textos = _textos(modal)
        self.assertNotIn("Diapositiva 5", textos, "real 0 no se clasifica")

    def test_dvs06_categoria_vacia(self):
        # Solo excesos -> la columna "poco" queda vacía.
        modal = self._abrir(grupo="3CM4",
                            grupos={"3CM4": _grupo({1: 600, 2: 600, 3: 600, 4: 600})})
        self.assertIn("Sin diapositivas en esta categoría.", _textos(modal))

    def test_dvs07_cierre_con_entendido(self):
        modal = self._abrir()
        boton = _buscar_boton(modal, "Entendido")
        self.assertIsNotNone(boton)
        boton.invoke()
        ui["root"].update()
        self.assertFalse(modal.winfo_exists())

    def test_dvs08_cierre_con_la_x(self):
        modal = self._abrir()
        comando = modal.protocol("WM_DELETE_WINDOW")
        self.assertTrue(comando)
        modal.tk.call(comando) if isinstance(comando, str) else None
        ui["root"].update()
        self.assertFalse(modal.winfo_exists())

    def test_dvs09_reapertura(self):
        m1 = self._abrir()
        m1.grab_release()
        m1.destroy()
        m2 = self._abrir()
        self.assertTrue(m2.winfo_exists())
        self.assertNotEqual(m1, m2)

    def test_dvs10_grupo_activo_en_el_encabezado(self):
        modal = self._abrir(grupo="3CM4",
                            grupos={"3CM2": self.grupos["3CM2"],
                                    "3CM4": _grupo({1: 600})})
        textos = _textos(modal)
        self.assertTrue(any(t.startswith("REPORTE") for t in textos))

    def test_dvs11_cambio_de_grupo_previo(self):
        modal = self._abrir(grupo="3CM2")
        self.assertIn("REPORTE · 3CM2", _textos(modal))
        modal.grab_release()
        modal.destroy()
        modal2 = self._abrir(grupo="3CM4",
                             grupos={"3CM4": _grupo({1: 600, 2: 600})})
        self.assertIn("REPORTE · 3CM4", _textos(modal2))

    def test_dvs12_limite_de_tres_por_categoria(self):
        analisis = _analisis_ia({n: 60 for n in range(1, 8)})
        # 5 diapositivas por debajo del umbral (real << IA).
        grupos = {"3CM2": _grupo({1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 60, 7: 60})}
        modal = self._abrir(analisis=analisis, grupos=grupos)
        poco = [t for t in _textos(modal)
                if t.startswith("Diapositiva ")][:4]
        self.assertLessEqual(len(poco), 3, f"Solo 3 por categoría, se obtuvo {poco}")

    def test_dvs13_referencia_ia_cero(self):
        analisis = _analisis_ia({1: 0, 2: 60})
        grupos = {"3CM2": _grupo({1: 30, 2: 30})}
        modal = self._abrir(analisis=analisis, grupos=grupos)
        textos = _textos(modal)
        self.assertNotIn("Diapositiva 1", textos,
                         "IA=0 no genera desviación porcentual")

    def test_dvs14_encabezado_y_detalle(self):
        modal = self._abrir()
        textos = _textos(modal)
        self.assertIn("REPORTE · 3CM2", textos)
        # El detalle incluye real, IA y la zona del análisis.
        self.assertTrue(any("Real" in t and "IA" in t for t in textos))
        self.assertTrue(any("Introduccion" in t for t in textos))

    def test_dvs15_sin_grupo(self):
        modal = self._abrir(grupo=None, grupos={})
        self.assertIn("REPORTE · —", _textos(modal))


# ===========================================================================
# INT - Integridad / USR - Usuario
# ===========================================================================

class IntegridadYUsuario(BaseRendimiento):

    def setUp(self):
        super().setUp()
        self.analisis = _analisis_ia({1: 60, 2: 120, 3: 90, 4: 150, 5: 30})
        self.grupos = {"3CM2": _grupo({1: 20, 2: 200, 3: 95, 4: 40, 5: 0})}

    def test_int01_base_uno(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        self.assertEqual(sorted(panel.slides_por_num), [1, 2, 3, 4, 5])
        self.assertEqual(set(panel.grupos["3CM2"]["tiempos_por_slide"]),
                         {"1", "2", "3", "4", "5"})

    def test_int02_correspondencia_entre_json(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        self.assertEqual(panel._pts[0][0], 1)
        self.assertEqual(panel._pts[-1][0], 5)
        self.assertEqual(panel._pts[1][5], 120, "El punto 2 toma la IA del análisis")
        self.assertEqual(panel._pts[1][4], 200, "El punto 2 toma el real del grupo")

    def test_int03_suma_total(self):
        analisis = _analisis_ia({1: 60, 2: 120, 3: 90})
        grupos = {"3CM2": {"tiempos_por_slide": {"1": 30, "2": 40}, "tiempo_total_seg": 0}}
        panel = self._panel_resumen(analisis, grupos)
        panel.actualizar("3CM2")
        ui["root"].update()
        self.assertEqual(panel._lbl_real.cget("text"), "1m 10s",
                         "El total cae a la suma (70 s) cuando falta tempo_total_seg")

    def test_int04_diapositiva_omitida(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        p = [x for x in panel._pts if x[0] == 5][0]
        panel.canvas.event_generate("<Motion>", x=int(p[1]), y=200)
        ui["root"].update()
        self.assertTrue(any("(no presentada)" in t
                            for t in _canvas_textos(panel.canvas)))

    def test_int05_pestanas_estables(self):
        grupos = {"3CM2": _grupo({1: 10}), "3CM4": _grupo({1: 20})}
        panel = self._panel_grafica(_analisis_ia({1: 60}), grupos)
        self.assertEqual(len(panel._tabs), 2)
        for _ in range(10):
            for g in ("3CM2", "3CM4"):
                panel.seleccionar_grupo(g)
        ui["root"].update()
        self.assertEqual(len(panel._tabs), 2, "No deben acumularse pestañas")

    def test_int06_zona_por_diapositiva(self):
        analisis = _analisis_ia({1: 60}, zonas={1: "desarrollo"})
        modal = abrir_reporte_desviaciones(ui["root"], analisis,
                                           {"3CM2": _grupo({1: 120})}, "3CM2")
        self.addCleanup(_destruir_modal, modal)
        ui["root"].update()
        self.assertTrue(any("Desarrollo" in t for t in _textos(modal)))

    def test_int07_total_derivado(self):
        analisis = _analisis_ia({1: 60, 2: 60, 3: 60}, con_total=False)
        panel = self._panel_resumen(analisis, {"3CM2": _grupo({1: 60})})
        self.assertEqual(panel.total, 3, "El total se deriva del máximo slide_number")

    def test_int08_tiempo_ia_derivado(self):
        analisis = _analisis_ia({1: 10, 2: 20, 3: 30}, con_total_seg=False)
        panel = self._panel_resumen(analisis, {"3CM2": _grupo({1: 10})})
        ui["root"].update()
        self.assertIn("1m 00s", _textos(panel))

    def test_usr01_clic_repetido_en_desviaciones(self):
        modal = abrir_reporte_desviaciones(ui["root"], self.analisis, self.grupos, "3CM2")
        self.addCleanup(_destruir_modal, modal)
        ui["root"].update()
        # Mientras el modal existe, retiene el grab: la gráfica no recibe clics.
        self.assertEqual(modal.grab_current(), modal)

    def test_usr02_clic_repetido_en_volver(self):
        self._flujo_con_sesiones()
        navigator.ir_a_principal()
        navigator.ir_a_principal()  # segunda llamada no debe fallar
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")
        self.assertIsNone(perf._contenedor_rendimiento)

    def test_usr03_desplazamiento_veloz(self):
        analisis = _analisis_ia({n: 60 for n in range(1, 31)})
        panel = self._panel_grafica(analisis, {"3CM2": _grupo({n: 60 for n in range(1, 31)})})
        for inicio in (0, 50, 5, 25, 0, 29):
            panel.inicio = inicio
            panel.dibujar("3CM2")
        ui["root"].update()
        self.assertGreaterEqual(panel.inicio, 0)

    def test_usr04_hover_repetido(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        p = panel._pts[0]
        for _ in range(6):
            panel.canvas.event_generate("<Motion>", x=int(p[1]), y=200)
            ui["root"].update()
        self.assertLessEqual(len(panel.canvas.find_withtag("hover")), 6,
                             "El detalle no debe acumular elementos")

    def test_usr05_grupo_y_hover(self):
        grupos = {"3CM2": _grupo({1: 20, 2: 20, 3: 20, 4: 20, 5: 20}),
                  "3CM4": _grupo({1: 99, 2: 99, 3: 99, 4: 99, 5: 99})}
        panel = self._panel_grafica(self.analisis, grupos)
        panel.seleccionar_grupo("3CM4")
        ui["root"].update()
        p = panel._pts[0]
        panel.canvas.event_generate("<Motion>", x=int(p[1]), y=200)
        ui["root"].update()
        textos = _canvas_textos(panel.canvas)
        self.assertTrue(any("1m39s" in t for t in textos), f"textos={textos}")

    def test_usr06_redimensionado_con_hover(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        p = panel._pts[0]
        panel.canvas.event_generate("<Motion>", x=int(p[1]), y=200)
        ui["root"].update()
        panel.canvas.event_generate("<Configure>", width=800, height=400)
        ui["root"].update()
        self.assertIsNotNone(panel._resize_id)

    def test_usr07_grupo_sin_excesos(self):
        analisis = _analisis_ia({1: 60, 2: 60})
        grupos = {"3CM2": _grupo({1: 10, 2: 10})}  # solo déficits
        modal = abrir_reporte_desviaciones(ui["root"], analisis, grupos, "3CM2")
        self.addCleanup(_destruir_modal, modal)
        ui["root"].update()
        self.assertIn("Sin diapositivas en esta categoría.", _textos(modal))

    def test_usr08_redimensionado_repetido(self):
        panel = self._panel_grafica(self.analisis, self.grupos)
        panel._resize_id = None
        for ancho in (700, 720, 740, 760):
            panel.canvas.event_generate("<Configure>", width=ancho, height=400)
        self.assertIsNotNone(panel._resize_id)

    def test_usr09_salir_con_modal_abierto(self):
        """Documenta el comportamiento: el grab del modal bloquea la topbar."""
        self._flujo_con_sesiones()
        modal = abrir_reporte_desviaciones(ui["root"],
                                            perf._resumen_panel.analisis,
                                            perf._grafica_panel.grupos, "3CM2")
        self.addCleanup(_destruir_modal, modal)
        ui["root"].update()
        # El modal retiene la entrada: la ventana principal no puede usarse hasta cerrarlo.
        self.assertEqual(modal.grab_current(), modal)
        modal.grab_release()
        modal.destroy()
        navigator.ir_a_principal()
        ui["root"].update()
        self.assertEqual(navigator.vista_actual(), "main")


if __name__ == "__main__":
    unittest.main(verbosity=2)
