# Reportes de pruebas

Cada ejecución de la suite crea una subcarpeta con marca de tiempo:

```
reportes/
└── 20261019_143000/
    ├── resumen.txt          # Entorno, conteos y resultado global
    ├── <modulo>.txt         # Salida cruda (stdout + stderr) por módulo
    └── detalle.json         # Resultados estructurados por caso (opcional)
```

Los reportes son evidencia generada automáticamente y no se versionan, salvo
que se solicite conservar una corrida específica:

```bash
git add -f tests/presentacion/reportes/20261019_143000/
```
