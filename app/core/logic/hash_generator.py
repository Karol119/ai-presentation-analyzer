import hashlib

def generar_hash_archivo(ruta_archivo):
    """Genera una firma única SHA-256 del archivo sin moverlo ni guardarlo."""
    sha256_hash = hashlib.sha256()
    # Leemos en binario ("rb")
    with open(ruta_archivo, "rb") as f:
        # Leemos en bloques para no saturar la memoria RAM
        for bloque in iter(lambda: f.read(4096), b""):
            sha256_hash.update(bloque)
    return sha256_hash.hexdigest()