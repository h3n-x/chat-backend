import logging
import sys
from datetime import datetime

def setup_logger(name: str = "chat_backend", level: int = logging.INFO):
    """Configurar logger para la aplicación"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Formato del log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger

def log_connection_event(event_type: str, username: str, total_users: int):
    """Log eventos de conexión"""
    logger = logging.getLogger("chat_backend")
    logger.info(f"[{event_type}] Usuario: {username} | Total usuarios: {total_users}")

def log_message_event(username: str, message_length: int):
    """Log eventos de mensajes"""
    logger = logging.getLogger("chat_backend")
    logger.info(f"[MESSAGE] Usuario: {username} | Longitud: {message_length} caracteres")
