# app/core/logic/recommendation_prompt.py
"""
recommendation_prompt.py  — v2

Correcciones:
  1. Instrucción de ICD ahora especifica explícitamente usar palabras más cortas
     y oraciones más cortas, no solo "simplificar estructura"
  2. Cuando WPS está BIEN, la instrucción le prohíbe cambiar la cantidad de texto
  3. Se agrega el conteo de sílabas objetivo para guiar al LLM numéricamente
"""

# ── Vocabulario de referencia por nivel de complejidad ────────────────────────
# Le damos ejemplos concretos al LLM de qué tipo de palabras usar/evitar

_GUIA_SIMPLIFICACION = """
Para reducir la complejidad léxica, prefiere palabras con menos sílabas:
  - En lugar de "epistemológico" → "conceptual" o "teórico"
  - En lugar de "decodificación" → "interpretación" o "lectura"
  - En lugar de "metacognitivo"  → "reflexivo" o "consciente"
  - En lugar de "heurístico"     → "práctico" o "exploratorio"
  - Usa oraciones de máximo 15-20 palabras separadas por punto
  - Evita subordinadas encadenadas (que... que... que...)
"""

_GUIA_ELEVACION = """
Para elevar la complejidad al nivel universitario:
  - Usa terminología técnica del área con precisión
  - Elabora las ideas con contexto y explicación
  - Usa conectores académicos: "en consecuencia", "sin embargo", "por tanto"
  - Las oraciones pueden tener 15-25 palabras con subordinadas simples
"""


def construir_contexto_metricas(score_slide):
    metricas   = score_slide.get("metricas", {})
    lineas_bien    = []
    lineas_mejorar = []

    icd_bien = False
    wps_bien = False

    # ── ICD ──────────────────────────────────────────────────────────────────
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
            # complejo o muy complejo — este es el caso problemático
            lineas_mejorar.append(
                f"  - Complejidad (ICD {m['valor']} — {m['zona']}) → MUY COMPLEJA:\n"
                + _GUIA_SIMPLIFICACION
                + f"\n  El objetivo es que el texto sea comprensible para un estudiante universitario "
                  f"sin requerir vocabulario de posgrado especializado."
            )

    # ── WPS ──────────────────────────────────────────────────────────────────
    if "wps" in metricas:
        m = metricas["wps"]
        if m["estado"] == "BIEN":
            wps_bien = True
            lineas_bien.append(
                f"  - Cantidad de texto: {m['palabras']} palabras ({m['zona']}) ✓ "
                f"MANTÉN exactamente entre {max(m['palabras']-5, 40)} y {min(m['palabras']+5, 75)} palabras"
            )
        elif m.get("exceso", 0) > 0:
            lineas_mejorar.append(
                f"  - Cantidad de texto: {m['palabras']} palabras (EXCESO, máximo 75) → "
                f"Reduce a entre 40 y 75 palabras eliminando redundancias. "
                f"Conserva los conceptos clave."
            )
        else:
            lineas_mejorar.append(
                f"  - Cantidad de texto: {m['palabras']} palabras (ESCASA, mínimo 40) → "
                f"Amplía a entre 40 y 75 palabras agregando contexto o explicación breve."
            )

    # ── HSS ──────────────────────────────────────────────────────────────────
    if "hss" in metricas:
        m = metricas["hss"]
        if m["estado"] == "BIEN":
            lineas_bien.append(
                f"  - Título: '{score_slide.get('titulo','')}' ✓ "
                "CONSERVA el título exactamente como está"
            )
        elif not m.get("tiene_titulo"):
            lineas_mejorar.append(
                "  - Título: FALTA → crea un título de 3 a 6 palabras que resuma el tema principal"
            )
        else:
            lineas_mejorar.append(
                "  - Título: no coherente con el contenido → "
                "reformula el título para que refleje específicamente lo que explica el cuerpo"
            )

    # ── NTS ──────────────────────────────────────────────────────────────────
    if "nts" in metricas:
        m = metricas["nts"]
        if m["estado"] == "BIEN":
            lineas_bien.append(
                "  - Continuidad narrativa ✓ "
                "NO cambies los términos clave que conectan con las slides adyacentes"
            )
        elif m["estado"] == "MEJORAR":
            lineas_mejorar.append(
                "  - Continuidad: desconectada de slides adyacentes → "
                "incluye al menos un concepto puente que conecte el tema con las slides anterior y siguiente"
            )

    # Restricción adicional: si WPS está bien y solo ICD necesita mejora,
    # reforzar que NO debe cambiar la cantidad de palabras
    if wps_bien and not icd_bien and "icd" in metricas:
        lineas_bien.append(
            "  ⚠ IMPORTANTE: la cantidad de palabras es correcta. "
            "Solo cambia el vocabulario y la estructura de las oraciones, "
            "NO el número de palabras."
        )

    contexto = ""
    if lineas_bien:
        contexto += "ASPECTOS QUE DEBES CONSERVAR — NO MODIFICAR BAJO NINGUNA CIRCUNSTANCIA:\n"
        contexto += "\n".join(lineas_bien) + "\n\n"
    if lineas_mejorar:
        contexto += "ASPECTOS QUE DEBES MEJORAR:\n"
        contexto += "\n".join(lineas_mejorar) + "\n"

    return contexto


# ── Prompt principal ──────────────────────────────────────────────────────────

_PROMPT_RECOMENDACION = """Eres un asistente especializado en mejorar presentaciones académicas universitarias.
Tu tarea es reestructurar el contenido de una diapositiva siguiendo instrucciones exactas.

REGLAS ABSOLUTAS — INCUMPLIRLAS INVALIDA TU RESPUESTA:
1. NO cambies el significado ni los conceptos del contenido original
2. NO inventes información que no esté en el contenido original
3. CONSERVA EXACTAMENTE lo marcado como "✓ CONSERVA" o "✓ NO cambies"
4. Solo modifica lo marcado como "MEJORAR"
5. Responde SOLO con el JSON, sin texto antes ni después

CONTENIDO ORIGINAL:
Título: {titulo}
Cuerpo:
{contenido}

ANÁLISIS Y RESTRICCIONES:
{contexto_metricas}

Responde con este JSON exacto:
{{
  "titulo_nuevo": "string",
  "contenido_nuevo": "string",
  "cambios_realizados": ["descripción de cada cambio aplicado"],
  "justificacion": "una oración"
}}"""


def generar_prompt_recomendacion(slide_data, score_slide):
    titulo    = slide_data.get("title", "").strip() or "(sin título)"
    contenido = "\n".join(slide_data.get("content", []))
    contexto  = construir_contexto_metricas(score_slide)

    return _PROMPT_RECOMENDACION.format(
        titulo=titulo,
        contenido=contenido,
        contexto_metricas=contexto
    )


# ── Prompt de resumen ─────────────────────────────────────────────────────────

_PROMPT_RESUMEN = """Eres un asistente que genera reportes pedagógicos para profesores universitarios.
Analiza los resultados de evaluación y genera un resumen ejecutivo de máximo 4 oraciones.

Nombre del archivo: {nombre}
Diapositivas evaluadas: {total}
Score global: {score_global}/10 ({zona_global})

Resultados: ICD={icd_prom} ({icd_zona}), palabras/slide={pal_prom}, 
cobertura títulos={hss_cob}%, hilo narrativo={nts_prom}

Problemas detectados:
{distribucion}

Instrucción: menciona primero los aspectos positivos, luego los 1-2 problemas más importantes.
Usa lenguaje profesional pero claro. No menciones nombres técnicos de métricas.
Responde SOLO con el texto del reporte."""


def generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts):
    distribucion = []
    if wps.get("slides_saturadas", 0):
        distribucion.append(f"- {wps['slides_saturadas']} diapositivas con exceso de texto")
    if wps.get("slides_escasas", 0):
        distribucion.append(f"- {wps['slides_escasas']} diapositivas con poco texto")
    if hss.get("slides_sin_titulo", 0):
        distribucion.append(f"- {hss['slides_sin_titulo']} diapositivas sin título")
    if hss.get("slides_no_coherentes", 0):
        distribucion.append(f"- {hss['slides_no_coherentes']} títulos no coherentes con el contenido")
    if nts.get("pares_rotura"):
        distribucion.append(f"- {len(nts['pares_rotura'])} rupturas de continuidad narrativa")

    return _PROMPT_RESUMEN.format(
        nombre=nombre,
        total=icd.get("slides_calculadas", 0),
        score_global=score_global["score_global"],
        zona_global=score_global["zona_global"],
        icd_prom=icd.get("icd_promedio", "—"),
        icd_zona=icd.get("zona_promedio", "—"),
        pal_prom=wps.get("palabras_promedio", "—"),
        hss_cob=hss.get("cobertura_titulo", "—"),
        nts_prom=nts.get("nts_promedio", "—"),
        distribucion="\n".join(distribucion) if distribucion else "- Sin problemas mayores detectados"
    )