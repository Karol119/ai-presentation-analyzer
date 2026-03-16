from app.data.database_manager import conectar_db

def existe_hash_en_db(hash_archivo):
    conn = conectar_db()
    if not conn: return False
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM Historial_de_Versiones WHERE hash = ?", (hash_archivo,))
    existe = cursor.fetchone() is not None
    
    conn.close()
    return existe