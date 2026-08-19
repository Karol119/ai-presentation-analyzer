# app/presentation/widgets/rendimiento_mode/rendimiento_data_panel.py
"""
Panel de datos de la vista de Rendimiento (contenedor derecho).

Replica la estructura de presentation_data_panel.py (header, scroll central y
footer de navegación con ◀ / entrada / ▶) y añade:
  - Selector de grupo (pills).
  - Análisis de tiempo por slide: Recomendado IA vs Real, desviación, estado,
    barra comparativa, comparativa entre grupos y score de la IA.
  - Botón + modal de "Reporte de desviaciones".

Datos (ambos vienen de la BD por los controladores):
  - Análisis IA       -> orquestar_obtener_analisis      (tabla Analisis.resultado)
      · tiempo_exposicion -> tiempo recomendado por la IA
      · score_slide       -> score del análisis
  - Reporte de tiempos -> orquestar_obtener_reporte_tiempo (Historial_de_Versiones.reporte_tiempo)
      · grupos[g].tiempos_por_slide -> tiempo real por diapositiva (base 1)

La navegación funciona igual que en presentación: este panel guarda la
referencia al visor en panel.visor y el visor le avisa cada cambio de página
mediante on_pagina_cambiada (lo cablea la vista rendimiento_gui).
"""

import json
import customtkinter as ctk

from app.core.controller.presentation_controller import (
    orquestar_obtener_analisis,
    orquestar_obtener_reporte_tiempo,
)
from app.core.controller.subject_controller import obtener_id_materia_controlador

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"
COLOR_OK           = "#1D9E75"
COLOR_UNDER        = "#BA7517"
COLOR_OVER         = "#D85A30"
COLOR_TIEMPO       = "#1E293B"
BG_SECONDARY       = "#F1F5F9"
TXT_SECOND         = "#64748B"
TXT_TERCIARIO      = "#94A3B8"
BORDE              = "#E8ECF2"

# Umbral de desviación a partir del cual se marca déficit/exceso (en %)
UMBRAL_DESV = 20


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------
def _fmt(seg):
    if seg is None:
        return "—"
    seg = int(round(seg))
    if seg < 60:
        return f"{seg}s"
    m, s = divmod(seg, 60)
    return f"{m}m {s:02d}s"


def _dev_pct(real, ref):
    if not ref:
        return 0
    return int(round(((real - ref) / ref) * 100))


def _color_desv(pct):
    if pct < -UMBRAL_DESV:
        return COLOR_UNDER
    if pct > UMBRAL_DESV:
        return COLOR_OVER
    return COLOR_OK


def _badge_estado(pct):
    if pct < -UMBRAL_DESV:
        return ("↓ Poco tiempo", "#854F0B", "#FAEEDA")
    if pct > UMBRAL_DESV:
        return ("↑ Excedió tiempo", "#993C1D", "#FAECE7")
    return ("✓ En rango", "#3B6D11", "#EAF3DE")


def _planeado_grupo(gdata):
    """Tiempo planeado por el docente; en el JSON vive por sesión: tomamos la última."""
    sesiones = gdata.get("historial_sesiones", {}) or {}
    if sesiones:
        try:
            ultima = str(max(int(k) for k in sesiones.keys()))
            return sesiones[ultima].get("planeado_seg", 0)
        except Exception:
            pass
    return gdata.get("planeado_seg", 0)


def _construir_barra(parent, frac_fill, frac_ref, color, alto=22,
                     track_bg=BG_SECONDARY, etiqueta_fill=None):
    """Track con relleno proporcional y línea de referencia (recomendado IA)."""
    track = ctk.CTkFrame(parent, fg_color=track_bg, corner_radius=5, height=alto)
    track.pack_propagate(False)
    frac_fill = max(0.0, min(1.0, frac_fill))
    frac_ref = max(0.0, min(1.0, frac_ref))

    fill = ctk.CTkFrame(track, fg_color=color, corner_radius=5)
    fill.place(relx=0, rely=0, relheight=1.0, relwidth=frac_fill)
    if etiqueta_fill and frac_fill > 0.20:
        ctk.CTkLabel(fill, text=etiqueta_fill, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

    ref = ctk.CTkFrame(track, fg_color=COLOR_GUINDA, corner_radius=1, width=3)
    ref.place(relx=frac_ref, rely=0, relheight=1.0, anchor="n")
    return track


# ---------------------------------------------------------------------------
# Factory del panel de datos (contenedor derecho)
# ---------------------------------------------------------------------------
def crear_panel_rendimiento(master, subject: str, nombre_presentacion: str, ruta_pdf: str,
                            visor_referencia=None, **kwargs):
    panel = ctk.CTkFrame(master, fg_color="white", corner_radius=14, width=336,
                         border_width=1, border_color=BORDE, **kwargs)
    panel.pack_propagate(False)

    # ---- Estado ----
    panel.subject = subject
    panel.nombre_presentacion = nombre_presentacion
    panel.visor = visor_referencia
    panel.indice_slide_actual = 0
    panel.analisis = {}
    panel.slides_por_num = {}
    panel.grupos = {}
    panel.grupo_actual = None
    panel._modal = None
    panel._btn_lock = False

    # ---- Carga de los dos JSON desde la BD ----
    id_materia = obtener_id_materia_controlador(subject)

    raw_a = orquestar_obtener_analisis(nombre_presentacion, id_materia)
    if raw_a:
        try:
            panel.analisis = json.loads(raw_a)
        except Exception as e:
            print(f"[rendimiento_data_panel] Error parseando análisis: {e}")
    for s in panel.analisis.get("slides", []):
        panel.slides_por_num[s.get("slide_number")] = s

    raw_r = orquestar_obtener_reporte_tiempo(nombre_presentacion, id_materia)
    if raw_r:
        try:
            panel.grupos = json.loads(raw_r).get("grupos", {}) or {}
        except Exception as e:
            print(f"[rendimiento_data_panel] Error parseando reporte de tiempos: {e}")

    grupos_keys = list(panel.grupos.keys())
    panel.grupo_actual = grupos_keys[0] if grupos_keys else None

    # ---- Helpers de datos ----
    def _t_ref(slide_n):
        return panel.slides_por_num.get(slide_n, {}).get("tiempo_exposicion", 0) or 0

    def _score(slide_n):
        return panel.slides_por_num.get(slide_n, {}).get("score_slide")

    def _real(grupo, slide_n):
        tps = panel.grupos.get(grupo, {}).get("tiempos_por_slide", {}) or {}
        return tps.get(str(slide_n))

    def _desviaciones(grupo):
        out = []
        tps = panel.grupos.get(grupo, {}).get("tiempos_por_slide", {}) or {}
        for k, v in tps.items():
            try:
                n = int(k)
            except (ValueError, TypeError):
                continue
            if n in panel.slides_por_num:
                ref = _t_ref(n)
                out.append({"n": n, "real": v or 0, "ref": ref, "pct": _dev_pct(v or 0, ref)})
        out.sort(key=lambda d: d["pct"])
        return out

    def _alerta(slide_n):
        if not panel.grupo_actual:
            return None
        devs = _desviaciones(panel.grupo_actual)
        if not devs:
            return None
        real = _real(panel.grupo_actual, slide_n)
        if real is None:
            return None
        pct = _dev_pct(real, _t_ref(slide_n))
        if slide_n == devs[0]["n"] and pct < -15:
            return ("under", "Mayor déficit de tiempo en este grupo")
        if slide_n == devs[-1]["n"] and pct > 15:
            return ("over", "Mayor exceso de tiempo en este grupo")
        return None

    # =======================================================================
    # HEADER
    # =======================================================================
    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(18, 5))
    ctk.CTkLabel(header, text="📈 Rendimiento",
                 font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                 text_color=COLOR_GUINDA).pack(anchor="w")
    ctk.CTkLabel(header, text=panel.analisis.get("archivo", nombre_presentacion),
                 font=ctk.CTkFont(family="Segoe UI", size=10),
                 text_color=TXT_SECOND, wraplength=290, justify="left").pack(anchor="w")

    # =======================================================================
    # SELECTOR DE GRUPO
    # =======================================================================
    grupo_box = ctk.CTkFrame(panel, fg_color="#F8FAFC", corner_radius=10,
                             border_width=1, border_color="#E2E8F0")
    grupo_box.pack(fill="x", padx=16, pady=5)
    ctk.CTkLabel(grupo_box, text="GRUPO", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color="#64748B").pack(anchor="w", padx=10, pady=(8, 2))
    pills_row = ctk.CTkFrame(grupo_box, fg_color="transparent")
    pills_row.pack(fill="x", padx=8, pady=(0, 8))
    panel._pills = {}

    def _seleccionar_grupo(g):
        panel.grupo_actual = g
        for k, b in panel._pills.items():
            act = (k == g)
            b.configure(fg_color=COLOR_GUINDA if act else BG_SECONDARY,
                        text_color="white" if act else TXT_SECOND,
                        border_color=COLOR_GUINDA if act else "#CBD5E1")
        _actualizar_contenido(panel.indice_slide_actual)

    def _construir_pills():
        for w in pills_row.winfo_children():
            w.destroy()
        panel._pills = {}
        if not panel.grupos:
            ctk.CTkLabel(pills_row, text="Sin grupos registrados",
                         font=ctk.CTkFont(size=11, slant="italic"),
                         text_color=TXT_TERCIARIO).pack(anchor="w", padx=2)
            return
        for g in panel.grupos.keys():
            act = (g == panel.grupo_actual)
            b = ctk.CTkButton(pills_row, text=g, height=24, width=0, corner_radius=20,
                              border_width=1,
                              fg_color=COLOR_GUINDA if act else BG_SECONDARY,
                              text_color="white" if act else TXT_SECOND,
                              border_color=COLOR_GUINDA if act else "#CBD5E1",
                              hover_color=COLOR_GUINDA_HOVER if act else "#E2E8F0",
                              font=ctk.CTkFont(size=11, weight="bold"),
                              command=lambda k=g: _seleccionar_grupo(k))
            b.pack(side="left", padx=3, pady=2)
            panel._pills[g] = b

    # =======================================================================
    # SCROLL CENTRAL (análisis por slide)
    # =======================================================================
    scroll_frame = ctk.CTkScrollableFrame(panel, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True, padx=14, pady=5)

    # =======================================================================
    # FOOTER: navegación + reporte
    # =======================================================================
    footer = ctk.CTkFrame(panel, fg_color="#FAFBFD", corner_radius=12,
                          border_width=1, border_color="#F1F5F9")
    footer.pack(fill="x", padx=12, pady=12, side="bottom")

    nav_box = ctk.CTkFrame(footer, fg_color="transparent")
    nav_box.pack(fill="x", padx=10, pady=(10, 5))

    def btn_retroceder_cmd():
        if getattr(panel, "_btn_lock", False):
            return
        if panel.visor:
            panel._btn_lock = True
            panel.visor.retroceder_pagina()
            panel.visor.focus_set()
            panel.after(400, lambda: setattr(panel, "_btn_lock", False))

    def btn_avanzar_cmd():
        if getattr(panel, "_btn_lock", False):
            return
        if panel.visor:
            panel._btn_lock = True
            panel.visor.avanzar_pagina()
            panel.visor.focus_set()
            panel.after(400, lambda: setattr(panel, "_btn_lock", False))

    btn_ant = ctk.CTkButton(nav_box, text="◀", width=35, height=28, fg_color=COLOR_GUINDA,
                            hover_color=COLOR_GUINDA_HOVER, command=btn_retroceder_cmd)
    btn_ant.pack(side="left")

    nav_center = ctk.CTkFrame(nav_box, fg_color="transparent")
    nav_center.pack(side="left", fill="x", expand=True)

    panel.entry_pagina = ctk.CTkEntry(nav_center, width=35, height=26, justify="center",
                                      font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
    panel.entry_pagina.pack(side="left", expand=True, anchor="e", padx=(0, 2))

    panel.label_paginas_total = ctk.CTkLabel(nav_center, text="/ -",
                                             font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                                             text_color="#334155")
    panel.label_paginas_total.pack(side="left", expand=True, anchor="w", padx=(2, 0))

    def saltar_pagina_cmd(event=None):
        if not panel.visor:
            return
        try:
            pag_objetivo = int(panel.entry_pagina.get()) - 1
            total = panel.visor.total_paginas
            if 0 <= pag_objetivo < total:
                panel.visor.pagina_actual = pag_objetivo
                panel.visor.renderizar_slide_actual()
                if hasattr(panel.visor, "on_pagina_cambiada") and panel.visor.on_pagina_cambiada:
                    panel.visor.on_pagina_cambiada(pag_objetivo)
            else:
                raise ValueError
        except ValueError:
            panel.entry_pagina.delete(0, "end")
            panel.entry_pagina.insert(0, str(panel.indice_slide_actual + 1))
        panel.focus_set()

    panel.entry_pagina.bind("<Return>", saltar_pagina_cmd)

    btn_sig = ctk.CTkButton(nav_box, text="▶", width=35, height=28, fg_color=COLOR_GUINDA,
                            hover_color=COLOR_GUINDA_HOVER, command=btn_avanzar_cmd)
    btn_sig.pack(side="right")

    ctk.CTkButton(footer, text="📊  Ver reporte de desviaciones", height=32, corner_radius=8,
                  fg_color="#FDF2F4", text_color=COLOR_GUINDA, border_width=1,
                  border_color=COLOR_GUINDA, hover_color="#FCE7EB",
                  font=ctk.CTkFont(size=12, weight="bold"),
                  command=lambda: _abrir_reporte()).pack(fill="x", padx=10, pady=(2, 10))

    # =======================================================================
    # RENDER DEL ANÁLISIS POR SLIDE
    # =======================================================================
    def _slabel(parent, texto):
        ctk.CTkLabel(parent, text=texto.upper(), font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TXT_TERCIARIO, anchor="w").pack(fill="x", pady=(10, 4))

    def _divider(parent):
        ctk.CTkFrame(parent, height=1, fg_color=BORDE).pack(fill="x", pady=8)

    def _actualizar_contenido(indice_slide):
        for w in scroll_frame.winfo_children():
            w.destroy()

        panel.indice_slide_actual = indice_slide
        slide_n = indice_slide + 1

        # Navegación (espejo de presentation_data_panel)
        total = panel.visor.total_paginas if panel.visor else 1
        panel.entry_pagina.delete(0, "end")
        panel.entry_pagina.insert(0, str(slide_n))
        panel.label_paginas_total.configure(text=f"/ {total}")
        if panel.visor:
            btn_ant.configure(state="disabled" if indice_slide == 0 else "normal")
            btn_sig.configure(state="disabled" if indice_slide >= total - 1 else "normal")

        ref = _t_ref(slide_n)
        real = _real(panel.grupo_actual, slide_n) if panel.grupo_actual else None
        pct = _dev_pct(real, ref) if real is not None else None
        col = _color_desv(pct) if pct is not None else "#888888"
        pct_txt = (f"{'+' if pct > 0 else ''}{pct}%") if pct is not None else "—"

        # --- Mini métricas ---
        grid = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        grid.pack(fill="x", pady=(2, 8))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="m")

        def _mini(col_i, valor, etiqueta, color_valor=COLOR_TIEMPO):
            c = ctk.CTkFrame(grid, fg_color=BG_SECONDARY, corner_radius=8)
            c.grid(row=0, column=col_i, sticky="nsew", padx=2)
            ctk.CTkLabel(c, text=valor, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=color_valor).pack(pady=(7, 0))
            ctk.CTkLabel(c, text=etiqueta, font=ctk.CTkFont(size=9),
                         text_color=TXT_TERCIARIO).pack(pady=(0, 7))

        _mini(0, _fmt(ref), "Rec. IA")
        _mini(1, _fmt(real) if real is not None else "—", f"Real · {panel.grupo_actual or '—'}")
        _mini(2, pct_txt, "Desviación", col)

        # --- Estado ---
        _slabel(scroll_frame, "Estado")
        if pct is not None:
            txt, c_txt, c_bg = _badge_estado(pct)
        else:
            txt, c_txt, c_bg = ("Sin tiempo real", TXT_SECOND, BG_SECONDARY)
        row_b = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        row_b.pack(fill="x")
        ctk.CTkLabel(row_b, text=f"  {txt}  ", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=c_txt, fg_color=c_bg, corner_radius=20, height=24).pack(anchor="w")

        # --- Barra real vs recomendado ---
        _slabel(scroll_frame, "Tiempo real vs recomendado")
        max_b = max(real or 0, ref, 1)
        barra = _construir_barra(scroll_frame, (real / max_b) if real is not None else 0,
                                 ref / max_b, col,
                                 etiqueta_fill=(pct_txt if real is not None else None))
        barra.pack(fill="x")
        leg = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        leg.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(leg, text="▮ Tiempo real", font=ctk.CTkFont(size=10),
                     text_color=col).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(leg, text="│ Recomendado IA", font=ctk.CTkFont(size=10),
                     text_color=COLOR_GUINDA).pack(side="left")

        _divider(scroll_frame)

        # --- Comparativa por grupo ---
        _slabel(scroll_frame, "Comparativa por grupo en esta slide")
        comp = ctk.CTkFrame(scroll_frame, fg_color=BG_SECONDARY, corner_radius=8)
        comp.pack(fill="x")
        if not panel.grupos:
            ctk.CTkLabel(comp, text="—", text_color=TXT_TERCIARIO,
                         font=ctk.CTkFont(size=11)).pack(padx=10, pady=8)
        else:
            todos = [(_real(g, slide_n) or 0) for g in panel.grupos.keys()]
            max_g = max([ref] + todos + [1])
            for g in panel.grupos.keys():
                t = _real(g, slide_n)
                act = (g == panel.grupo_actual)
                fila = ctk.CTkFrame(comp, fg_color="transparent")
                fila.pack(fill="x", padx=10, pady=4)
                ctk.CTkLabel(fila, text="●" if act else "", width=10,
                             font=ctk.CTkFont(size=10), text_color=COLOR_GUINDA).pack(side="left")
                ctk.CTkLabel(fila, text=g, width=38, anchor="w",
                             font=ctk.CTkFont(size=10, weight="bold" if act else "normal"),
                             text_color=COLOR_TIEMPO if act else TXT_SECOND).pack(side="left")
                if t is None:
                    g_track = _construir_barra(fila, 0, ref / max_g, "#888888",
                                               alto=14, track_bg="white")
                    g_track.pack(side="left", fill="x", expand=True, padx=6)
                    ctk.CTkLabel(fila, text="—", width=66, anchor="e",
                                 font=ctk.CTkFont(size=10),
                                 text_color=TXT_TERCIARIO).pack(side="left")
                else:
                    g_pct = _dev_pct(t, ref)
                    g_col = _color_desv(g_pct)
                    g_track = _construir_barra(fila, t / max_g, ref / max_g, g_col,
                                               alto=14, track_bg="white")
                    g_track.pack(side="left", fill="x", expand=True, padx=6)
                    ctk.CTkLabel(fila, text=f"{_fmt(t)}  {'+' if g_pct > 0 else ''}{g_pct}%",
                                 width=66, anchor="e",
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color=g_col).pack(side="left")

        _divider(scroll_frame)

        # --- Contenido IA (score) ---
        _slabel(scroll_frame, "Contenido IA")
        sc = _score(slide_n)
        sc_txt = f"{sc}/10" if sc is not None else "Omitida"
        row_sc = ctk.CTkFrame(scroll_frame, fg_color=BG_SECONDARY, corner_radius=8, height=34)
        row_sc.pack(fill="x")
        row_sc.pack_propagate(False)
        ctk.CTkLabel(row_sc, text="Score análisis", font=ctk.CTkFont(size=11),
                     text_color=TXT_SECOND).pack(side="left", padx=10)
        ctk.CTkLabel(row_sc, text=sc_txt, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COLOR_GUINDA).pack(side="right", padx=10)

        # --- Alerta inline ---
        alerta = _alerta(slide_n)
        if alerta:
            tipo, msg = alerta
            if tipo == "under":
                a_bg, a_bd, a_tx, ic = "#FAEEDA", "#EF9F27", "#633806", "⏱↓"
            else:
                a_bg, a_bd, a_tx, ic = "#FAECE7", "#D85A30", "#4A1B0C", "⏱↑"
            box = ctk.CTkFrame(scroll_frame, fg_color=a_bg, corner_radius=8,
                               border_width=1, border_color=a_bd)
            box.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(box, text=f"{ic}  {msg}", font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=a_tx, wraplength=260, justify="left",
                         anchor="w").pack(fill="x", padx=10, pady=8)

    panel.actualizar_contenido_por_slide = _actualizar_contenido

    # =======================================================================
    # MODAL: REPORTE DE DESVIACIONES
    # =======================================================================
    def _abrir_reporte():
        if not panel.grupo_actual:
            return
        if panel._modal is not None and panel._modal.winfo_exists():
            panel._modal.focus()
            return

        g_data = panel.grupos[panel.grupo_actual]
        devs = _desviaciones(panel.grupo_actual)
        total_real = sum((g_data.get("tiempos_por_slide", {}) or {}).values())
        total_ref = sum(d["ref"] for d in devs)
        total_plan = _planeado_grupo(g_data)
        total_pct = _dev_pct(total_real, total_ref)
        bajo = [d for d in devs if d["pct"] < 0][:3]
        sobre = list(reversed([d for d in devs if d["pct"] > 0]))[:3]

        modal = ctk.CTkToplevel(panel)
        panel._modal = modal
        modal.title("Reporte de desviaciones")
        modal.geometry("560x640")
        modal.transient(panel.winfo_toplevel())
        modal.grab_set()
        modal.configure(fg_color="white")

        def _cerrar():
            try:
                modal.grab_release()
            except Exception:
                pass
            modal.destroy()
            panel._modal = None
        modal.protocol("WM_DELETE_WINDOW", _cerrar)

        head = ctk.CTkFrame(modal, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkButton(head, text="✕", width=28, height=28, corner_radius=14,
                      fg_color=BG_SECONDARY, text_color=TXT_SECOND, hover_color="#E2E8F0",
                      command=_cerrar).pack(side="right", anchor="n")
        head_txt = ctk.CTkFrame(head, fg_color="transparent")
        head_txt.pack(side="left", anchor="w")
        ctk.CTkLabel(head_txt, text=f"REPORTE · {panel.grupo_actual}",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_ORO).pack(anchor="w")
        ctk.CTkLabel(head_txt, text="Desviaciones de tiempo por slide",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TIEMPO).pack(anchor="w", pady=(2, 0))
        ctk.CTkFrame(modal, height=1, fg_color=BORDE).pack(fill="x")

        body = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        ctk.CTkLabel(body, text=f"RESUMEN · {panel.grupo_actual}",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TXT_TERCIARIO, anchor="w").pack(fill="x", pady=(0, 6))
        res = ctk.CTkFrame(body, fg_color="transparent")
        res.pack(fill="x")
        for i in range(3):
            res.grid_columnconfigure(i, weight=1, uniform="r")

        def _sum_card(col_i, valor, etiqueta, color_valor=COLOR_TIEMPO):
            c = ctk.CTkFrame(res, fg_color=BG_SECONDARY, corner_radius=8)
            c.grid(row=0, column=col_i, sticky="nsew", padx=3)
            ctk.CTkLabel(c, text=valor, font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=color_valor).pack(pady=(8, 0))
            ctk.CTkLabel(c, text=etiqueta, font=ctk.CTkFont(size=10),
                         text_color=TXT_TERCIARIO, wraplength=140).pack(pady=(2, 8))

        _sum_card(0, _fmt(total_plan), "Planeado (docente)")
        _sum_card(1, _fmt(total_real), "Tiempo real total")
        _sum_card(2, f"{'+' if total_pct > 0 else ''}{total_pct}%", "Desviación global",
                  _color_desv(total_pct))

        ctk.CTkFrame(body, height=1, fg_color=BORDE).pack(fill="x", pady=12)

        def _dev_card(d, tipo, rank):
            es_u = (tipo == "under")
            col = COLOR_UNDER if es_u else COLOR_OVER
            bg = "#FAEEDA" if es_u else "#FAECE7"
            bd = "#EF9F27" if es_u else "#D85A30"
            badge = f"↓ Déficit #{rank}" if es_u else f"↑ Exceso #{rank}"
            card = ctk.CTkFrame(body, fg_color=bg, corner_radius=10, border_width=1, border_color=bd)
            card.pack(fill="x", pady=5)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(10, 4))
            ctk.CTkLabel(top, text=f" {badge} ", font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=col, fg_color="white", corner_radius=20).pack(side="left")
            h2 = ctk.CTkFrame(card, fg_color="transparent")
            h2.pack(fill="x", padx=14)
            ctk.CTkLabel(h2, text=f"Diapositiva {d['n']}",
                         font=ctk.CTkFont(size=13, weight="bold"), text_color=col).pack(side="left")
            ctk.CTkLabel(h2, text=f"{'+' if d['pct'] > 0 else ''}{d['pct']}%",
                         font=ctk.CTkFont(size=13, weight="bold"), text_color=col).pack(side="right")
            max_v = max(d["real"], d["ref"], 1)
            _construir_barra(card, d["real"] / max_v, d["ref"] / max_v, col,
                             alto=12, track_bg="#00000010").pack(fill="x", padx=14, pady=(6, 4))
            diff = abs(d["real"] - d["ref"])
            ctk.CTkLabel(card, text=f"Real: {_fmt(d['real'])}  ·  Rec. IA: {_fmt(d['ref'])}  ·  Dif: {_fmt(diff)}",
                         font=ctk.CTkFont(size=11), text_color=col, anchor="w").pack(fill="x", padx=14, pady=(0, 10))

        if bajo:
            ctk.CTkLabel(body, text="SLIDES CON MENOS TIEMPO DEL RECOMENDADO",
                         font=ctk.CTkFont(size=10, weight="bold"), text_color=TXT_TERCIARIO,
                         anchor="w").pack(fill="x", pady=(0, 6))
            for i, d in enumerate(bajo):
                _dev_card(d, "under", i + 1)
        if sobre:
            ctk.CTkLabel(body, text="SLIDES QUE EXCEDIERON EL TIEMPO RECOMENDADO",
                         font=ctk.CTkFont(size=10, weight="bold"), text_color=TXT_TERCIARIO,
                         anchor="w").pack(fill="x", pady=(12, 6))
            for i, d in enumerate(sobre):
                _dev_card(d, "over", i + 1)
        if not bajo and not sobre:
            ctk.CTkLabel(body, text="Sin desviaciones significativas.",
                         font=ctk.CTkFont(size=13), text_color=TXT_SECOND).pack(pady=30)

        ctk.CTkFrame(modal, height=1, fg_color=BORDE).pack(fill="x")
        foot = ctk.CTkFrame(modal, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=(10, 16))
        ctk.CTkButton(foot, text="Entendido", height=36, corner_radius=8, fg_color=COLOR_GUINDA,
                      hover_color=COLOR_GUINDA_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
                      command=_cerrar).pack(fill="x")

    def cerrar_modal():
        if panel._modal is not None and panel._modal.winfo_exists():
            try:
                panel._modal.grab_release()
            except Exception:
                pass
            panel._modal.destroy()
        panel._modal = None

    panel.cerrar_modal = cerrar_modal

    # =======================================================================
    # ARRANQUE
    # =======================================================================
    _construir_pills()

    # Si la vista ya inyectó el visor al crear, sincroniza de inmediato.
    if panel.visor is not None:
        panel.visor.on_pagina_cambiada = panel.actualizar_contenido_por_slide
        panel.actualizar_contenido_por_slide(panel.visor.pagina_actual)
    else:
        # Pinta el estado de la primera slide aunque el visor aún no esté listo.
        _actualizar_contenido(0)

    return panel