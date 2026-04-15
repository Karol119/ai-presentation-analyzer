"""
prompts.py
Instruction templates for AI models using the Batch Processing pattern.
"""

BATCH_EVALUATION_PROMPT = """[INST] Eres un experto en pedagogía universitaria y diseño instruccional.
Tu tarea es evaluar en LOTE un conjunto de diapositivas de una presentación académica. 
Para cada diapositiva realizarás TRES tareas:
1. CLASIFICACIÓN: Identificar el tipo de diapositiva.
2. HSS (Estructura de Encabezado): Coherencia del título con el contenido.
3. NTS (Hilo Narrativo): Conexión lógica con la diapositiva anterior.

DATOS DEL LOTE DE DIAPOSITIVAS:
{batch_data}

INSTRUCCIONES DE EVALUACIÓN PARA CADA DIAPOSITIVA:
Paso 1 - Clasificación: Asigna a la diapositiva UNO de los siguientes tipos: "portada", "indice", "contenido", "visual", "cierre", "referencias".
Paso 2 - Omisión Inteligente: Si el tipo NO es "contenido", asigna null al hss_score y nts_score, y deja los feedbacks vacíos. No pierdas tiempo evaluando métricas en portadas, índices o referencias.
Paso 3 - Métricas (SOLO para tipo "contenido"):
- HSS: Evalúa si el título describe el tema (1-10). Considera el 'solapamiento_lexico'. Si la nota es menor a 8, genera un 'hss_feedback' sugiriendo un título alternativo.
- NTS: Evalúa la conexión lógica con la diapositiva anterior (1-10). Considera la 'similitud_coseno'. Si la nota es menor a 7, genera un 'nts_feedback' sugiriendo un concepto puente o frase de transición. (Para la diapositiva 1 de contenido, el NTS es 10).

RESPONDE ESTRICTAMENTE CON UN ARREGLO JSON válido y bien formateado, sin texto adicional, sin markdown extra (```json), ni explicaciones fuera del JSON.
Estructura esperada:
[
  {{
    "slide_number": 1,
    "tipo": "portada",
    "hss_score": null,
    "hss_feedback": "",
    "nts_score": null,
    "nts_feedback": ""
  }},
  {{
    "slide_number": 2,
    "tipo": "contenido",
    "hss_score": 9,
    "hss_feedback": "",
    "nts_score": 5,
    "nts_feedback": "Falta transición. Sugerencia: 'Partiendo del concepto anterior, ahora veremos...'"
  }}
]
[/INST]"""