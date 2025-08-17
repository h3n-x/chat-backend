"""
Utilidades de cifrado mejoradas para el chat anónimo
Implementa AES-256-GCM para cifrado end-to-end seguro
"""
import base64
import secrets
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("chat_backend")

class ChatCrypto:
    """Clase para manejar cifrado/descifrado de mensajes del chat"""
    
    def __init__(self):
        self.room_keys: Dict[str, bytes] = {}
        self.public_chat_key: Optional[bytes] = None
        
    def generate_key(self) -> str:
        """Generar una nueva clave AES-256 y retornarla en base64"""
        key_bytes = AESGCM.generate_key(bit_length=256)
        return base64.b64encode(key_bytes).decode('utf-8')
    
    def set_public_chat_key(self, key_b64: str) -> bool:
        """Establecer la clave del chat público desde base64"""
        try:
            self.public_chat_key = base64.b64decode(key_b64)
            logger.info("🔐 Clave del chat público establecida")
            return True
        except Exception as e:
            logger.error(f"❌ Error al establecer clave pública: {e}")
            return False
    
    def set_room_key(self, room_id: str, key_b64: str) -> bool:
        """Establecer la clave de una sala privada desde base64"""
        try:
            self.room_keys[room_id] = base64.b64decode(key_b64)
            logger.info(f"🔐 Clave de sala {room_id} establecida")
            return True
        except Exception as e:
            logger.error(f"❌ Error al establecer clave de sala {room_id}: {e}")
            return False
    
    def encrypt_message(self, message: str, room_id: Optional[str] = None) -> Optional[Dict]:
        """
        Cifrar un mensaje usando AES-256-GCM
        
        Args:
            message: Texto a cifrar
            room_id: ID de sala (None para chat público)
            
        Returns:
            Dict con datos cifrados o None si hay error
        """
        try:
            # Seleccionar clave apropiada
            if room_id and room_id in self.room_keys:
                key = self.room_keys[room_id]
                logger.debug(f"🔐 Usando clave de sala {room_id}")
            elif self.public_chat_key:
                key = self.public_chat_key
                logger.debug("🔐 Usando clave del chat público")
            else:
                logger.error("❌ No hay clave disponible para cifrado")
                return None
            
            # Cifrar mensaje
            aesgcm = AESGCM(key)
            nonce = secrets.token_bytes(12)  # 96 bits para GCM
            
            message_bytes = message.encode('utf-8')
            ciphertext = aesgcm.encrypt(nonce, message_bytes, None)
            
            # Retornar datos cifrados en formato base64
            encrypted_data = {
                "data": base64.b64encode(ciphertext).decode('utf-8'),
                "nonce": base64.b64encode(nonce).decode('utf-8'),
                "algorithm": "AES-256-GCM"
            }
            
            logger.debug(f"✅ Mensaje cifrado correctamente (longitud: {len(ciphertext)})")
            return encrypted_data
            
        except Exception as e:
            logger.error(f"❌ Error al cifrar mensaje: {e}")
            return None
    
    def decrypt_message(self, encrypted_data: Dict, room_id: Optional[str] = None) -> Optional[str]:
        """
        Descifrar un mensaje usando AES-256-GCM
        
        Args:
            encrypted_data: Datos cifrados del frontend
            room_id: ID de sala (None para chat público)
            
        Returns:
            Mensaje descifrado o None si hay error
        """
        try:
            # Validar estructura de datos
            if not all(key in encrypted_data for key in ["data", "nonce"]):
                logger.error("❌ Datos cifrados incompletos")
                return None
            
            # Seleccionar clave apropiada
            if room_id and room_id in self.room_keys:
                key = self.room_keys[room_id]
                logger.debug(f"🔐 Usando clave de sala {room_id} para descifrado")
            elif self.public_chat_key:
                key = self.public_chat_key
                logger.debug("🔐 Usando clave del chat público para descifrado")
            else:
                logger.error("❌ No hay clave disponible para descifrado")
                return None
            
            # Descifrar mensaje
            aesgcm = AESGCM(key)
            ciphertext = base64.b64decode(encrypted_data["data"])
            nonce = base64.b64decode(encrypted_data["nonce"])
            
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            message = plaintext_bytes.decode('utf-8')
            
            logger.debug(f"✅ Mensaje descifrado correctamente (longitud: {len(message)})")
            return message
            
        except Exception as e:
            logger.error(f"❌ Error al descifrar mensaje: {e}")
            return None
    
    def verify_encrypted_data(self, encrypted_data: Dict) -> bool:
        """Verificar que los datos cifrados tienen el formato correcto"""
        if not isinstance(encrypted_data, dict):
            return False
        
        required_fields = ["data", "nonce"]
        if not all(field in encrypted_data for field in required_fields):
            return False
        
        try:
            # Verificar que son base64 válidos
            base64.b64decode(encrypted_data["data"])
            base64.b64decode(encrypted_data["nonce"])
            return True
        except Exception:
            return False

# Instancia global del sistema de cifrado
chat_crypto = ChatCrypto()

def crypto_system():
    """Retorna la instancia global del sistema de cifrado"""
    return chat_crypto

def get_crypto_info():
    """Obtiene información sobre el estado del sistema de cifrado"""
    info = {
        "has_public_key": chat_crypto.public_chat_key is not None,
        "room_keys_count": len(chat_crypto.room_keys),
        "algorithm": "AES-256-GCM",
        "status": "ready"
    }
    return info

def encrypt_data(data: str, room_id: Optional[str] = None) -> Optional[Dict]:
    """Función de compatibilidad para cifrar datos"""
    return chat_crypto.encrypt_message(data, room_id)

def decrypt_data(encrypted_data: Dict, room_id: Optional[str] = None) -> Optional[str]:
    """Función de compatibilidad para descifrar datos"""
    return chat_crypto.decrypt_message(encrypted_data, room_id)

def generate_chat_key() -> str:
    """Función de compatibilidad para generar claves"""
    return chat_crypto.generate_key()

def set_chat_key(key_b64: str, room_id: Optional[str] = None) -> bool:
    """Función de compatibilidad para establecer claves"""
    if room_id:
        return chat_crypto.set_room_key(room_id, key_b64)
    else:
        return chat_crypto.set_public_chat_key(key_b64)
