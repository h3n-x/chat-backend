"""
Script de prueba completo para el sistema de cifrado
"""
import sys
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_crypto_installation():
    """Probar instalación de librerías de cifrado"""
    logger.info("🔧 Probando instalación de librerías de cifrado...")
    
    # Probar cryptography
    try:
        import cryptography
        logger.info(f"✅ cryptography {cryptography.__version__} instalada correctamente")
    except ImportError:
        logger.warning("⚠️ cryptography no disponible")
    
    # Probar pycryptodome
    try:
        import Crypto
        logger.info(f"✅ pycryptodome instalada correctamente")
    except ImportError:
        logger.warning("⚠️ pycryptodome no disponible")

def test_crypto_system():
    """Probar el sistema de cifrado completo"""
    logger.info("🧪 Iniciando pruebas del sistema de cifrado...")
    
    try:
        from crypto_utils import crypto_system, get_crypto_info, encrypt_data, decrypt_data, generate_chat_key, set_chat_key
        
        # Información del sistema
        crypto_info = get_crypto_info()
        logger.info(f"📊 Sistema de cifrado: {crypto_info}")
        
        if not crypto_info.get('status') == 'ready':
            logger.error("❌ Sistema de cifrado no está listo")
            return False
        
        # Generar clave
        key = generate_chat_key()
        if not key:
            logger.error("❌ No se pudo generar clave")
            return False
        logger.info(f"🔑 Clave generada: {key[:20]}...")
        
        if not set_chat_key(key):
            logger.error("❌ No se pudo establecer la clave")
            return False
        
        # Mensaje de prueba
        test_message = "¡Hola! Este es un mensaje de prueba para el cifrado E2EE 🔐"
        logger.info(f"📝 Mensaje original: {test_message}")
        
        encrypted_data = encrypt_data(test_message)
        if not encrypted_data:
            logger.error("❌ No se pudo cifrar el mensaje")
            return False
        logger.info(f"🔐 Mensaje cifrado: {encrypted_data}")
        
        decrypted_message = decrypt_data(encrypted_data)
        if not decrypted_message:
            logger.error("❌ No se pudo descifrar el mensaje")
            return False
        logger.info(f"🔓 Mensaje descifrado: {decrypted_message}")
        
        if test_message == decrypted_message:
            logger.info("✅ ¡Cifrado y descifrado funcionan correctamente!")
            
            logger.info("🏠 Probando cifrado para sala privada...")
            room_key = generate_chat_key()
            set_chat_key(room_key, "test_room")
            
            encrypted_room = encrypt_data("Mensaje de sala privada", "test_room")
            decrypted_room = decrypt_data(encrypted_room, "test_room")
            
            if decrypted_room == "Mensaje de sala privada":
                logger.info("✅ ¡Cifrado de sala privada también funciona!")
                return True
            else:
                logger.error("❌ Error en cifrado de sala privada")
                return False
        else:
            logger.error("❌ El mensaje descifrado no coincide con el original")
            return False
            
    except ImportError as e:
        logger.error(f"❌ Error importando crypto_utils: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error en pruebas de cifrado: {e}")
        return False

def main():
    """Función principal"""
    logger.info("🚀 Iniciando pruebas del sistema de cifrado del chat...")
    
    # Probar instalación
    test_crypto_installation()
    
    # Probar sistema
    success = test_crypto_system()
    
    if success:
        logger.info("🎉 ¡Todas las pruebas pasaron exitosamente!")
        logger.info("💬 El sistema de chat con cifrado E2EE está listo para usar")
    else:
        logger.error("💥 Algunas pruebas fallaron")
        logger.info("🔧 Revisa la instalación de las librerías de cifrado")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
