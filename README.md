# Chat Anónimo - Backend

Backend en Python para una aplicación de chat anónimo en tiempo real usando WebSockets.

## Características

- ✅ Chat en tiempo real con WebSockets
- ✅ Usuarios anónimos con nombres auto-generados
- ✅ Colores únicos para cada usuario
- ✅ Historial de mensajes (últimos 20 mensajes)
- ✅ Lista de usuarios conectados en vivo
- ✅ Mensajes del sistema (conexión/desconexión)
- ✅ API REST para información del servidor
- ✅ Manejo robusto de errores y desconexiones
- ✅ CORS configurado para frontend

## Tecnologías

- **FastAPI**: Framework web rápido y moderno
- **WebSockets**: Comunicación bidireccional en tiempo real
- **Uvicorn**: Servidor ASGI de alto rendimiento
- **Pydantic**: Validación de datos

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar el servidor:
```bash
python run_server.py
```

O alternativamente:
```bash
python main.py
```

## Endpoints

### REST API
- `GET /` - Información general del servidor
- `GET /health` - Estado de salud del servidor

### WebSocket
- `WS /ws` - Endpoint principal para conexiones de chat

## Estructura de Mensajes WebSocket

### Mensajes del Cliente al Servidor

#### Enviar mensaje de chat:
```json
{
  "type": "chat_message",
  "message": "Hola a todos!"
}
```

#### Ping (mantener conexión):
```json
{
  "type": "ping"
}
```

### Mensajes del Servidor al Cliente

#### Mensaje de bienvenida:
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

#### Mensaje de chat:
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

#### Mensaje del sistema:
```json
{
  "type": "system_message",
  "message": "Anónimo_1 se ha unido al chat",
  "timestamp": "2024-01-01T12:00:00"
}
```

#### Lista de usuarios:
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

#### Historial de mensajes:
```json
{
  "type": "message_history",
  "messages": [...]
}
```

## Configuración

Editar `config.py` para personalizar:

- `MAX_MESSAGE_LENGTH`: Longitud máxima de mensajes (500 caracteres)
- `MAX_CONNECTIONS`: Máximo número de usuarios conectados (100)
- `MESSAGE_HISTORY_LIMIT`: Mensajes guardados en historial (100)
- `USER_COLORS`: Colores disponibles para usuarios
- `HOST` y `PORT`: Configuración del servidor

## Logs

El servidor registra eventos importantes:
- Conexiones y desconexiones de usuarios
- Mensajes enviados (con longitud)
- Errores de WebSocket
- Estado general del servidor

## Producción

Para producción, considera:

1. **Base de datos**: Reemplazar almacenamiento en memoria por Redis/PostgreSQL
2. **Autenticación**: Implementar sistema de usuarios opcional
3. **Rate limiting**: Limitar frecuencia de mensajes por usuario
4. **Moderación**: Sistema de filtros y moderación de contenido
5. **Escalabilidad**: Usar múltiples instancias con Redis para pub/sub
6. **HTTPS**: Configurar SSL/TLS para conexiones seguras
7. **Monitoreo**: Integrar herramientas de monitoreo y métricas

## Estructura del Proyecto

```
chat-backend/
├── main.py              # Servidor principal FastAPI
├── models.py            # Modelos Pydantic
├── config.py            # Configuración
├── utils.py             # Utilidades y logging
├── run_server.py        # Script para ejecutar servidor
├── requirements.txt     # Dependencias
└── README.md           # Este archivo
```
