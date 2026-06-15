import sqlite3

def imprimir_esquema(ruta_db: str):
    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tablas = cursor.fetchall()

    if not tablas:
        print("⚠️  No se encontraron tablas en la base de datos.")
        return

    print(f"📦 Base de datos: {ruta_db}")
    print(f"📊 Total de tablas: {len(tablas)}\n")
    print("=" * 50)

    for (nombre_tabla,) in tablas:
        print(f"\n🗂️  Tabla: {nombre_tabla}")
        print("-" * 50)

        cursor.execute(f"PRAGMA table_info('{nombre_tabla}');")
        columnas = cursor.fetchall()

        print(f"{'#':<4} {'Columna':<30} {'Tipo':<15} {'Nulo':<8} {'PK'}")
        print("-" * 50)

        for col in columnas:
            cid, nombre, tipo, not_null, default, pk = col
            nulo = "NO" if not_null else "YES"
            es_pk = "✅ PK" if pk else ""
            print(f"{cid:<4} {nombre:<30} {tipo:<15} {nulo:<8} {es_pk}")

        cursor.execute(f"PRAGMA foreign_key_list('{nombre_tabla}');")
        fks = cursor.fetchall()

        if fks:
            print(f"\n  🔗 Foreign Keys:")
            for fk in fks:
                _, _, tabla_ref, col_origen, col_ref, *_ = fk
                print(f"     {col_origen} → {tabla_ref}({col_ref})")

    print("\n" + "=" * 50)
    conn.close()


imprimir_esquema("ai_analyzer.db")