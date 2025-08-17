"""
Script simple para probar funcionalidades básicas del backend
sin dependencias externas de testing
"""
import json
import asyncio
import websockets
import aiohttp
from datetime import datetime

async def test_rest_endpoints():
    """Probar endpoints REST"""
    print("🧪 Probando endpoints REST...")
    
    async with aiohttp.ClientSession() as session:
        # Test endpoint raíz
        async with session.get('http://localhost:8000/') as response:
            data = await response.json()
            print(f"✅ Endpoint raíz: {response.status} - {data['status']}")
        
        # Test endpoint salud
        async with session.get('http://localhost:8000/health') as response:
            data = await response.json()
            print(f"✅ Endpoint salud: {response.status} - {data['status']}")
            print(f"   Usuarios activos: {data['metrics']['active_connections']}")
        
        # Test endpoint usuarios
        async with session.get('http://localhost:8000/users') as response:
            data = await response.json()
            print(f"✅ Endpoint usuarios: {response.status} - {data['count']} usuarios")

async def test_websocket_connection():
    """Probar conexión WebSocket básica"""
    print("\n🔌 Probando conexión WebSocket...")
    
    try:
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri) as websocket:
            print("✅ Conexión WebSocket establecida")
            
            # Esperar mensaje de bienvenida
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            print(f"✅ Mensaje de bienvenida recibido: {welcome_data['type']}")
            
            # Enviar mensaje de prueba
            test_message = {
                "type": "chat_message",
                "message": "Mensaje de prueba desde script de testing"
            }
            await websocket.send(json.dumps(test_message))
            print("✅ Mensaje de prueba enviado")
            
            # Esperar respuesta (mensaje debería ser retransmitido)
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('type') == 'chat_message':
                print(f"✅ Mensaje retransmitido correctamente: {response_data['message'][:30]}...")
            else:
                print(f"📄 Otro tipo de mensaje recibido: {response_data['type']}")
            
            # Test ping/pong
            ping_msg = {"type": "ping"}
            await websocket.send(json.dumps(ping_msg))
            
            pong_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            pong_data = json.loads(pong_response)
            
            if pong_data.get('type') == 'pong':
                print("✅ Ping/Pong funciona correctamente")
            
    except Exception as e:
        print(f"❌ Error en WebSocket: {e}")

async def test_message_validation():
    """Probar validaciones de mensaje"""
    print("\n🛡️ Probando validaciones de mensaje...")
    
    try:
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri) as websocket:
            # Esperar mensaje de bienvenida
            await websocket.recv()
            
            # Test mensaje muy largo
            long_message = {
                "type": "chat_message",
                "message": "A" * 600  # Más de 500 caracteres
            }
            await websocket.send(json.dumps(long_message))
            
            # Deberías recibir el mensaje truncado
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if len(response_data.get('message', '')) <= 503:  # 500 + "..."
                print("✅ Limitación de longitud funciona")
            
            # Test mensaje con HTML
            html_message = {
                "type": "chat_message",
                "message": "<script>alert('xss')</script>Mensaje normal"
            }
            await websocket.send(json.dumps(html_message))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if "&lt;script&gt;" in response_data.get('message', ''):
                print("✅ Sanitización HTML funciona")
            
    except Exception as e:
        print(f"❌ Error en validaciones: {e}")

async def simulate_multiple_users():
    """Simular múltiples usuarios conectados"""
    print("\n👥 Simulando múltiples usuarios...")
    
    connections = []
    try:
        # Crear 3 conexiones simultáneas
        for i in range(3):
            uri = "ws://localhost:8000/ws"
            websocket = await websockets.connect(uri)
            connections.append(websocket)
            
            # Esperar mensaje de bienvenida
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            username = welcome_data['user_info']['username']
            print(f"✅ Usuario {username} conectado")
            
            # Cada usuario envía un mensaje
            await websocket.send(json.dumps({
                "type": "chat_message",
                "message": f"Hola desde {username}"
            }))
        
        print("✅ Múltiples usuarios conectados y enviando mensajes")
        
        # Esperar un poco para ver la interacción
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"❌ Error con múltiples usuarios: {e}")
    finally:
        # Cerrar todas las conexiones
        for ws in connections:
            await ws.close()
        print("✅ Todas las conexiones cerradas")

async def test_rate_limiting():
    """Probar rate limiting"""
    print("\n⏱️ Probando rate limiting...")
    
    try:
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri) as websocket:
            # Esperar mensaje de bienvenida
            await websocket.recv()
            
            print("Enviando muchos mensajes rápidamente...")
            
            # Enviar muchos mensajes rápido
            for i in range(15):
                message = {
                    "type": "chat_message",
                    "message": f"Mensaje spam #{i+1}"
                }
                await websocket.send(json.dumps(message))
                
                # Leer respuesta
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    
                    if response_data.get('type') == 'error':
                        print(f"✅ Rate limiting activado en mensaje #{i+1}")
                        break
                        
                except asyncio.TimeoutError:
                    pass
            
    except Exception as e:
        print(f"❌ Error en rate limiting: {e}")

async def main():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas del backend de chat...")
    print("=" * 50)
    
    try:
        await test_rest_endpoints()
        await test_websocket_connection()
        await test_message_validation()
        await simulate_multiple_users()
        await test_rate_limiting()
        
        print("\n" + "=" * 50)
        print("🎉 ¡Todas las pruebas completadas!")
        
    except Exception as e:
        print(f"\n❌ Error ejecutando pruebas: {e}")
        print("Asegúrate de que el servidor esté ejecutándose en localhost:8000")

if __name__ == "__main__":
    asyncio.run(main())
