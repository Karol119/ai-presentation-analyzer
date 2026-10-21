# tests/presentacion/__init__.py
"""
Pruebas del modo de presentación en vivo (simulación de clase).

Esta suite valida el flujo que sigue un docente al exponer una presentación
ante el grupo: configuración de la sesión, ensamblaje del visor, navegación
entre diapositivas, proyección, cronómetros y generación del reporte de
tiempos.

A diferencia de `tests/e2e`, aquí el insumo principal son presentaciones
`.pptx` reales colocadas en `presentaciones/`, y la evidencia de cada corrida
se guarda en `reportes/<AAAAMMDD_HHMMSS>/`.
"""
