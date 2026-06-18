# app/presentation/widgets/performance_mode/performance_chart_panel.py
"""
Gráfica de tiempo por diapositiva (ocupa todo el espacio inferior).

- Filtro de grupo como PESTAÑAS dentro de la cabecera.
- Botón "Desviaciones" que abre el reporte en una ventana (on_ver_reporte).
- BARRA DE SCROLL horizontal para recorrer todas las diapositivas.
- TOOLTIP al pasar el cursor: diapositiva, tiempo real y de IA.
- Dos líneas pastel de la marca: real (guinda, gruesa, con área) e IA (oro punteado).

Grafica TODAS las diapositivas; la real cae a 0s donde no se presentó.
Al cambiar de pestaña avisa por on_grupo_cambiado(grupo).
"""

import tkinter as tk
import customtkinter as ctk

COLOR_REAL      = "#6A1B31"
COLOR_REAL_FILL = "#F4E2E7"
COLOR_IA        = "#BC955C"
COLOR_GRID      = "#EFF1F5"
COLOR_EJE       = "#D8DEE8"
COLOR_GUIA      = "#D9C2C9"
BG_PLOT         = "#FCFBFB"
TXT_SECOND      = "#64748B"
TXT_TERC        = "#9AA3B2"
TAB_BG          = "#F1F5F9"


def _fmt(seg):
    seg = int(round(seg or 0))
    if seg < 60:
        return f"{seg}s"
    m, s = divmod(seg, 60)
    return f"{m}m{s:02d}s" if s else f"{m}m"


def crear_grafica_rendimiento(master, nombre_presentacion, analisis, grupos,
                              on_grupo_cambiado=None, on_ver_reporte=None, **kwargs):
    panel = ctk.CTkFrame(master, fg_color="white", corner_radius=16,
                         border_width=1, border_color="#ECECEC", **kwargs)

    panel.analisis = analisis or {}
    panel.grupos = grupos or {}
    panel.on_grupo_cambiado = on_grupo_cambiado
    panel.on_ver_reporte = on_ver_reporte
    panel.grupo_actual = next(iter(panel.grupos.keys()), None)
    panel.inicio = 0
    panel.por_vista = 12
    panel._ymax = 1
    panel._resize_id = None
    panel._pts = []
    panel._geom = (54, 18, 10, 10)
    panel._tabs = {}

    panel.slides_por_num = {}
    for s in panel.analisis.get("slides", []):
        panel.slides_por_num[s.get("slide_number")] = s
    panel.total = panel.analisis.get("total_diapositivas") or (
        max(panel.slides_por_num) if panel.slides_por_num else 0)

    # ===== Header: titulo + (pestañas + botón) =====
    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=20, pady=(14, 2))
    izq = ctk.CTkFrame(header, fg_color="transparent")
    izq.pack(side="left")
    ctk.CTkLabel(izq, text="Tendencia de tiempo por diapositiva",
                 font=ctk.CTkFont(size=16, weight="bold"), text_color="#1E293B").pack(anchor="w")
    ctk.CTkLabel(izq, text=nombre_presentacion, font=ctk.CTkFont(size=11),
                 text_color=TXT_SECOND).pack(anchor="w")

    der = ctk.CTkFrame(header, fg_color="transparent")
    der.pack(side="right")
    ctk.CTkButton(der, text="📋  Desviaciones", height=34, corner_radius=9,
                  fg_color="white", text_color=COLOR_REAL, border_width=1, border_color=COLOR_REAL,
                  hover_color="#FBEFF2", font=ctk.CTkFont(size=12, weight="bold"),
                  command=lambda: (panel.on_ver_reporte and panel.on_ver_reporte(panel.grupo_actual))
                  ).pack(side="right", padx=(10, 0))
    panel._tabs_wrap = ctk.CTkFrame(der, fg_color=TAB_BG, corner_radius=12)
    panel._tabs_wrap.pack(side="right")

    # ===== Leyenda =====
    leg = ctk.CTkFrame(panel, fg_color="transparent")
    leg.pack(fill="x", padx=20, pady=(2, 0))
    ctk.CTkLabel(leg, text="\u25CF", text_color=COLOR_REAL, font=ctk.CTkFont(size=14)).pack(side="left")
    ctk.CTkLabel(leg, text="Tiempo real", text_color=TXT_SECOND,
                 font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(2, 16))
    ctk.CTkLabel(leg, text="\u25CF", text_color=COLOR_IA, font=ctk.CTkFont(size=14)).pack(side="left")
    ctk.CTkLabel(leg, text="Recomendado IA", text_color=TXT_SECOND,
                 font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 0))

    # ===== Lienzo (ocupa el resto) =====
    cont = ctk.CTkFrame(panel, fg_color=BG_PLOT, corner_radius=12)
    cont.pack(fill="both", expand=True, padx=20, pady=(8, 4))
    panel.canvas = tk.Canvas(cont, bg=BG_PLOT, highlightthickness=0, bd=0)
    panel.canvas.pack(fill="both", expand=True, padx=10, pady=10)

    # ===== Scroll horizontal + caption =====
    panel.scroll = ctk.CTkScrollbar(panel, orientation="horizontal", command=lambda *a: _xview(*a))
    panel.scroll.pack(fill="x", padx=20, pady=(0, 2))
    ctk.CTkLabel(panel, text="Pasa el cursor sobre un punto para ver el detalle",
                 font=ctk.CTkFont(size=11, slant="italic"), text_color=TXT_TERC).pack(pady=(0, 10))

    # ---- datos ----
    def _ia(n):
        return panel.slides_por_num.get(n, {}).get("tiempo_exposicion", 0) or 0

    def _real(n):
        if not panel.grupo_actual:
            return 0
        tps = (panel.grupos.get(panel.grupo_actual, {}) or {}).get("tiempos_por_slide", {}) or {}
        v = tps.get(str(n))
        return v if v is not None else 0

    def _ticks(ymax, n=4):
        if ymax <= 0:
            return [0]
        return sorted(set(int(round(ymax * k / n)) for k in range(n + 1)))

    def _clamp():
        panel.inicio = max(0, min(panel.inicio, max(0, panel.total - panel.por_vista)))

    def _xview(*args):
        if not args:
            return
        if args[0] == "moveto":
            panel.inicio = int(round(float(args[1]) * panel.total))
        elif args[0] == "scroll":
            n = int(args[1]); what = args[2] if len(args) > 2 else "units"
            panel.inicio += n * (max(1, panel.por_vista) if what == "pages" else 1)
        _clamp()
        _dibujar()

    def _recalcular_ymax():
        m = 1
        for n in range(1, panel.total + 1):
            m = max(m, _ia(n), _real(n))
        panel._ymax = m

    def _dibujar():
        c = panel.canvas
        c.delete("all")
        panel._pts = []
        W, H = c.winfo_width(), c.winfo_height()
        if W < 80 or H < 80:
            panel.after(80, _dibujar)
            return
        if panel.total <= 0:
            c.create_text(W / 2, H / 2, text="Sin datos de análisis", fill=TXT_TERC,
                          font=("Segoe UI", 12))
            return

        ml, mr, mt, mb = 54, 18, 18, 38
        pw, ph = W - ml - mr, H - mt - mb
        panel._geom = (ml, mt, pw, ph)
        if pw < 30 or ph < 30:
            return

        panel.por_vista = max(5, min(panel.total, int(pw // 70)))
        _clamp()
        ini = panel.inicio
        nums = list(range(ini + 1, min(ini + panel.por_vista, panel.total) + 1))
        ymax = panel._ymax if panel._ymax > 0 else 1

        def X(i):
            if len(nums) == 1:
                return ml + pw / 2
            return ml + pw * i / (len(nums) - 1)

        def Y(t):
            return mt + ph * (1 - min(t, ymax) / ymax)

        for tv in _ticks(ymax):
            y = Y(tv)
            c.create_line(ml, y, ml + pw, y, fill=COLOR_GRID)
            c.create_text(ml - 8, y, text=_fmt(tv), anchor="e", fill=TXT_TERC, font=("Segoe UI", 8))
        c.create_line(ml, mt, ml, mt + ph, fill=COLOR_EJE)
        c.create_line(ml, mt + ph, ml + pw, mt + ph, fill=COLOR_EJE)
        for i, n in enumerate(nums):
            c.create_text(X(i), mt + ph + 14, text=str(n), fill=TXT_SECOND, font=("Segoe UI", 8, "bold"))

        pts_real = [(X(i), Y(_real(n))) for i, n in enumerate(nums)]
        pts_ia = [(X(i), Y(_ia(n))) for i, n in enumerate(nums)]

        if len(pts_real) >= 2:
            poly = pts_real + [(pts_real[-1][0], mt + ph), (pts_real[0][0], mt + ph)]
            c.create_polygon(*[v for xy in poly for v in xy], fill=COLOR_REAL_FILL, outline="")

        for j in range(len(pts_ia) - 1):
            c.create_line(*pts_ia[j], *pts_ia[j + 1], fill=COLOR_IA, width=3, dash=(5, 3))
        for j in range(len(pts_real) - 1):
            c.create_line(*pts_real[j], *pts_real[j + 1], fill=COLOR_REAL, width=3)

        mostrar_lbl = panel.por_vista <= 12
        for i, n in enumerate(nums):
            xr, yr = pts_real[i]
            xi, yi = pts_ia[i]
            rv, iv = _real(n), _ia(n)
            c.create_oval(xi - 4, yi - 4, xi + 4, yi + 4, fill="white", outline=COLOR_IA, width=2)
            c.create_oval(xr - 5, yr - 5, xr + 5, yr + 5, fill=COLOR_REAL, outline="white", width=2)
            if mostrar_lbl and rv > 0:
                c.create_text(xr, yr - 13, text=_fmt(rv), fill=COLOR_REAL, font=("Segoe UI", 8, "bold"))
            panel._pts.append((n, xr, yr, yi, rv, iv))

        first = ini / panel.total if panel.total else 0
        last = min(1.0, (ini + panel.por_vista) / panel.total) if panel.total else 1
        panel.scroll.set(first, last)

    def _hover(e):
        if not panel._pts:
            return
        ml, mt, pw, ph = panel._geom
        cerca = min(panel._pts, key=lambda p: abs(e.x - p[1]))
        if abs(e.x - cerca[1]) > 40:
            panel.canvas.delete("hover")
            return
        n, xr, yr, yi, rv, iv = cerca
        c = panel.canvas
        c.delete("hover")
        c.create_line(xr, mt, xr, mt + ph, fill=COLOR_GUIA, dash=(2, 2), tags="hover")
        c.create_oval(xr - 8, yr - 8, xr + 8, yr + 8, outline=COLOR_REAL, width=2, tags="hover")
        c.create_oval(xr - 7, yi - 7, xr + 7, yi + 7, outline=COLOR_IA, width=2, tags="hover")
        t1 = f"Diapositiva {n}"
        rv_txt = f"Real {_fmt(rv)}" + ("  (no presentada)" if rv == 0 else "")
        t2 = f"{rv_txt}   \u00B7   IA {_fmt(iv)}"
        bw, bh = 200, 42
        bx = min(max(xr - bw / 2, ml), ml + pw - bw)
        by = mt + 2
        c.create_rectangle(bx, by, bx + bw, by + bh, fill="white", outline="#E6D6DB", width=1, tags="hover")
        c.create_text(bx + 10, by + 13, text=t1, anchor="w", fill=COLOR_REAL,
                      font=("Segoe UI", 9, "bold"), tags="hover")
        c.create_text(bx + 10, by + 29, text=t2, anchor="w", fill=TXT_SECOND,
                      font=("Segoe UI", 9), tags="hover")

    def _leave(e):
        panel.canvas.delete("hover")

    def _on_resize(e):
        if e.width > 40 and e.height > 40:
            if panel._resize_id:
                panel.after_cancel(panel._resize_id)
            panel._resize_id = panel.after(80, _dibujar)

    panel.canvas.bind("<Configure>", _on_resize)
    panel.canvas.bind("<Motion>", _hover)
    panel.canvas.bind("<Leave>", _leave)

    # ---- pestañas de grupo ----
    def _seleccionar_grupo(g, notificar=True):
        panel.grupo_actual = g
        for k, b in panel._tabs.items():
            act = (k == g)
            b.configure(fg_color="white" if act else "transparent",
                        text_color=COLOR_REAL if act else TXT_SECOND)
        _recalcular_ymax()
        _dibujar()
        if notificar and panel.on_grupo_cambiado:
            panel.on_grupo_cambiado(g)

    def _construir_tabs():
        for w in panel._tabs_wrap.winfo_children():
            w.destroy()
        panel._tabs = {}
        if not panel.grupos:
            ctk.CTkLabel(panel._tabs_wrap, text="Sin grupos",
                         font=ctk.CTkFont(size=11, slant="italic"),
                         text_color=TXT_TERC).pack(padx=12, pady=8)
            return
        for g in panel.grupos.keys():
            act = (g == panel.grupo_actual)
            b = ctk.CTkButton(panel._tabs_wrap, text=g, height=30, corner_radius=9,
                              fg_color="white" if act else "transparent",
                              text_color=COLOR_REAL if act else TXT_SECOND,
                              hover_color="#E2E8F0", font=ctk.CTkFont(size=12, weight="bold"),
                              command=lambda k=g: _seleccionar_grupo(k))
            b.pack(side="left", padx=3, pady=4)
            panel._tabs[g] = b

    def dibujar(grupo):
        _seleccionar_grupo(grupo, notificar=False)

    panel.dibujar = dibujar
    panel.seleccionar_grupo = _seleccionar_grupo

    _construir_tabs()
    if panel.grupo_actual:
        _recalcular_ymax()
    panel.after(250, _dibujar)
    return panel