# app/presentation/widgets/performance_mode/performance_deviations_panel.py
"""
Reporte de desviaciones como VENTANA (modal), abierto desde un botón en la
gráfica. Muestra, para el grupo seleccionado, dos categorías:
  - "Duró muy poco"  (real << esperado)
  - "Duró mucho"     (real >> esperado)
Hasta 3 diapositivas por categoría; solo cuenta diapositivas presentadas (real > 0).

REFERENCIA DE LA DESVIACIÓN:
La desviación se mide SIEMPRE contra el tiempo que planeó el docente (nunca
contra la recomendación de la IA). Como el docente planea un tiempo TOTAL de
sesión, ese total se reparte entre las diapositivas de forma proporcional al
recomendado por la IA para cada una (el reparto es solo interno del cálculo).

Uso:
    from .performance_deviations_panel import abrir_reporte_desviaciones
    abrir_reporte_desviaciones(parent, analisis, grupos, grupo)
"""

import customtkinter as ctk

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_UNDER        = "#BA7517"
COLOR_OVER         = "#D85A30"
COLOR_ORO          = "#BC955C"
TXT_SECOND         = "#64748B"
TXT_TERC           = "#94A3B8"
BORDE              = "#ECECEC"


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


def _planeado_grupo(gdata):
    """Tiempo total que planeó el docente para la sesión más reciente del grupo."""
    sesiones = (gdata or {}).get("historial_sesiones", {}) or {}
    if sesiones:
        try:
            ultima = str(max(int(k) for k in sesiones.keys()))
            return sesiones[ultima].get("planeado_seg", 0)
        except Exception:
            pass
    return (gdata or {}).get("planeado_seg", 0)


def abrir_reporte_desviaciones(parent, analisis: dict, grupos: dict, grupo):
    analisis = analisis or {}
    grupos = grupos or {}

    slides_por_num = {}
    for s in analisis.get("slides", []):
        slides_por_num[s.get("slide_number")] = s

    def _ia(n):
        return slides_por_num.get(n, {}).get("tiempo_exposicion", 0) or 0

    def _zona(n):
        return slides_por_num.get(n, {}).get("zona_slide")

    gdata = grupos.get(grupo, {}) or {}
    plan_total = _planeado_grupo(gdata)
    ia_total = sum(_ia(n) for n in slides_por_num)

    def _esperado(n):
        """Parte del tiempo planeado por el docente que corresponde a esta diapositiva."""
        if plan_total <= 0 or ia_total <= 0:
            return 0
        return plan_total * (_ia(n) / ia_total)

    devs = []
    tps = gdata.get("tiempos_por_slide", {}) or {}
    for k, v in tps.items():
        try:
            n = int(k)
        except (ValueError, TypeError):
            continue
        if n in slides_por_num and (v or 0) > 0:
            ref = _esperado(n)
            devs.append({"n": n, "real": v, "ref": ref, "pct": _dev_pct(v, ref)})
    devs.sort(key=lambda d: d["pct"])
    poco = [d for d in devs if d["pct"] < 0][:3]
    mucho = list(reversed([d for d in devs if d["pct"] > 0]))[:3]
    sin_referencia = plan_total <= 0 or ia_total <= 0

    try:
        raiz = parent.winfo_toplevel()
    except Exception:
        raiz = parent

    modal = ctk.CTkToplevel(raiz)
    modal.title("Reporte de desviaciones")
    modal.geometry("780x560")
    modal.transient(raiz)
    modal.grab_set()
    modal.configure(fg_color="white")

    def _cerrar():
        try:
            modal.grab_release()
        except Exception:
            pass
        modal.destroy()
    modal.protocol("WM_DELETE_WINDOW", _cerrar)

    head = ctk.CTkFrame(modal, fg_color="transparent")
    head.pack(fill="x", padx=22, pady=(18, 8))
    ctk.CTkLabel(head, text=f"REPORTE · {grupo or '—'}", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color=COLOR_ORO).pack(anchor="w")
    ctk.CTkLabel(head, text="Desviaciones de tiempo por diapositiva",
                 font=ctk.CTkFont(size=17, weight="bold"), text_color="#1E293B").pack(anchor="w", pady=(2, 0))
    if sin_referencia:
        ctk.CTkLabel(head, text="Sin referencia: este grupo no registró tiempo planeado o el análisis no tiene tiempos.",
                     font=ctk.CTkFont(size=10), text_color=COLOR_UNDER).pack(anchor="w", pady=(2, 0))
    else:
        ctk.CTkLabel(head, text=f"Referencia: lo planeado por el docente ({_fmt(plan_total)}) repartido entre las diapositivas.",
                     font=ctk.CTkFont(size=10), text_color=TXT_SECOND).pack(anchor="w", pady=(2, 0))
    ctk.CTkFrame(modal, height=1, fg_color=BORDE).pack(fill="x")

    cuerpo = ctk.CTkFrame(modal, fg_color="transparent")
    cuerpo.pack(fill="both", expand=True, padx=22, pady=12)
    cuerpo.grid_columnconfigure(0, weight=1, uniform="dv")
    cuerpo.grid_columnconfigure(1, weight=1, uniform="dv")
    cuerpo.grid_rowconfigure(0, weight=1)

    def _columna(col, titulo, accent, datos, bg_fila):
        c = ctk.CTkFrame(cuerpo, fg_color="white", corner_radius=14, border_width=1, border_color=BORDE)
        c.grid(row=0, column=col, sticky="nsew", padx=6)
        ctk.CTkLabel(c, text=titulo, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=accent).pack(anchor="w", padx=14, pady=(12, 6))
        body = ctk.CTkScrollableFrame(c, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        if not datos:
            ctk.CTkLabel(body, text="Sin diapositivas en esta categoría.",
                         font=ctk.CTkFont(size=12, slant="italic"), text_color=TXT_TERC).pack(pady=24)
            return
        for d in datos:
            fila = ctk.CTkFrame(body, fg_color=bg_fila, corner_radius=10)
            fila.pack(fill="x", pady=4)
            izq = ctk.CTkFrame(fila, fg_color="transparent")
            izq.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=9)
            ctk.CTkLabel(izq, text=f"Diapositiva {d['n']}", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#1E293B", anchor="w").pack(fill="x")
            zn = _zona(d["n"])
            sub = f"Real {_fmt(d['real'])} · Planeado {_fmt(d['ref'])}"
            if zn:
                sub += f" · {zn.capitalize()}"
            ctk.CTkLabel(izq, text=sub, font=ctk.CTkFont(size=10), text_color=TXT_SECOND,
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(fila, text=f"{'+' if d['pct'] > 0 else ''}{d['pct']}%",
                         font=ctk.CTkFont(size=16, weight="bold"), text_color=accent).pack(side="right", padx=(6, 14))

    _columna(0, "Diapositivas que duraron muy poco", COLOR_UNDER, poco, "#FCF4E6")
    _columna(1, "Diapositivas que duraron mucho", COLOR_OVER, mucho, "#FBEEE8")

    ctk.CTkFrame(modal, height=1, fg_color=BORDE).pack(fill="x")
    foot = ctk.CTkFrame(modal, fg_color="transparent")
    foot.pack(fill="x", padx=22, pady=(10, 16))
    ctk.CTkButton(foot, text="Entendido", height=38, corner_radius=8, fg_color=COLOR_GUINDA,
                  hover_color=COLOR_GUINDA_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
                  command=_cerrar).pack(fill="x")
    return modal