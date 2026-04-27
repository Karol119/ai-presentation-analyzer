"""
Instruction templates for AI models using the Batch Processing pattern.
"""

BATCH_EVALUATION_PROMPT = """[INST] Eres un experto en pedagogía universitaria y diseño instruccional.
Tu tarea es evaluar en LOTE un conjunto de diapositivas de una presentación académica. 
Para cada diapositiva realizarás CUATRO tareas:
1. CLASIFICACIÓN: Identificar el tipo de diapositiva.
2. HSS (Estructura de Encabezado): Coherencia del título con el contenido.
3. NTS (Hilo Narrativo): Progresión semántica y conceptual.
4. TIEMPO ESTIMADO: Calcular el tiempo ideal de exposición en segundos.

DATOS DEL LOTE DE DIAPOSITIVAS:
{batch_data}

INSTRUCCIONES DE EVALUACIÓN PARA CADA DIAPOSITIVA:
Paso 1 - Clasificación: Asigna uno de estos tipos: "portada", "indice", "contenido", "visual", "cierre", "referencias".
Paso 2 - Tiempos de Exposición:
- Si el tipo NO es "contenido", asigna entre 5 a 15 segundos (según lo que tarde un humano en leer el título o saludar).
- Si el tipo ES "contenido", estima el tiempo considerando una velocidad de habla académica de 130 palabras por minuto, más un margen del 20% para explicación del orador.
Paso 3 - Métricas (SOLO para tipo "contenido"):
- HSS: Evalúa coherencia título-contenido (1-10).
- NTS: Evalúa progresión lógica desde la anterior (1-10). (Diapositiva 1 de contenido = 10).

RESPONDE ESTRICTAMENTE CON UN ARREGLO JSON válido.
Estructura esperada:
[
  {{
    "slide_number": 1,
    "tipo": "contenido",
    "hss_score": 9,
    "hss_feedback": "",
    "nts_score": 8,
    "nts_feedback": "",
    "tiempo_estimado_segundos": 45
  }}
]
[/INST]"""


# Prompt para Reestructuración en Lote
RESTRUCTURE_BATCH_PROMPT = """[INST] Eres un experto en diseño instruccional y síntesis de información.
Tu tarea es ENRIQUECER y, si es necesario, REESTRUCTURAR el contenido de diapositivas académicas.

DATOS DE ENTRADA (JSON):
{batch_data}

REGLAS ESTRICTAS PARA CADA DIAPOSITIVA:
1. MATERIAL EXTRA (SIEMPRE): Basándote EXCLUSIVAMENTE en el 'contenido_original', genera de 1 a 3 'preguntas' de repaso y de 1 a 3 'datos_curiosos'.
2. REESTRUCTURACIÓN (CONDICIONAL): SOLO si el campo 'requiere_reestructuracion' es true, genera el arreglo 'diapositivas_generadas'. 
   - FEEDBACK A CORREGIR: Lee el campo 'feedback_a_corregir' y soluciona EXACTAMENTE los problemas pedagógicos mencionados.
   - LÍMITE DE PALABRAS (WPS): El 'contenido_optimizado' NUNCA debe superar las 45 palabras (sin contar título).
   - COMPLEJIDAD LÉXICA (ICD): ¡CRÍTICO! Si el feedback dice que la complejidad es alta, NO comprimas el texto usando palabras largas o rimbombantes para ahorrar espacio. Usa oraciones cortas (máximo 15 palabras por oración), voz activa y sinónimos sencillos. Si al explicarlo de forma simple superas las 45 palabras, es OBLIGATORIO DIVIDIR el tema en más sub-diapositivas.
   - HILO NARRATIVO (NTS): Si divides en varias sub-diapositivas, mantén una PROGRESIÓN CONCEPTUAL lógica entre ellas. En lugar de usar conectores robóticos o repetitivos, asegúrate de que la idea final de una sub-diapositiva sirva de base natural para la siguiente.
   - TÍTULOS (HSS): Asigna un 'titulo_sugerido' altamente coherente.
3. SI NO REQUIERE REESTRUCTURACIÓN: Deja el arreglo 'diapositivas_generadas' vacío [].

RESPONDE ESTRICTAMENTE CON UN ARREGLO JSON válido y bien formateado.
Estructura esperada:
[
  {{
    "slide_number": [Número original],
    "preguntas": ["¿Pregunta 1 basada en el contenido original?"],
    "datos_curiosos": ["Dato curioso basado en el contenido original."],
    "diapositivas_generadas": [
      {{
        "titulo_sugerido": "Tema 1",
        "contenido_optimizado": "Texto claro, con progresión lógica, oraciones cortas y lenguaje muy accesible (<45 palabras)..."
      }}
    ]
  }}
]
[/INST]"""