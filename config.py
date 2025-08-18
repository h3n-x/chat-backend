# Configuración del chat
import os

MAX_MESSAGE_LENGTH = 500
MAX_USERNAME_LENGTH = 30
MAX_CONNECTIONS = 50  # Reducido para mejor rendimiento sin BD
MESSAGE_HISTORY_LIMIT = 50  # Reducido para mayor privacidad
PING_INTERVAL = 30  # segundos

# Configuración de archivos - TAMAÑOS RAZONABLES PARA MÁXIMO ANONIMATO
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB máximo (mejor balance para archivos útiles)
MAX_FILES_PER_USER = 5  # Máximo 5 archivos por usuario conectado
MAX_TOTAL_FILES = 30   # Máximo 30 archivos totales en memoria

ALLOWED_FILE_TYPES = {
    # Imágenes (optimizadas para chat)
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    # Documentos básicos
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    # Audio ligero para mensajes de voz
    'audio/mpeg': '.mp3',
    'audio/webm': '.webm',
    'audio/ogg': '.ogg'
    # Removimos videos y documentos pesados para mejor rendimiento
}

UPLOAD_DIR = "temp_uploads"  # Nombre más claro
FILE_CLEANUP_INTERVAL = 180  # 3 minutos (más frecuente)
FILE_RETENTION_TIME = 2700   # 45 minutos (balance entre utilidad y privacidad)
MESSAGE_RETENTION_TIME = 600 # 10 minutos para mensajes (más privacidad)

# Configuración del servidor
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Colores disponibles para usuarios
USER_COLORS = [
    "#FF6B6B",  # Rojo coral
    "#4ECDC4",  # Turquesa
    "#45B7D1",  # Azul cielo
    "#96CEB4",  # Verde menta
    "#FFEAA7",  # Amarillo claro
    "#DDA0DD",  # Ciruela
    "#98D8C8",  # Verde agua
    "#F7DC6F",  # Amarillo dorado
    "#BB8FCE",  # Lavanda
    "#85C1E9",  # Azul claro
    "#F8C471",  # Naranja melocotón
    "#82E0AA",  # Verde claro
    "#F1948A",  # Rosa salmón
    "#85C1E9",  # Azul celeste
    "#D2B4DE"   # Púrpura claro
]

# Mensajes del sistema
WELCOME_MESSAGES = [
    "¡Bienvenido al chat anónimo!",
    "¡Hola! Disfruta conversando de forma anónima",
    "¡Te damos la bienvenida a nuestro chat!",
]

SYSTEM_MESSAGES = {
    "user_joined": "{username} se ha unido al chat",
    "user_left": "{username} ha salido del chat",
    "server_restart": "El servidor se está reiniciando...",
    "max_users": "Se ha alcanzado el máximo de usuarios conectados"
}
