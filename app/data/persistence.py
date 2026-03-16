from app.data.database_manager import conectar_db
import uuid
from datetime import datetime

def registrar_presentacion(ruta_pptx, hash_archivo, total_slides, id_ua):
    conn = conectar_db()
    if not conn: return False, None
    
    cursor = conn.cursor()
    try:
        id_p = str(uuid.uuid4())
        id_v = str(uuid.uuid4())
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        # Insertamos usando la conexión estructurada
        cursor.execute("INSERT INTO Presentacion VALUES (?, ?, ?)", (id_p, id_ua, ruta_pptx))
        cursor.execute("INSERT INTO Historial_de_Versiones (id_version, id_presentacion, total_diapositivas, hash, fecha_carga) VALUES (?, ?, ?, ?, ?)", 
                       (id_v, id_p, total_slides, hash_archivo, fecha))
        
        conn.commit()
        return True, id_p
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return False, None
    finally:
        conn.close()