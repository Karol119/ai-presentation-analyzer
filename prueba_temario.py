import json

from app.data.queries import obtener_temario_materia


materia = "Administración de Servicios en Red"

temario = obtener_temario_materia(materia)

print(json.dumps(
    temario,
    ensure_ascii=False,
    indent=2
))