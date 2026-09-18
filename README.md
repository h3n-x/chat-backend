<div align="center">

# 🛡️ Chat Anónimo — Backend (Zero-Knowledge Blind Relay v2.0)

![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-Blind_Relay-010101?style=for-the-badge&logo=socketdotio&logoColor=white)
![Coverage](https://img.shields.io/badge/Test_Coverage-93%25-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)
![Security](https://img.shields.io/badge/Security-Zero_Knowledge-10B981?style=for-the-badge&logo=shield&logoColor=white)

**Enrutador ciego de paquetes de comunicación efímera cifrada de extremo a extremo (E2EE) con cero conocimiento y cero persistencia.**

[🏠 Repositorio Umbrella](https://github.com/h3n-x/chat-anonimo) • [🎨 Frontend SPA](https://github.com/h3n-x/chat-frontend) • [🌐 Demo](https://chat-zk.netlify.app)

</div>

---

## 🔒 Principio Rector: Zero-Knowledge Blind Relay

A diferencia de arquitecturas tradicionales de chat o de la versión v1.0 (donde el servidor generaba claves simétricas y descifraba el contenido en tránsito), **Chat Anónimo v2.0 implementa una política estricta de Cero Confianza (*Zero-Knowledge Blind Relay*)**:

1. **Diseño Blind Relay (Aislamiento de Claves):** El servidor jamás genera, recibe, deduce ni almacena claves privadas ni simétricas en su código o base de datos. Solo enruta sobres opacos de ciphertext en Base64 sin retener material criptográfico que permita descifrarlos.
2. **Zero-Persistence Real:** No existe base de datos ni almacenamiento persistente de mensajes. Las salas y los identificadores efímeros residen exclusivamente en la memoria RAM y son purgados de inmediato en cuanto todos los participantes se desconectan.
3. **Cero Exposición de Metadatos de Aplicación:** Los nombres originales de archivos, tipos MIME, remitentes y apodos viajan cifrados dentro del payload AEAD, invisibles para el servidor.

---

## 🏛️ Arquitectura y Modelo de Amenazas

```
+-------------------------------------------------------------------------+
|                              CLIENTE ALICE                              |
|   Genera RoomKey (AES-256-GCM) en memoria local vía WebCrypto API      |
+------------------------------------+------------------------------------+
                                     |  Sobre Cifrado (AAD: "room:XYZ")
                                     v
+------------------------------------+------------------------------------+
|                   BACKEND FASTAPI (BLIND RELAY)                         |
|   1. Valida esquema de frame WebSocket (Pydantic v2)                   |
|   2. Aplica Rate Limiting deslizante por IP (30 msg/min, 5 conn/IP)     |
|   3. Retransmite sobre opaco a sockets conectados a la sala "XYZ"       |
|   4. JAMÁS inspecciona o descifra el contenido (Blind Relay)           |
+------------------------------------+------------------------------------+
                                     |  Sobre Cifrado intacto
                                     v
+------------------------------------+------------------------------------+
|                               CLIENTE BOB                               |
|   Descifra y autentica payload con RoomKey y AAD: "room:XYZ"            |
+-------------------------------------------------------------------------+
```

### Límites de Seguridad del Modelo de Amenazas

#### Lo que este sistema SÍ protege:
- **Espionaje en tránsito:** Ataques pasivos de red (ISP, sniffing Wi-Fi, intermediarios no autorizados).
- **Acceso no autorizado al servidor en operación normal:** La inspección de logs, buffers y memoria del proceso del servidor no expone claves privadas, claves simétricas ni texto plano (verificado en suite de pruebas).
- **Inyección y retransmisión entre salas:** El uso de Datos Asociados Autenticados ($\text{AAD} = \text{"room:"} + room\_id$) garantiza que un mensaje capturado de una sala no pueda ser inyectado ni validado en otra.
- **Saturación por memoria en subidas:** Streaming en chunks de 64 KB con corte estricto en **15 MB** (`HTTP 413`).

#### Lo que este sistema NO protege (Límites Explícitos):
> [!CAUTION]
> - **Dispositivo final comprometido (Endpoint Security):** Si el navegador o el sistema operativo del usuario está infectado con malware, keyloggers, software espía o extensiones maliciosas de navegador con acceso al DOM o memoria, la seguridad del cifrado queda completamente invalidada a nivel local.
> - **Omisión de la verificación SAS fuera de banda:** Si los participantes no comparan activamente el código de 4 palabras por un canal externo seguro (ej. llamada de voz o presencial), el protocolo es susceptible a ataques Man-in-the-Middle (MITM) activos donde un intermediario sustituya las claves públicas efímeras de ECDH.
> - **Canal de distribución del enlace o código inicial:** Si el enlace directo con hash fragment (`#room=...&key=...`) o el código de sala se comparte a través de un canal inseguro (SMS, correo en texto plano, chat no cifrado), cualquier tercero que acceda al enlace obtendrá la clave de descifrado.
> - **Metadatos de red y análisis de tráfico:** El servidor y los proveedores de infraestructura pueden observar las direcciones IP de origen, timestamps de conexión/desconexión, y volumen/frecuencia de paquetes. El sistema no implementa enrutamiento cebolla (Tor) ni ofuscación de tráfico de red.
> - **Persistencia en la memoria del navegador:** Mientras la pestaña permanezca abierta, las claves simétricas residen en la RAM del proceso del navegador. Es responsabilidad del usuario pulsar "Salir" para purgar las claves del estado local.

---

## ⚙️ Características Técnicas del Backend

- **FastAPI 0.115+ & Python 3.12+:** Arquitectura modular asíncrona estructurada en `app/`.
- **Enrutador WebSocket Blind:** Retransmisión transparente de frames de mensajería E2EE y paquetes de acuerdo de claves efímero (ECDH / X25519).
- **Streaming de Archivos Cifrados con Límite Estricto:** Subida en chunks de 64 KB con corte inmediato en **15 MB** (`HTTP 413 Content Too Large`) para garantizar un consumo de RAM acotado en el servidor.
- **Auto-Destrucción (TTL):** Tarea asíncrona en segundo plano que purga automáticamente los blobs cifrados temporales a los 10 minutos (`600s`).
- **Defensa en Profundidad:**
  - Rate limiting deslizante en memoria por IP para WebSockets, subida de archivos y creación de salas.
  - Cabeceras de seguridad HTTP estrictas (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`).
  - Eliminación total de endpoints administrativos inseguros (`/admin/broadcast`, `/admin/cleanup`).

---

## 🔌 Especificación de la API

### Endpoints REST

| Método | Endpoint | Descripción | Rate Limit |
|---|---|---|---|
| `GET` | `/health` | Chequeo de salud del servicio y salas activas en RAM | Sin límite |
| `POST` | `/api/rooms/create` | Genera un código de sala alfanumérico seguro (6 chars) | 10 / min por IP |
| `GET` | `/api/rooms/{room_id}/status` | Consulta el estado y participantes de una sala | 60 / min por IP |
| `POST` | `/api/files/upload` | Streaming de payload cifrado (máx. 15 MB, chunks 64KB) | 3 / min por IP |
| `GET` | `/api/files/download/{file_id}` | Descarga de payload `.enc` opaco con cabeceras `no-store` | 30 / min por IP |

### WebSocket Endpoint

- **URL:** `/ws/{room_id}`
- **Protocolo de Enmarcado (Frames JSON):**
  - Inbound: `e2ee_message`, `key_request`, `key_delivery`, `ping`.
  - Outbound: `e2ee_message`, `key_request`, `key_delivery`, `peer_joined`, `peer_left`, `pong`, `error`.
  - Límite máximo de frame WebSocket: **64 KB**.

---

## 🧪 Pruebas Automatizadas y Cobertura

El backend cuenta con una suite completa de pruebas unitarias y de integración que simulan el ciclo de vida criptográfico completo entre clientes pares:

```bash
# Ejecutar la suite de pruebas
pytest -v

# Ejecutar con reporte de cobertura detallado
pytest --cov=app --cov-report=term-missing
```

### Resultados de Cobertura (93% Global):
```
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
app/config.py                     17      0   100%
app/main.py                       53      6    89%
app/models/api_schemas.py          8      0   100%
app/models/ws_messages.py         34      0   100%
app/routers/files.py              25      0   100%
app/routers/health.py              7      0   100%
app/routers/rooms.py              27      0   100%
app/routers/websocket.py          73      5    93%
app/security/rate_limiter.py      55      1    98%
app/services/file_storage.py      76      7    91%
app/services/room_manager.py      75     14    81%
------------------------------------------------------------
```

### 🔬 Auditoría de Aislamiento de Claves (`tests/test_server_inability.py`):
El test `test_server_key_isolation_and_zero_retention` simula el intercambio completo entre Alice y Bob a través del router WebSocket real y audita forensicamente el proceso:
- Verifica que el servidor no almacene, registre en logs ni retenga claves privadas (`sk_Alice`, `sk_Bob`), claves de envoltura (`K_wrap`), claves de sala (`RoomKey`) ni texto plano de mensajes.
- Comprueba que tras la desconexión de los participantes, la sala se purga al 100% de la memoria RAM (*Zero-Persistence*).
- Demuestra que con los datos que transitan por el servidor (puntos públicos y ciphertext opaco), descifrar el mensaje o desenvolver la clave de sala falla, ratificando el aislamiento del blind relay en operación normal.

---

## 🚀 Despliegue y Ejecución Local

### Requisitos
- Python 3.12+ (compatible con Python 3.14)
- Pip o entorno virtual

```bash
# 1. Clonar el repositorio
git clone https://github.com/h3n-x/chat-backend.git
cd chat-backend

# 2. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar el servidor Uvicorn
python main.py
# O alternativamente:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Despliegue con Docker
```bash
docker build -t chat-backend:v2.0 .
docker run -p 8000:8000 chat-backend:v2.0
```

---

## 📜 Licencia
Distribuido bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.
