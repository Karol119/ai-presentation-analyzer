"""
recommendation_prompt.py — v3

Cambios:
  1. generar_prompt_recomendacion acepta max_chars para truncar contenido largo
  2. Se agrega instrucción de división cuando la slide está saturada
  3. Tabla de diagnóstico imprimible por consola
"""

_GUIA_SIMPLIFICACION = """
Para reducir la complejidad léxica usa palabras con menos sílabas:
  - "epistemológico" → "conceptual" o "teórico"
  - "decodificación" → "interpretación" o "lectura"  
  - "metacognitivo"  → "reflexivo" o "consciente"
  - "heurístico"     → "práctico" o "exploratorio"
  - Oraciones de máximo 15-20 palabras separadas por punto
  - Elimina subordinadas encadenadas (que... que... que...)
"""

_GUIA_ELEVACION = """
Para elevar la complejidad al nivel universitario:
  - Usa terminología técnica del área con precisión
  - Elabora ideas con contexto y ejemplos breves
  - Usa conectores académicos: "en consecuencia", "sin embargo", "por tanto"
  - Oraciones de 15-25 palabras con una subordinada simple
"""


def construir_contexto_metricas(score_slide):
    metricas      = score_slide.get("metricas", {})
    lineas_bien   = []
    lineas_mejorar = []
    icd_bien = wps_bien = False

    if "icd" in metricas:
        m = metricas["icd"]
        if m["estado"] == "BIEN":
            icd_bien = True
            lineas_bien.append(
                f"  - Complejidad textual: {m['valor']} ({m['zona']}) ✓ "
                "NO cambies el nivel de complejidad ni el vocabulario"
            )
        elif m["zona"] in ("simple", "muy simple"):
            lineas_mejorar.append(
                f"  - Complejidad (ICD {m['valor']} — {m['zona']}) → SIMPLIFICADA:\n"
                + _GUIA_ELEVACION
            )
        else:
            lineas_mejorar.append(
                f"  - Complejidad (ICD {m['valor']} — {m['zona']}) → MUY COMPLEJA:\n"
                + _GUIA_SIMPLIFICACION
                + "\n  Objetivo: comprensible para estudiante universitario sin vocabulario de posgrado."
            )

    if "wps" in metricas:
        m = metricas["wps"]
        if m["estado"] == "BIEN":
            wps_bien = True
            lineas_bien.append(
                f"  - Cantidad de texto: {m['palabras']} palabras ✓ "
                f"MANTÉN entre {max(m['palabras']-5,40)} y {min(m['palabras']+5,75)} palabras"
            )
        # Busca esta sección en construir_contexto_metricas:
        elif m.get("exceso", 0) > 50:
            lineas_mejorar.append(
                f" - Cantidad de texto: {m['palabras']} palabras (MUY SATURADA) → "
                f"Analiza si el contenido es demasiado extenso para una sola diapositiva. "
                f"Si es posible, resúmelo manteniendo la esencia entre 40-75 palabras. "
                f"Si consideras que se pierde información vital, indica en 'justificacion' que se sugiere dividir."
            )
        elif m.get("exceso", 0) > 0:
            lineas_mejorar.append(
                f"  - Cantidad de texto: {m['palabras']} palabras (EXCESO) → "
                f"Reduce a entre 40 y 75 palabras eliminando redundancias."
            )
        else:
            lineas_mejorar.append(
                f"  - Cantidad de texto: {m['palabras']} palabras (ESCASA) → "
                f"Amplía a entre 40 y 75 palabras con contexto o ejemplo breve."
            )

    if "hss" in metricas:
        m = metricas["hss"]
        if m["estado"] == "BIEN":
            lineas_bien.append(
                f"  - Título ✓ CONSERVA el título exactamente como está"
            )
        elif not m.get("tiene_titulo"):
            lineas_mejorar.append(
                "  - Título: FALTA → crea uno de 3-6 palabras que resuma el tema"
            )
        else:
            lineas_mejorar.append(
                "  - Título: no coherente → reformula para reflejar específicamente el contenido"
            )

    if "nts" in metricas:
        m = metricas["nts"]
        if m["estado"] == "BIEN":
            lineas_bien.append(
                "  - Continuidad narrativa ✓ NO cambies los términos que conectan con slides adyacentes"
            )
        elif m["estado"] == "MEJORAR":
            lineas_mejorar.append(
                "  - Continuidad: desconectada → incluye un concepto que conecte con el tema anterior/siguiente"
            )

    if wps_bien and not icd_bien and "icd" in metricas:
        lineas_bien.append(
            "  ⚠ IMPORTANTE: la cantidad de palabras ya es correcta. "
            "Solo cambia el vocabulario y estructura de oraciones, NO el número de palabras."
        )

    ctx = ""
    if lineas_bien:
        ctx += "CONSERVA — NO MODIFICAR BAJO NINGUNA CIRCUNSTANCIA:\n"
        ctx += "\n".join(lineas_bien) + "\n\n"
    if lineas_mejorar:
        ctx += "MEJORAR:\n"
        ctx += "\n".join(lineas_mejorar) + "\n"
    return ctx


_PROMPT = """Eres un asistente especializado en mejorar presentaciones académicas universitarias.

REGLAS ABSOLUTAS:
1. NO cambies el significado ni los conceptos del contenido original
2. NO inventes información que no esté en el contenido original  
3. CONSERVA exactamente lo marcado con ✓
4. Solo modifica lo marcado como MEJORAR
5. Responde SOLO con el JSON, sin texto antes ni después

CONTENIDO ORIGINAL:
Título: {titulo}
Cuerpo:
{contenido}

{contexto}

Responde con este JSON exacto:
{{
  "titulo_nuevo": "string",
  "contenido_nuevo": "string",
  "cambios_realizados": [],
  "justificacion": "string",
  "requiere_division_fisica": boolean  // <--- Añade esto
}}"""


def generar_prompt_recomendacion(slide_data, score_slide, max_chars=None):
    titulo    = slide_data.get("title", "").strip() or "(sin título)"
    contenido = "\n".join(slide_data.get("content", []))
    if max_chars and len(contenido) > max_chars:
        contenido = contenido[:max_chars] + "\n[... contenido truncado por longitud ...]"
    contexto = construir_contexto_metricas(score_slide)
    return _PROMPT.format(titulo=titulo, contenido=contenido, contexto=contexto)


# ── Tabla de diagnóstico ──────────────────────────────────────────────────────

def imprimir_tabla_diagnostico(scores_slides, icd_res, wps_res, hss_res, nts_res, recs):
    """
    Imprime la tabla completa de métricas por slide con el estado de recomendación.
    """
    icd_map = {r["slide_number"]: r for r in icd_res.get("resultados", [])}
    wps_map = {r["slide_number"]: r for r in wps_res.get("resultados", [])}
    hss_map = {r["slide_number"]: r for r in hss_res.get("resultados", [])}
    nts_map = {r["slide_number"]: r for r in nts_res.get("resultados", [])}
    rec_map = {r["slide_number"]: r for r in recs}

    HDR = (f"{'Slide':>5}  {'ICD':>5} {'Zona ICD':<13} "
           f"{'Pal':>4} {'WPS':<11} "
           f"{'HSS':>5} {'Coherencia':<13} "
           f"{'NTS':>5} {'Hilo':<12} "
           f"{'Score':>5}  Estado rec")
    print(f"\n{HDR}")
    print("─" * 110)

    for s in scores_slides:
        n   = s["slide_number"]
        ir  = icd_map.get(n, {})
        wr  = wps_map.get(n, {})
        hr  = hss_map.get(n, {})
        nr  = nts_map.get(n, {})
        rec = rec_map.get(n, {})

        icd_v = f"{ir['icd']:.2f}" if ir.get("calculable") else "  —  "
        icd_z = ir.get("zona", "—")
        pal   = str(wr.get("palabras", "—"))
        wps_z = wr.get("zona", "—")
        hss_v = f"{hr.get('hss_score',0):.1f}" if hr else "—"
        coh   = hr.get("coherencia","—") if hr else "—"
        nts_v = f"{nr.get('nts_score',0):.1f}" if nr else "—"
        nts_e = nr.get("estado","—") if nr else "—"
        sc    = f"{s['score']:.2f}"

        # Estado de la recomendación
        if not s.get("necesita_recomendacion"):
            estado_rec = "✓ OK"
        elif rec.get("omitida_razon"):
            estado_rec = "~ omitida"
        elif rec.get("sugerencia_division"):
            estado_rec = "⚠ dividir"
        elif rec.get("error"):
            estado_rec = f"✗ error"
        elif rec.get("necesitaba_rec"):
            estado_rec = "→ generada"
        else:
            estado_rec = "pendiente"

        # Marcar ICD irreducible
        icd_flag = " !" if s.get("metricas",{}).get("icd",{}).get("irreducible") else ""

        print(
            f"  [{n:02d}]  {icd_v:>5}{icd_flag} {icd_z:<13} "
            f"{pal:>4} {wps_z:<11} "
            f"{hss_v:>5} {coh:<13} "
            f"{nts_v:>5} {nts_e:<12} "
            f"{sc:>5}  {estado_rec}"
        )

    print()
    # Leyenda
    print("  ! = ICD irreducible (vocabulario técnico de posgrado)")
    print("  ~ = omitida (no es necesaria la recomendación)")
    print("  ⚠ = sugerencia de dividir la diapositiva")


# ── Resumen ───────────────────────────────────────────────────────────────────

_PROMPT_RESUMEN = """Eres un asistente que genera reportes pedagógicos para profesores universitarios.
Genera un resumen ejecutivo de máximo 4 oraciones.

Archivo: {nombre}
Diapositivas evaluadas: {total}
Score global: {score_global}/10 ({zona_global})
Métricas: ICD={icd_prom} ({icd_zona}), palabras/slide={pal_prom}, 
cobertura títulos={hss_cob}%, hilo narrativo={nts_prom}

Problemas:
{distribucion}

Menciona primero los aspectos positivos, luego los 1-2 problemas principales.
Usa lenguaje claro para el docente. No menciones nombres técnicos de métricas.
Responde SOLO con el texto del reporte."""


def generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts):
    dist = []
    if wps.get("slides_saturadas", 0):
        dist.append(f"- {wps['slides_saturadas']} diapositivas con exceso de texto")
    if wps.get("slides_escasas", 0):
        dist.append(f"- {wps['slides_escasas']} diapositivas con poco texto")
    if hss.get("slides_sin_titulo", 0):
        dist.append(f"- {hss['slides_sin_titulo']} diapositivas sin título")
    if hss.get("slides_no_coherentes", 0):
        dist.append(f"- {hss['slides_no_coherentes']} títulos no coherentes con el contenido")
    if nts.get("pares_rotura"):
        dist.append(f"- {len(nts['pares_rotura'])} rupturas de continuidad narrativa")

    return _PROMPT_RESUMEN.format(
        nombre=nombre,
        total=icd.get("slides_calculadas", 0),
        score_global=score_global["score_global"],
        zona_global=score_global["zona_global"],
        icd_prom=icd.get("icd_promedio","—"),
        icd_zona=icd.get("zona_promedio","—"),
        pal_prom=wps.get("palabras_promedio","—"),
        hss_cob=hss.get("cobertura_titulo","—"),
        nts_prom=nts.get("nts_promedio","—"),
        distribucion="\n".join(dist) if dist else "- Sin problemas mayores"
    )