<div align="center">

# 🚀 Chat Anónimo - Backend

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-010101?style=for-the-badge&logo=socketdotio&logoColor=white)
![Encryption](https://img.shields.io/badge/AES_256-FF6B6B?style=for-the-badge&logo=lock&logoColor=white)
![Deploy](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)

**Backend seguro con FastAPI, WebSockets y cifrado end-to-end**

[![Backend Status](https://img.shields.io/website?url=https://chat-backend-haeb.onrender.com&label=Backend%20Status&style=flat-square)](https://chat-backend-haeb.onrender.com)
[![API Docs](https://img.shields.io/badge/API-Docs-blue?style=flat-square)](https://chat-backend-haeb.onrender.com/docs)
[![Health Check](https://img.shields.io/badge/Health-Check-green?style=flat-square)](https://chat-backend-haeb.onrender.com/health)

[🏠 Documentación Principal](https://github.com/h3n-x/chat-anonimo) • [🎨 Frontend](https://github.com/h3n-x/chat-frontend) • [🌐 Demo](https://write-ghost.netlify.app)

</div>

---

## 📋 Tabla de Contenidos

<details>
<summary>🔍 Expandir navegación</summary>

- [⚡ Quick Start](#-quick-start)
- [🌟 Características](#-características)
- [📦 Instalación](#-instalación)
- [🔌 API Reference](#-api-reference)
- [⚙️ Configuración](#️-configuración)
- [🚀 Deployment](#-deployment)
- [🤝 Contribución](#-contribución)

</details>

---

## ⚡ Quick Start

<div align="center">

**¿Quieres probar el backend en 30 segundos?**

</div>

```bash
# 1️⃣ Clonar y configurar
git clone https://github.com/h3n-x/chat-backend.git && cd chat-backend

# 2️⃣ Instalar dependencias
pip install -r requirements.txt

# 3️⃣ Ejecutar servidor
python main.py

# 4️⃣ Verificar funcionamiento
curl http://localhost:8000/health
```

> 💡 **Tip**: Para la experiencia completa, también ejecuta el [frontend](https://github.com/h3n-x/chat-frontend)

---

## 🌟 Características

<table>
<tr>
<td width="50%">

### 🔧 **Stack Tecnológico**
- **FastAPI** - Framework web moderno
- **WebSockets** - Comunicación tiempo real
- **Python 3.11+** - Rendimiento optimizado
- **Asyncio** - Operaciones asíncronas
- **Uvicorn** - Servidor ASGI de alto rendimiento
- **Pydantic** - Validación de datos

</td>
<td width="50%">

### 🛡️ **Seguridad Avanzada**
- **🔐 AES-256-GCM** - Cifrado de grado militar
- **🔑 Diffie-Hellman** - Intercambio seguro de claves
- **🚫 Zero Persistence** - Sin almacenamiento de datos
- **⏰ Auto-cleanup** - Limpieza automática
- **🛡️ CORS** - Configuración de dominios
- **🔒 Metadatos cifrados** - Privacidad total

</td>
</tr>
</table>

### 📁 **Gestión de Archivos Inteligente**

| Característica | Descripción |
|---|---|
| **Subida Segura** | Validación automática de tipos de archivo |
| **Cifrado Automático** | Todo el contenido se cifra con AES-256 |
| **Límites Inteligentes** | Máximo 15MB por archivo |
| **Auto-eliminación** | Archivos se eliminan después de 30 minutos |
| **Metadatos Protegidos** | Información del archivo completamente cifrada |

---

## 📦 Instalación

<details>
<summary>📋 <strong>Requisitos del Sistema</strong></summary>

- **Python 3.11+**
- **pip** (gestor de paquetes)
- **Git** (para clonar repositorio)
- **4GB RAM** (recomendado)
- **50MB espacio libre**

</details>

### 🔧 **Instalación Paso a Paso**

<details>
<summary>🐍 <strong>Instalación Estándar</strong></summary>

```bash
# Clonar repositorio
git clone https://github.com/h3n-x/chat-backend.git
cd chat-backend

# Crear entorno virtual (recomendado)
python -m venv venv

# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python main.py
```

</details>

<details>
<summary>🐳 <strong>Instalación con Docker</strong></summary>

```bash
# Construir imagen
docker build -t chat-backend .

# Ejecutar contenedor
docker run -p 8000:8000 chat-backend

# Verificar funcionamiento
curl http://localhost:8000/health
```

</details>

### 🔗 **Conexión con Frontend**

Este backend funciona perfectamente con nuestro frontend de Next.js:

- **📁 Repositorio**: [chat-frontend](https://github.com/h3n-x/chat-frontend.git)
- **🌐 Demo Live**: [write-ghost.netlify.app](https://write-ghost.netlify.app)
- **🔌 WebSocket**: `ws://localhost:8000/ws` (desarrollo)

---

## 🔌 API Reference

### 🌐 **REST Endpoints**

| Método | Endpoint | Descripción | Respuesta |
|---|---|---|---|
| `GET` | `/` | Información del servidor | Server info |
| `GET` | `/health` | Estado de salud | Health status |
| `GET` | `/docs` | Documentación interactiva | Swagger UI |

### 🔌 **WebSocket Endpoints**

| Endpoint | Protocolo | Descripción |
|---|---|---|
| `/ws` | WebSocket | Conexión principal de chat |

<details>
<summary>📡 <strong>Estructura de Mensajes WebSocket</strong></summary>

#### **Cliente → Servidor**

**Enviar mensaje:**
```json
{
  "type": "chat_message",
  "message": "Hola a todos!"
}
```

**Mantener conexión:**
```json
{
  "type": "ping"
}
```

#### **Servidor → Cliente**

**Mensaje de bienvenida:**
```json
{
  "type": "welcome",
  "user_info": {
    "id": "abc123",
    "username": "Anónimo_1",
    "connected_at": "2024-01-01T12:00:00",
    "color": "#FF6B6B"
  },
  "message": "¡Bienvenido al chat, Anónimo_1!"
}
```

**Mensaje de chat:**
```json
{
  "type": "chat_message",
  "id": "msg-uuid",
  "user_id": "abc123",
  "username": "Anónimo_1",
  "message": "Hola a todos!",
  "timestamp": "2024-01-01T12:00:00",
  "color": "#FF6B6B"
}
```

**Mensaje del sistema:**
```json
{
  "type": "system_message",
  "message": "Anónimo_1 se ha unido al chat",
  "timestamp": "2024-01-01T12:00:00"
}
```

**Lista de usuarios:**
```json
{
  "type": "user_list",
  "users": [
    {
      "id": "abc123",
      "username": "Anónimo_1",
      "color": "#FF6B6B"
    }
  ],
  "count": 1
}
```

</details>

---

## ⚙️ Configuración

<details>
<summary>🔧 <strong>Parámetros de Configuración</strong></summary>

Edita `config.py` para personalizar el comportamiento:

```python
# Límites de mensajes
MAX_MESSAGE_LENGTH = 500        # Caracteres máximos por mensaje
MESSAGE_HISTORY_LIMIT = 100     # Mensajes en historial

# Conexiones
MAX_CONNECTIONS = 100           # Usuarios simultáneos máximos

# Servidor
HOST = "0.0.0.0"               # Host del servidor
PORT = 8000                    # Puerto del servidor

# Colores de usuario
USER_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", 
    "#96CEB4", "#FFEAA7", "#DDA0DD"
]
