# app/presentation/widgets/performance_mode/performance_summary_panel.py
"""
Fila superior de tarjetas de resumen (compactas, blancas con franja de color).

Cinco tarjetas:
  - Calificación de la presentación (score_global)   [fija]
  - Tiempo que recomienda la IA                       [fija]
  - Tiempo que planeó el docente                      [depende del grupo]
  - Duración real de la sesión                        [depende del grupo]
  - Desviación global vs IA                           [depende del grupo]

actualizar(grupo) refresca las tarjetas dependientes del grupo.
"""

import customtkinter as ctk

COLOR_GUINDA = "#6A1B31"
COLOR_OK     = "#1D9E75"
COLOR_UNDER  = "#BA7517"
COLOR_OVER   = "#D85A30"
TXT_SECOND   = "#64748B"
TXT_TERC     = "#94A3B8"
BORDE        = "#ECECEC"
UMBRAL_DESV  = 20

ALTO_TARJETA = 88


def _fmt(seg):
    seg = int(round(seg or 0))
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


def _planeado_grupo(gdata):
    sesiones = gdata.get("historial_sesiones", {}) or {}
    if sesiones:
        try:
            ultima = str(max(int(k) for k in sesiones.keys()))
            return sesiones[ultima].get("planeado_seg", 0)
        except Exception:
            pass
    return gdata.get("planeado_seg", 0)


def crear_resumen_rendimiento(master, analisis: dict, grupos: dict, **kwargs):
    panel = ctk.CTkFrame(master, fg_color="transparent", **kwargs)
    panel.analisis = analisis or {}
    panel.grupos = grupos or {}

    panel.slides_por_num = {}
    for s in panel.analisis.get("slides", []):
        panel.slides_por_num[s.get("slide_number")] = s
    panel.total = panel.analisis.get("total_diapositivas") or (
        max(panel.slides_por_num) if panel.slides_por_num else 0)

    def _ia(n):
        return panel.slides_por_num.get(n, {}).get("tiempo_exposicion", 0) or 0

    ia_total = panel.analisis.get("tiempo_total_exposicion_segundos") or \
        sum(_ia(n) for n in range(1, panel.total + 1))

    sg = panel.analisis.get("score_global_presentacion", {}) or {}
    score = sg.get("score_global")
    zona = sg.get("zona_global", "")
    score_txt = f"{score:.1f}/10" if isinstance(score, (int, float)) else "—"

    for i in range(5):
        panel.grid_columnconfigure(i, weight=1, uniform="card")

    def _card(col, accent, etiqueta, valor, sub, color_valor=None):
        # Tarjeta BLANCA, compacta, con franja de color a la izquierda
        card = ctk.CTkFrame(panel, fg_color="white", corner_radius=12,
                            height=ALTO_TARJETA, border_width=1, border_color=BORDE)
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        card.pack_propagate(False)

        franja = ctk.CTkFrame(card, fg_color=accent, corner_radius=8, width=5)
        franja.pack(side="left", fill="y", padx=(8, 0), pady=12)

        cont = ctk.CTkFrame(card, fg_color="transparent")
        cont.pack(side="left", fill="both", expand=True, padx=(10, 12), pady=8)
        ctk.CTkLabel(cont, text=etiqueta.upper(), font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TXT_TERC, anchor="w").pack(fill="x")
        lbl_val = ctk.CTkLabel(cont, text=valor, font=ctk.CTkFont(size=19, weight="bold"),
                               text_color=color_valor or accent, anchor="w")
        lbl_val.pack(fill="x", pady=(1, 0))
        lbl_sub = ctk.CTkLabel(cont, text=sub, font=ctk.CTkFont(size=10),
                               text_color=TXT_SECOND, anchor="w")
        lbl_sub.pack(fill="x")
        return lbl_val, lbl_sub

    # Fijas
    _card(0, "#2563EB", "Calificación", score_txt, zona.capitalize() if zona else "—")
    _card(1, "#BC955C", "Tiempo IA", _fmt(ia_total), "recomendado")
    # Dependientes del grupo
    panel._lbl_doc, _ = _card(2, "#0E9AA8", "Planeó docente", "—", "estimado")
    panel._lbl_real, panel._lbl_real_sub = _card(3, COLOR_GUINDA, "Duración real", "—", "—")
    panel._lbl_desv, _ = _card(4, "#64748B", "Desviación", "—", "vs IA")

    def actualizar(grupo):
        if not grupo or grupo not in panel.grupos:
            panel._lbl_doc.configure(text="—")
            panel._lbl_real.configure(text="—", text_color=COLOR_GUINDA)
            panel._lbl_real_sub.configure(text="sin grupo")
            panel._lbl_desv.configure(text="—", text_color="#64748B")
            return
        gd = panel.grupos.get(grupo, {}) or {}
        tps = gd.get("tiempos_por_slide", {}) or {}
        real_total = gd.get("tiempo_total_seg") or sum(v for v in tps.values() if v)
        plan_total = _planeado_grupo(gd)
        dev = _dev_pct(real_total, ia_total) if ia_total else 0

        presentadas = 0
        for k, v in tps.items():
            try:
                n = int(k)
            except (ValueError, TypeError):
                continue
            if n in panel.slides_por_num and (v or 0) > 0:
                presentadas += 1

        panel._lbl_doc.configure(text=_fmt(plan_total))
        panel._lbl_real.configure(text=_fmt(real_total), text_color=_color_desv(dev))
        panel._lbl_real_sub.configure(text=f"{presentadas}/{panel.total} diapositivas")
        panel._lbl_desv.configure(text=f"{'+' if dev > 0 else ''}{dev}%", text_color=_color_desv(dev))

    panel.actualizar = actualizar
    return panel