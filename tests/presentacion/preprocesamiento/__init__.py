# tests/presentacion/preprocesamiento/__init__.py
"""
Preprocesamiento de presentaciones para las pruebas de exposición en vivo.

Genera una predicción del tiempo que puede tomar presentar cada archivo
`.pptx`, inspirada en el tiempo de lectura estimado de los lectores de libros
electrónicos (palabras por minuto), pero ajustada a una exposición oral:

  * velocidad de habla didáctica (140 palabras por minuto por defecto),
  * texto visible + notas del orador,
  * pausas por diapositiva y por viñeta,
  * tiempo extra para imágenes, gráficos y tablas.

El resultado se escribe como un JSON junto a cada presentación, con el mismo
nombre base.
"""
