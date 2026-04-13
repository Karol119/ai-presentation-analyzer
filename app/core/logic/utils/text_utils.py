import re

# Centralización de palabras funcionales [cite: 9]
STOPWORDS = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con",
    "contra","de","desde","en","entre","hacia","hasta","para","por","según",
    "sin","sobre","tras","y","e","ni","o","u","pero","sino","aunque","porque"
    # ... añade el resto aquí una sola vez
}

def limpiar_texto_basico(texto):
    """Normaliza espacios y saltos de línea."""
    return re.sub(r'\s+', ' ', texto).strip()