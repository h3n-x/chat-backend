#!/usr/bin/env python3
"""
Script de inicio para Render.com
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"  # Render requiere bind a todas las interfaces
    
    print("🚀 Iniciando servidor para Render...")
    print(f"🌐 Puerto: {port}")
    print("💬 Chat anónimo listo!")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
