#!/usr/bin/env python3
"""
Script para ejecutar el servidor de chat anónimo
"""
import uvicorn
from config import HOST, PORT, DEBUG

if __name__ == "__main__":
    print("🚀 Iniciando servidor de Chat Anónimo...")
    print(f"🌐 Servidor ejecutándose en: http://{HOST}:{PORT}")
    print(f"🔌 WebSocket endpoint: ws://{HOST}:{PORT}/ws")
    print("💬 ¡El chat está listo para recibir usuarios!")
    print(f"👥 Máximo de usuarios: {100}")  # Importar MAX_CONNECTIONS si es necesario
    print(f"📝 Longitud máxima de mensaje: {500} caracteres")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
        access_log=True
    )
