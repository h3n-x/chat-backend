# Configuración del chat
import os

MAX_MESSAGE_LENGTH = 500
MAX_USERNAME_LENGTH = 30
MAX_CONNECTIONS = 100
MESSAGE_HISTORY_LIMIT = 100
PING_INTERVAL = 30  # segundos

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
