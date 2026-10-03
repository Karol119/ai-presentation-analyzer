# app/data/persistence.py
import sqlite3
import uuid
import json
import os
import shutil
from datetime import datetime
from app.data.database_manager import conectar_db
from app.core.logic.slide_processor import generar_miniatura, generar_pdf

def registrar_presentacion(ruta_origen, hash_unico, num_diapositivas, id_materia):
    """Guarda archivos físicos y registra la presentación (v1) en la BD."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        # Obtener nombre de materia para la carpeta
        cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE id_unidad_aprendizaje = ?", (id_materia,))
        resultado = cursor.fetchone()
        if not resultado: return False, "La materia no existe."
        
        nombre_materia = resultado[0]
        nombre_archivo = os.path.basename(ruta_origen)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        os.makedirs(carpeta_destino, exist_ok=True)
        
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        shutil.copy2(ruta_origen, ruta_destino)

        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        ruta_thumb = os.path.join(carpeta_destino, f"{nombre_sin_ext}_thumb.png")
        generar_miniatura(ruta_destino, ruta_thumb)

        ruta_pdf = os.path.join(carpeta_destino, f"{nombre_sin_ext}.pdf")
        generar_pdf(ruta_destino, ruta_pdf)

        id_presentacion = str(uuid.uuid4())
        cursor.execute("INSERT INTO Presentacion VALUES (?, ?, ?)", (id_presentacion, id_materia, nombre_archivo))

        id_version = str(uuid.uuid4())
        fecha = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO Historial_de_Versiones 
            (id_version, id_presentacion, numero_version, fecha_carga, total_diapositivas, hash, ruta, ruta_miniatura, ruta_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, 1, fecha, num_diapositivas, hash_unico, ruta_destino, ruta_thumb, ruta_pdf))

        conn.commit()
        return True, id_presentacion
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def eliminar_presentacion_completa(nombre_presentacion, id_materia):
    """Borra físicamente archivos y lógicamente registros en cascada manual."""
    conn = conectar_db()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT hv.numero_version, hv.ruta, hv.ruta_miniatura, hv.ruta_pdf
            FROM Historial_de_Versiones hv
            JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
            WHERE p.presentacion = ? AND p.id_unidad_aprendizaje = ?
        """, (nombre_presentacion, id_materia))
        filas = cursor.fetchall()
        if not filas: return False

        id_pres = cursor.execute(
            "SELECT id_presentacion FROM Presentacion WHERE presentacion = ? AND id_unidad_aprendizaje = ?",
            (nombre_presentacion, id_materia)
        ).fetchone()[0]

        # Jerarquía de borrado: Analisis -> Subtemas -> Historial -> Presentacion
        cursor.execute("DELETE FROM Analisis WHERE id_version IN (SELECT id_version FROM Historial_de_Versiones WHERE id_presentacion = ?)", (id_pres,))
        cursor.execute("DELETE FROM Presentacion_Subtema WHERE id_presentacion = ?", (id_pres,))
        cursor.execute("DELETE FROM Historial_de_Versiones WHERE id_presentacion = ?", (id_pres,))
        cursor.execute("DELETE FROM Presentacion WHERE id_presentacion = ?", (id_pres,))

        # Limpieza física de TODAS las versiones (pptx, miniaturas, pdf, json)
        nombre_materia = None
        for numero_version, r_pptx, r_thumb, r_pdf in filas:
            for r in (r_pptx, r_thumb, r_pdf):
                if r and os.path.exists(r): os.remove(r)
            if r_pdf:
                carpeta = os.path.dirname(r_pdf)
                nombre_materia = os.path.basename(carpeta)
                # JSON de análisis junto al pdf
                base = os.path.splitext(r_pdf)[0]
                ruta_json = base + "_analysis.json"
                if os.path.exists(ruta_json): os.remove(ruta_json)
                # Algunas versiones guardan el json como <base_pptx>_analysis.json
                if r_pptx:
                    ruta_json2 = os.path.splitext(r_pptx)[0] + "_analysis.json"
                    if os.path.exists(ruta_json2): os.remove(ruta_json2)
                # PPTX optimizado en Documentos
                try:
                    ruta_doc = os.path.join(
                        os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer',
                        nombre_materia,
                        f"{os.path.splitext(nombre_presentacion)[0]}_v{numero_version}.pptx"
                    )
                    if os.path.exists(ruta_doc): os.remove(ruta_doc)
                except Exception:
                    pass

        # Si la carpeta de la materia en storage quedó vacía, eliminarla
        try:
            carpeta_presentaciones = os.path.dirname(r_pptx) if filas and filas[0][1] else None
            if carpeta_presentaciones and os.path.isdir(carpeta_presentaciones) and not os.listdir(carpeta_presentaciones):
                os.rmdir(carpeta_presentaciones)
        except Exception:
            pass

        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        conn.close()

def registrar_analisis_completo(id_version, json_string):
    """Persiste el resultado JSON de la IA en la base de datos."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO Analisis (id_version, numero_diapositiva, resultado) VALUES (?, 0, ?)", (id_version, json_string))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def actualizar_estado_analisis(nombre_presentacion, id_materia, estado=1):
    """Cambia el estatus de análisis de la versión activa de una presentación."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        query = """
            UPDATE Historial_de_Versiones SET analisis = ? 
            WHERE id_presentacion = (
                SELECT id_presentacion FROM Presentacion 
                WHERE presentacion = ? AND id_unidad_aprendizaje = ?
            ) AND numero_version = (
                SELECT MAX(numero_version) FROM Historial_de_Versiones hv2
                WHERE hv2.id_presentacion = Historial_de_Versiones.id_presentacion
            )
        """
        cursor.execute(query, (estado, nombre_presentacion, id_materia))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def actualizar_estado_materia(nombre_materia, activa):
    """Habilita o deshabilita una materia en el catálogo."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        val = 1 if activa else 0
        cursor.execute("UPDATE Unidad_de_Aprendizaje SET activa = ? WHERE unidad_aprendizaje = ?", (val, nombre_materia))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally: conn.close()

def eliminar_datos_materia_cascada(id_materia):
    """Limpia todos los registros vinculados a una materia para desactivación total."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM Analisis WHERE id_version IN (
                SELECT hv.id_version FROM Historial_de_Versiones hv
                JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
                WHERE p.id_unidad_aprendizaje = ?
            )
        """, (id_materia,))
        cursor.execute("DELETE FROM Historial_de_Versiones WHERE id_presentacion IN (SELECT id_presentacion FROM Presentacion WHERE id_unidad_aprendizaje = ?)", (id_materia,))
        cursor.execute("DELETE FROM Presentacion WHERE id_unidad_aprendizaje = ?", (id_materia,))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally: conn.close()

def registrar_nueva_version(id_presentacion, ruta_origen, hash_unico, num_diapositivas, nueva_version, id_materia):
    """Guarda archivos físicos y registra una nueva versión manteniendo intacta la tabla Presentacion."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        # 1. Obtener nombre de materia para la ruta
        cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE id_unidad_aprendizaje = ?", (id_materia,))
        resultado = cursor.fetchone()
        if not resultado: return False, "La materia no existe."
        nombre_materia = resultado[0]
        
        # 2. Generar nombres físicos con sufijo _vX para no sobrescribir en disco
        nombre_archivo_original = os.path.basename(ruta_origen)
        nombre_sin_ext, ext = os.path.splitext(nombre_archivo_original)
        nombre_archivo_fisico = f"{nombre_sin_ext}_v{nueva_version}{ext}"
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        os.makedirs(carpeta_destino, exist_ok=True)
        
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo_fisico)
        shutil.copy2(ruta_origen, ruta_destino)

        # 3. Generar PDF y Miniatura
        ruta_thumb = os.path.join(carpeta_destino, f"{nombre_sin_ext}_v{nueva_version}_thumb.png")
        generar_miniatura(ruta_destino, ruta_thumb)

        ruta_pdf = os.path.join(carpeta_destino, f"{nombre_sin_ext}_v{nueva_version}.pdf")
        generar_pdf(ruta_destino, ruta_pdf)

        # 4. Insertar en Historial_de_Versiones respetando el esquema original
        id_version = str(uuid.uuid4())
        fecha = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO Historial_de_Versiones 
            (id_version, id_presentacion, numero_version, analisis, fecha_carga, total_diapositivas, hash, ruta, ruta_miniatura, ruta_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, nueva_version, 0, fecha, num_diapositivas, hash_unico, ruta_destino, ruta_thumb, ruta_pdf))

        conn.commit()
        return True, "Nueva versión registrada con éxito."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def actualizar_metricas_version(id_version, calificacion, recomendacion):
    """Actualiza los campos de calificación y recomendación de una versión específica."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        query = """
            UPDATE Historial_de_Versiones 
            SET calificacion_presentacion = ?, 
                recomendacion_presentacion = ?
            WHERE id_version = ?
        """
        cursor.execute(query, (calificacion, recomendacion, id_version))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al actualizar métricas: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def actualizar_reporte_tiempo_db(id_version, texto_reporte):
    """Guarda el texto crudo del reporte de tiempo en la base de datos."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Historial_de_Versiones SET reporte_tiempo = ? WHERE id_version = ?", (texto_reporte, id_version))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al guardar tiempo: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()