# app/data/persistence.py
import sqlite3
import uuid
import json
import os
import re
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
        cursor.execute(
            "INSERT INTO Presentacion (id_presentacion, id_unidad_aprendizaje, presentacion) VALUES (?, ?, ?)",
            (id_presentacion, id_materia, nombre_archivo),
        )

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

# Sufijos válidos que la app GENERA a partir del nombre de una presentación
# (base sin extensión): archivos/fisicos propios y derivados de sus versiones.
_RE_DERIVADOS = re.compile(
    r"^(_v\d+)*(?:\.pptx|\.pdf|_thumb\.png|_analysis(?:-v2)?\.json)$",
    re.IGNORECASE,
)

def _es_derivado_de(nombre_archivo, base):
    """
    Indica si `nombre_archivo` es un recurso de la presentación cuyo nombre
    base (sin extensión) es `base`. Ej.: base 'Examen' reconoce
    'Examen.pptx', 'Examen.pdf', 'Examen_thumb.png', 'Examen_analysis.json',
    'Examen_v2_thumb.png', 'Examen_v1_v2_analysis.json'...
    La comparación es exacta tras el base (los nombres de OTRAS presentaciones
    que empiecen igual NO cuentan como propios).
    """
    if not base:
        return False
    nombre_lower = nombre_archivo.lower()
    base_lower = base.lower()
    if not nombre_lower.startswith(base_lower):
        return False
    cadena = nombre_lower[len(base_lower):]
    return bool(_RE_DERIVADOS.match(cadena))


def _referenciados_y_bases_vivas(conn):
    """
    Devuelve (rutas_db, bases_por_materia):
      - rutas_db: rutas absolutas (normalizadas y en minúsculas) de los
        archivos físicos guardados en Historial_de_Versiones (pptx, miniatura,
        pdf) de las versiones VIVAS.
      - bases_por_materia: {materia: [base_sin_ext, ...]} de las
        presentaciones registradas (visibles u ocultas) por materia.
    """
    cursor = conn.cursor()
    rutas_db = set()
    for columna in ("ruta", "ruta_miniatura", "ruta_pdf"):
        for (r,) in cursor.execute(
            f"SELECT {columna} FROM Historial_de_Versiones WHERE {columna} IS NOT NULL"
        ):
            try:
                rutas_db.add(os.path.abspath(r).lower())
            except Exception:
                pass
    bases_por_materia = {}
    filas = cursor.execute("""
        SELECT u.unidad_aprendizaje, p.presentacion
        FROM Presentacion p
        JOIN Unidad_de_Aprendizaje u ON p.id_unidad_aprendizaje = u.id_unidad_aprendizaje
    """).fetchall()
    for materia, nombre_presentacion in filas:
        bases_por_materia.setdefault(materia, []).append(
            os.path.splitext(nombre_presentacion)[0]
        )
    return rutas_db, bases_por_materia


def limpiar_huerfanos_presentaciones():
    """
    LIMPIEZA DE RECURSOS HUÉRFANOS (archivos de presentaciones que ya NO están
    registradas en la BD, p. ej. borradas por versiones anteriores de la app
    que solo eliminaban registros). Recorre:

      - storage/presentaciones/<materia>/  (pptx, pdf, miniatura, json de análisis)
      - Documentos/AI Presentation Analyzer/<materia>/  (PPTX mejorados)
    Regla: un archivo se conserva SI (a) su ruta está registrada en la BD, o
    (b) su nombre es un derivado legítimo de una presentación VIVA de esa
    misma materia. Todo lo demás es huérfano y se elimina con registro en
    consola. Devuelve la cantidad de archivos eliminados.
    """
    eliminados = []
    conn = conectar_db()
    try:
        rutas_db, bases_por_materia = _referenciados_y_bases_vivas(conn)
    finally:
        conn.close()

    raiz_proyecto = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # --- storage/presentaciones/<materia> ---
    raiz_storage = os.path.join(raiz_proyecto, "storage", "presentaciones")
    if os.path.isdir(raiz_storage):
        for materia in os.listdir(raiz_storage):
            carpeta = os.path.join(raiz_storage, materia)
            if not os.path.isdir(carpeta):
                continue
            bases_vivas = bases_por_materia.get(materia, [])
            for archivo in os.listdir(carpeta):
                ruta = os.path.join(carpeta, archivo)
                if not os.path.isfile(ruta):
                    continue
                if os.path.abspath(ruta).lower() in rutas_db:
                    continue
                if any(_es_derivado_de(archivo, b) for b in bases_vivas):
                    continue
                try:
                    os.remove(ruta)
                    eliminados.append(ruta)
                    print(f"[huerfanos] Eliminado: {ruta}")
                except Exception as e:
                    print(f"[huerfanos] No se pudo eliminar {ruta}: {e}")
            try:
                if not os.listdir(carpeta):
                    os.rmdir(carpeta)
            except Exception:
                pass

    # --- Documentos/AI Presentation Analyzer/<materia> (PPTX mejorados) ---
    ruta_docs = os.path.join(
        os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer'
    )
    if os.path.isdir(ruta_docs):
        for materia in os.listdir(ruta_docs):
            carpeta = os.path.join(ruta_docs, materia)
            if not os.path.isdir(carpeta):
                continue
            bases_vivas = bases_por_materia.get(materia, [])
            for archivo in os.listdir(carpeta):
                ruta = os.path.join(carpeta, archivo)
                if not os.path.isfile(ruta):
                    continue
                if any(_es_derivado_de(archivo, b) for b in bases_vivas):
                    continue
                try:
                    os.remove(ruta)
                    eliminados.append(ruta)
                    print(f"[huerfanos] Eliminado: {ruta}")
                except Exception as e:
                    print(f"[huerfanos] No se pudo eliminar {ruta}: {e}")
            try:
                if not os.listdir(carpeta):
                    os.rmdir(carpeta)
            except Exception:
                pass

    return len(eliminados)


def eliminar_presentacion_completa(nombre_presentacion, id_materia):
    """
    Borra registros en cascada (BD) y luego todos los recursos físicos de la
    presentación en disco (storage + Documentos).

    Orden deliberado: PRIMERO se hace commit de la BD y DESPUÉS se toca el
    disco. Así un fallo físico (archivo bloqueado, permisos, OneDrive) nunca
    deja la BD sin registros ni revierte el borrado del usuario: los archivos
    restantes quedarán como huérfanos y los limpia el barrido del arranque.
    """
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
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[borrado] Error al eliminar registros de la BD: {e}")
        return False
    finally:
        conn.close()

    # ================= LIMPIEZA FÍSICA (la BD ya quedó eliminada) ============
    def _borrar_seguro(ruta, motivo=""):
        try:
            if ruta and os.path.exists(ruta):
                os.remove(ruta)
                return True
        except Exception as e:
            print(f"[borrado] No se pudo eliminar ({motivo}) {ruta}: {e}")
        return False

    bases_presentacion = set()
    directorios_version = set()
    carpeta_presentaciones = None
    for numero_version, r_pptx, r_thumb, r_pdf in filas:
        for r in (r_pptx, r_thumb, r_pdf):
            _borrar_seguro(r, "versión")
        if r_pdf:
            carpeta = os.path.dirname(r_pdf)
            nombre_materia = os.path.basename(carpeta)
            # JSON de análisis junto al pdf
            base = os.path.splitext(r_pdf)[0]
            _borrar_seguro(base + "_analysis.json", "json de análisis")
            # Algunas versiones guardan el json como <base_pptx>_analysis.json
            if r_pptx:
                _borrar_seguro(os.path.splitext(r_pptx)[0] + "_analysis.json", "json de análisis (pptx)")
            # PPTX optimizado en Documentos
            try:
                ruta_doc = os.path.join(
                    os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer',
                    nombre_materia,
                    f"{os.path.splitext(nombre_presentacion)[0]}_v{numero_version}.pptx"
                )
                _borrar_seguro(ruta_doc, "PPTX optimizado en Documentos")
            except Exception:
                pass
        # Recolectar bases y carpetas de ESTA presentación para el barrido
        # de derivados (abajo): cubre archivos cuyo patrón de nombre derivó
        # del PPTX/PDF aunque la BD no registrara su ruta concreta.
        for r in (r_pptx, r_thumb, r_pdf):
            if not r:
                continue
            try:
                bases_presentacion.add(os.path.splitext(os.path.basename(r))[0])
                directorios_version.add(os.path.dirname(r))
                carpeta_presentaciones = os.path.dirname(r)
            except Exception:
                pass

    # Barrido de derivados por patrón: cualquier archivo de la carpeta de
    # la versión que derive del nombre de ESTA presentación se elimina,
    # aunque la BD no tuviera su ruta (p. ej. generados sin registro).
    for directorio in directorios_version:
        if not directorio or not os.path.isdir(directorio):
            continue
        for archivo in os.listdir(directorio):
            if os.path.isdir(os.path.join(directorio, archivo)):
                continue
            if any(_es_derivado_de(archivo, b) for b in bases_presentacion):
                _borrar_seguro(os.path.join(directorio, archivo), "derivado")

    # Si la carpeta de la presentación en storage quedó vacía, eliminarla
    try:
        if carpeta_presentaciones and os.path.isdir(carpeta_presentaciones) and not os.listdir(carpeta_presentaciones):
            os.rmdir(carpeta_presentaciones)
    except Exception:
        pass

    return True

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

def actualizar_visibilidad_presentacion(nombre_presentacion, id_materia, visible):
    """Marca una presentación como visible (1) u oculta (0) sin borrar sus datos."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE Presentacion SET visible = ? WHERE presentacion = ? AND id_unidad_aprendizaje = ?",
            (1 if visible else 0, nombre_presentacion, id_materia)
        )
        conn.commit()
        return cursor.rowcount > 0
    except:
        conn.rollback()
        return False
    finally: conn.close()

def mostrar_todas_presentaciones_materia(id_materia):
    """Restaura la visibilidad de todas las presentaciones de una materia."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Presentacion SET visible = 1 WHERE id_unidad_aprendizaje = ?", (id_materia,))
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