import sqlite3
import os
import uuid

def generar_id():
    """Genera un UUID de 32 caracteres como texto"""
    return str(uuid.uuid4())

def poblar_base_de_datos_uuid():
    # Ruta adaptada a la raíz de tu proyecto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "storage", "db", "ai_analyzer.db")
    
    if not os.path.exists(db_path):
        print(f"❌ Error: No se encontró la base de datos en {db_path}")
        print("Asegúrate de ejecutar tu generador de base de datos primero.")
        return

    # --- DATOS COMPLETOS DE LAS DOS MATERIAS ---
    materias_a_cargar = [
        {
            "unidad_aprendizaje": "Redes de Computadoras",
            "unidades": [
                {
                    "numero": 1, "nombre": "Fundamentos de redes",
                    "temas": [
                        {"numero": 1, "nombre": "Fundamentos de redes de computadoras", "subtemas": []},
                        {"numero": 2, "nombre": "Clasificación de redes de computadoras", "subtemas": [
                            {"numero": 1, "nombre": "Redes por su área geográfica, topología y relación funcional"},
                            {"numero": 2, "nombre": "Redes conmutadas"},
                            {"numero": 3, "nombre": "Tendencias de las redes: Redes SAN, SDN"}
                        ]},
                        {"numero": 3, "nombre": "Organizaciones de estandarización", "subtemas": [
                            {"numero": 1, "nombre": "ISO, IETF, UIT-T"},
                            {"numero": 2, "nombre": "Principales estándares IEEE (802.2, 802.3, 802.11, 802.15, 802.16)"}
                        ]},
                        {"numero": 4, "nombre": "Modelo OSI y Arquitectura TCP/IP", "subtemas": []}
                    ]
                },
                {
                    "numero": 2, "nombre": "Transmisión de datos",
                    "temas": [
                        {"numero": 1, "nombre": "Funciones de los protocolos", "subtemas": [
                            {"numero": 1, "nombre": "Encapsulamiento, control de flujo y control de error"},
                            {"numero": 2, "nombre": "Segmentación y ensamblado, direccionamiento: nivel, alcance y tipos"},
                            {"numero": 3, "nombre": "Servicios de transmisión, control de conexión y multiplexación"}
                        ]},
                        {"numero": 2, "nombre": "Especificaciones y estándares de medios de transmisión", "subtemas": []},
                        {"numero": 3, "nombre": "Códigos de línea", "subtemas": []}
                    ]
                },
                {
                    "numero": 3, "nombre": "Capa de Acceso a la Red",
                    "temas": [
                        {"numero": 1, "nombre": "Fundamentos de capa física", "subtemas": [
                            {"numero": 1, "nombre": "Ancho de banda"},
                            {"numero": 2, "nombre": "Ruido y relación señal-ruido"},
                            {"numero": 3, "nombre": "Capacidad de canal"}
                        ]},
                        {"numero": 2, "nombre": "Rutinas para manipular la NIC", "subtemas": [
                            {"numero": 1, "nombre": "Rutinas para leer tramas al vuelo"},
                            {"numero": 2, "nombre": "Rutinas para leer tramas desde un archivo"},
                            {"numero": 3, "nombre": "Rutinas para enviar tramas"}
                        ]},
                        {"numero": 3, "nombre": "Estándar IEEE 802.3", "subtemas": [
                            {"numero": 1, "nombre": "Protocolo HDLC"},
                            {"numero": 2, "nombre": "Encabezado IEEE 802.3"},
                            {"numero": 3, "nombre": "Encabezado LLC y análisis de trama IEEE 802.3"}
                        ]},
                        {"numero": 4, "nombre": "Tecnologías de Control de Acceso al Medio", "subtemas": []}
                    ]
                },
                {
                    "numero": 4, "nombre": "Capa de Internet",
                    "temas": [
                        {"numero": 1, "nombre": "Protocolo de Internet (IP)", "subtemas": [
                            {"numero": 1, "nombre": "Direccionamiento IPv4 por clases, VLSM, CIDR"},
                            {"numero": 2, "nombre": "IPv4 vs IPv6"},
                            {"numero": 3, "nombre": "Encabezado IPv4 e IPv6 y análisis de tramas"}
                        ]},
                        {"numero": 2, "nombre": "Enrutamiento IP", "subtemas": [
                            {"numero": 1, "nombre": "Sistema autónomo"},
                            {"numero": 2, "nombre": "Enrutamiento estático"},
                            {"numero": 3, "nombre": "Protocolos de enrutamiento dinámico (interior y exterior)"}
                        ]},
                        {"numero": 3, "nombre": "Protocolo ARP", "subtemas": [
                            {"numero": 1, "nombre": "Encabezado ARP"},
                            {"numero": 2, "nombre": "Análisis de tramas ARP"}
                        ]},
                        {"numero": 4, "nombre": "Protocolo ICMP", "subtemas": [
                            {"numero": 1, "nombre": "Encabezado ICMP"},
                            {"numero": 2, "nombre": "Análisis de tramas ICMP"}
                        ]},
                        {"numero": 5, "nombre": "Protocolo IGMP", "subtemas": [
                            {"numero": 1, "nombre": "Encabezado IGMP"},
                            {"numero": 2, "nombre": "Análisis de tramas IGMP"},
                            {"numero": 3, "nombre": "IGMP vs DVMRP vs PIM vs MSDP"}
                        ]}
                    ]
                },
                {
                    "numero": 5, "nombre": "Capa de Transporte",
                    "temas": [
                        {"numero": 1, "nombre": "Protocolo TCP", "subtemas": [
                            {"numero": 1, "nombre": "Encabezado TCP"}
                        ]},
                        {"numero": 2, "nombre": "Protocolo UDP", "subtemas": [
                            {"numero": 1, "nombre": "Encabezado UDP"}
                        ]},
                        {"numero": 3, "nombre": "Análisis de segmentos TCP y datagramas", "subtemas": []}
                    ]
                }
            ]
        },
        {
            "unidad_aprendizaje": "Administración de Servicios en Red",
            "unidades": [
                {
                    "numero": 1, "nombre": "Fundamentos de los servicios de red",
                    "temas": [
                        {"numero": 1, "nombre": "Servicios de red", "subtemas": [
                            {"numero": 1, "nombre": "Clasificación de los servicios de red"},
                            {"numero": 2, "nombre": "Características de los servicios de red"}
                        ]},
                        {"numero": 2, "nombre": "Análisis de requerimientos", "subtemas": [
                            {"numero": 1, "nombre": "Requerimientos de software"},
                            {"numero": 2, "nombre": "Requerimientos de hardware"},
                            {"numero": 3, "nombre": "Diseño de políticas"}
                        ]},
                        {"numero": 3, "nombre": "Tecnologías de telecomunicaciones", "subtemas": [
                            {"numero": 1, "nombre": "PDH y SDH"},
                            {"numero": 2, "nombre": "DWDM"},
                            {"numero": 3, "nombre": "GSM y GPRS"}
                        ]},
                        {"numero": 4, "nombre": "Ética informática", "subtemas": [
                            {"numero": 1, "nombre": "Código de ética"}
                        ]}
                    ]
                },
                {
                    "numero": 2, "nombre": "Temas avanzados de conectividad",
                    "temas": [
                        {"numero": 1, "nombre": "Configuración avanzada de conectividad", "subtemas": [
                            {"numero": 1, "nombre": "Balanceo de carga"},
                            {"numero": 2, "nombre": "Alta disponibilidad"}
                        ]},
                        {"numero": 2, "nombre": "Listas de Control de Acceso", "subtemas": [
                            {"numero": 1, "nombre": "ACL estándar / extendidas"},
                            {"numero": 2, "nombre": "ACL de entrada y salida"}
                        ]},
                        {"numero": 3, "nombre": "NAT", "subtemas": [
                            {"numero": 1, "nombre": "NAT estática"},
                            {"numero": 2, "nombre": "NAT dinámica"},
                            {"numero": 3, "nombre": "PAT"}
                        ]},
                        {"numero": 4, "nombre": "VLANs", "subtemas": [
                            {"numero": 1, "nombre": "Configuración de puertos troncales"},
                            {"numero": 2, "nombre": "Etiquetado"}
                        ]},
                        {"numero": 5, "nombre": "Redes definidas por software", "subtemas": []}
                    ]
                },
                {
                    "numero": 3, "nombre": "SNMP, monitoreo y calidad",
                    "temas": [
                        {"numero": 1, "nombre": "Administración de la red", "subtemas": [
                            {"numero": 1, "nombre": "SNMP"},
                            {"numero": 2, "nombre": "Bitácoras"},
                            {"numero": 3, "nombre": "Sistemas administradores de red"}
                        ]},
                        {"numero": 2, "nombre": "Calidad de servicio", "subtemas": [
                            {"numero": 1, "nombre": "Conformación de tráfico"},
                            {"numero": 2, "nombre": "Servicios diferenciados"},
                            {"numero": 3, "nombre": "Parametrización de servicios"}
                        ]},
                        {"numero": 3, "nombre": "Monitorización de redes", "subtemas": [
                            {"numero": 1, "nombre": "Proceso y principios de monitorización"},
                            {"numero": 2, "nombre": "Recolección, análisis y notificación"}
                        ]}
                    ]
                },
                {
                    "numero": 4, "nombre": "Implementación de servicios de red",
                    "temas": [
                        {"numero": 1, "nombre": "Servicios de alto nivel", "subtemas": [
                            {"numero": 1, "nombre": "Hipertexto, transferencia de archivos y correo electrónico"},
                            {"numero": 2, "nombre": "Mensajería instantánea, acceso remoto y VoIP"},
                            {"numero": 3, "nombre": "Sistema de archivos de red"}
                        ]},
                        {"numero": 2, "nombre": "Servicios de bajo nivel", "subtemas": [
                            {"numero": 1, "nombre": "Asignación dinámica de direcciones IP"},
                            {"numero": 2, "nombre": "Servicios de nombres"},
                            {"numero": 3, "nombre": "Servidor proxy"}
                        ]}
                    ]
                },
                {
                    "numero": 5, "nombre": "Gestión de la seguridad y el desempeño",
                    "temas": [
                        {"numero": 1, "nombre": "Seguridad básica", "subtemas": [
                            {"numero": 1, "nombre": "Elementos de seguridad"},
                            {"numero": 2, "nombre": "Tipos de riesgo"},
                            {"numero": 3, "nombre": "Políticas y mecanismos de seguridad"}
                        ]},
                        {"numero": 2, "nombre": "Resolución de problemas", "subtemas": [
                            {"numero": 1, "nombre": "Mejorar el desempeño"},
                            {"numero": 2, "nombre": "Tolerancia a fallos"},
                            {"numero": 3, "nombre": "Recuperación"}
                        ]},
                        {"numero": 3, "nombre": "Auditoría informática", "subtemas": [
                            {"numero": 1, "nombre": "Objetivos y criterios"},
                            {"numero": 2, "nombre": "Planeación de auditoría"},
                            {"numero": 3, "nombre": "Seguimiento y reportes"}
                        ]}
                    ]
                }
            ]
        }
    ]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    for materia in materias_a_cargar:
        try:
            # Comprobar si la materia ya existe para no duplicar
            cursor.execute("SELECT id_unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE unidad_aprendizaje = ?", (materia["unidad_aprendizaje"],))
            existe = cursor.fetchone()
            
            if existe:
                print(f"⚠️ La materia '{materia['unidad_aprendizaje']}' ya existe. Saltando...")
                continue

            # 1. Insertar Materia con UUID
            id_materia = generar_id()
            cursor.execute(
                "INSERT INTO Unidad_de_Aprendizaje (id_unidad_aprendizaje, unidad_aprendizaje, activa) VALUES (?, ?, ?)", 
                (id_materia, materia["unidad_aprendizaje"], 1)
            )
            print(f"✅ Materia registrada: {materia['unidad_aprendizaje']} (ID: {id_materia[:8]}...)")

            # 2. Iterar Unidades
            for unidad in materia["unidades"]:
                id_unidad = generar_id()
                cursor.execute(
                    "INSERT INTO Unidad (id_unidad_tematica, id_unidad_aprendizaje, nombre_unidad_tematica, numero_unidad) VALUES (?, ?, ?, ?)",
                    (id_unidad, id_materia, unidad["nombre"], unidad["numero"])
                )

                # 3. Iterar Temas
                for tema in unidad["temas"]:
                    id_tema = generar_id()
                    cursor.execute(
                        "INSERT INTO Temas (id_tema, id_unidad_tematica, nombre_tema, numero_tema) VALUES (?, ?, ?, ?)",
                        (id_tema, id_unidad, tema["nombre"], tema["numero"])
                    )

                    # 4. Iterar Subtemas
                    for subtema in tema["subtemas"]:
                        id_subtema = generar_id()
                        cursor.execute(
                            "INSERT INTO Subtema (id_subtema, id_tema, nombre_subtema, numero_subtema, embedding) VALUES (?, ?, ?, ?, ?)",
                            (id_subtema, id_tema, subtema["nombre"], subtema["numero"], None)
                        )
        except sqlite3.IntegrityError as e:
            print(f"⚠️ Error de integridad con '{materia['unidad_aprendizaje']}': {e}")

    conn.commit()
    conn.close()
    print("🚀 Base de datos poblada exitosamente usando UUIDs.")

if __name__ == "__main__":
    poblar_base_de_datos_uuid()