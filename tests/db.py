# ─────────────────────────────────────────────────────────────────────────────
# db.py  →  Capa de datos.
#           Cuando conectes tu BD real, solo edita estas funciones.
#           La interfaz llama a estas funciones y no necesita cambios.
# ─────────────────────────────────────────────────────────────────────────────

def get_all_subjects() -> list[str]:
    """
    Retorna TODAS las materias disponibles en la BD.
    Reemplazar con:  SELECT nombre FROM materias
    """
    return [f"Materia {i:02d}" for i in range(1, 13)]


def get_curriculum(subject: str) -> list[dict]:
    """
    Retorna el árbol de contenido de una materia.
    Reemplazar con queries reales, manteniendo el mismo formato de retorno:

        [
          {
            "unidad": "Unidad 1: ...",
            "temas": [
              {
                "tema": "1.1 ...",
                "subtemas": ["1.1.1 ...", "1.1.2 ..."]
              },
              ...
            ]
          },
          ...
        ]
    """
    # ── Datos dummy ──────────────────────────────────────────────────────────
    base = [
        {
            "unidad": "Unidad 1: Introducción",
            "temas": [
                {"tema": "1.1 Conceptos básicos",
                 "subtemas": ["1.1.1 Definiciones", "1.1.2 Historia", "1.1.3 Aplicaciones"]},
                {"tema": "1.2 Fundamentos",
                 "subtemas": ["1.2.1 Principios", "1.2.2 Modelos"]},
            ],
        },
        {
            "unidad": "Unidad 2: Desarrollo",
            "temas": [
                {"tema": "2.1 Metodologías",
                 "subtemas": ["2.1.1 Ágil", "2.1.2 Cascada"]},
                {"tema": "2.2 Herramientas",
                 "subtemas": ["2.2.1 Software", "2.2.2 Hardware"]},
            ],
        },
        {
            "unidad": "Unidad 3: Análisis",
            "temas": [
                {"tema": "3.1 Técnicas",
                 "subtemas": ["3.1.1 Cualitativo", "3.1.2 Cuantitativo"]},
            ],
        },
        {
            "unidad": "Unidad 4: Diseño",
            "temas": [
                {"tema": "4.1 Patrones",
                 "subtemas": ["4.1.1 MVC", "4.1.2 MVVM"]},
                {"tema": "4.2 Diagramas",
                 "subtemas": ["4.2.1 UML", "4.2.2 ER"]},
            ],
        },
        {
            "unidad": "Unidad 5: Implementación",
            "temas": [
                {"tema": "5.1 Lenguajes",
                 "subtemas": ["5.1.1 Python", "5.1.2 Java", "5.1.3 C++"]},
            ],
        },
        {
            "unidad": "Unidad 6: Evaluación",
            "temas": [
                {"tema": "6.1 Pruebas",
                 "subtemas": ["6.1.1 Unitarias", "6.1.2 Integración"]},
                {"tema": "6.2 Métricas",
                 "subtemas": ["6.2.1 Cobertura", "6.2.2 Rendimiento"]},
            ],
        },
    ]
    return base  # mismo contenido para todas las materias en el dummy