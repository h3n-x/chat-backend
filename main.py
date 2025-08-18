from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
import json
import uuid
import os
import shutil
import time
from datetime import datetime, timedelta
import logging
import asyncio
import re
from collections import defaultdict
import aiofiles
from pathlib import Path

from config import *
from models import ChatMessage, UserInfo, WebSocketMessage
from utils import setup_logger, log_connection_event, log_message_event
from crypto_utils import chat_crypto

# Configurar logging
logger = setup_logger("chat_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configurar tareas de inicio y cierre de la aplicación"""
    # Startup
    asyncio.create_task(cleanup_expired_files())
    logger.info("🚀 Sistema iniciado - Chat anónimo con archivos temporales")
    logger.info(f"📁 Límites: {MAX_FILE_SIZE/(1024*1024):.1f}MB por archivo, {MAX_FILES_PER_USER} archivos por usuario")
    logger.info(f"⏰ Retención: mensajes {MESSAGE_RETENTION_TIME//60}min, archivos {FILE_RETENTION_TIME//60}min")
    yield
    # Shutdown
    logger.info("🛑 Sistema detenido")

app = FastAPI(
    title="Chat Anónimo Backend", 
    description="API para chat anónimo en tiempo real con WebSockets",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS para desarrollo y producción
import os

# Obtener orígenes permitidos de variables de entorno
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://write-ghost.netlify.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://192.168.*:3000",  # Red local
        "http://192.168.19.1:3000",  # IP específica del usuario
        "https://write-ghost.netlify.app",  # Tu dominio de Netlify
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Crear directorio de uploads y servir archivos estáticos
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

class ConnectionManager:
    def __init__(self):
        # Lista de conexiones activas
        self.active_connections: List[WebSocket] = []
        # Información de usuarios conectados {websocket: user_info}
        self.connected_users: Dict[WebSocket, Dict] = {}
        # Historial de mensajes (en memoria, en producción usar base de datos)
        self.message_history: List[Dict] = []
        # Timestamps de mensajes para auto-eliminación: {message_id: timestamp}
        self.message_timestamps: Dict[str, datetime] = {}
        # Contador de usuarios anónimos
        self.anonymous_counter = 0
        # Rate limiting: {user_id: [timestamps]}
        self.user_message_times: Dict[str, List[datetime]] = defaultdict(list)
        # Usuarios baneados temporalmente
        self.banned_users: Dict[str, datetime] = {}
        # Tracking de usuarios únicos por sesión
        self.user_sessions: Dict[str, WebSocket] = {}
        
        # *** SISTEMA DE CHATS PRIVADOS ***
        # Salas privadas: {room_id: {"users": set(), "messages": [], "created_at": datetime, "name": str}}
        self.private_rooms: Dict[str, Dict] = {}
        # Usuario a sala: {websocket: room_id}
        self.user_rooms: Dict[WebSocket, str] = {}
        
        # *** SISTEMA DE CIFRADO E2EE ***
        # Claves de salas privadas: {room_id: key_data}
        self.room_keys: Dict[str, str] = {}
        # Clave del chat público (se genera al inicio)
        self.public_chat_key: str = None
        # Claves públicas de usuarios: {user_id: public_key}
        self.user_public_keys: Dict[str, str] = {}
        
        # *** SISTEMA DE CIFRADO E2EE MEJORADO ***
        self.crypto = chat_crypto
        # Clave del chat público (se genera al inicio)
        self.public_chat_key: str = None
        
        # *** SISTEMA DE ARCHIVOS MEJORADO PARA MÁXIMO ANONIMATO ***
        # Archivos subidos: {file_id: {"path": str, "uploaded_at": datetime, "user_id": str, "room_id": str}}
        self.uploaded_files: Dict[str, Dict] = {}
        # Tracking por usuario: {user_id: [file_ids]}
        self.user_files: Dict[str, List[str]] = defaultdict(list)
        # Crear directorio de uploads temporal si no existe
        self.upload_dir = Path(UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)
        
        # Generar clave para chat público al inicializar
        self.generate_public_chat_key()
        
        # Flag para saber si la tarea de limpieza ya está iniciada
        self.cleanup_task_started = False
    
    def generate_public_chat_key(self):
        """Generar una clave temporal para el chat público"""
        self.public_chat_key = self.crypto.generate_key()
        self.crypto.set_public_chat_key(self.public_chat_key)
        logger.info("🔐 Clave del chat público generada con cifrado mejorado")
        # Códigos de invitación: {invite_code: room_id}
        self.invite_codes: Dict[str, str] = {}
    
    def start_message_cleanup_task(self):
        """Iniciar tarea en segundo plano para limpiar mensajes automáticamente"""
        if not self.cleanup_task_started:
            self.cleanup_task_started = True
            asyncio.create_task(self.cleanup_old_messages())
            asyncio.create_task(self.cleanup_old_files())  # Nueva tarea para archivos
            logger.info("🧹 Tarea de limpieza automática iniciada")
    
    async def cleanup_old_files(self):
        """Limpiar archivos antiguos automáticamente"""
        while True:
            try:
                await asyncio.sleep(FILE_CLEANUP_INTERVAL)
                current_time = datetime.now()
                files_to_remove = []
                
                for file_id, file_data in self.uploaded_files.items():
                    upload_time = file_data["uploaded_at"]
                    if (current_time - upload_time).total_seconds() > FILE_RETENTION_TIME:
                        files_to_remove.append(file_id)
                
                for file_id in files_to_remove:
                    await self.remove_file(file_id)
                    
                if files_to_remove:
                    logger.info(f"🗑️ Eliminados {len(files_to_remove)} archivos antiguos")
                    
            except Exception as e:
                logger.error(f"Error en limpieza de archivos: {e}")
    
    async def save_file(self, file: UploadFile, user_id: str, room_id: str = "general") -> Dict:
        """Guardar archivo subido con límites de privacidad y anonimato"""
        try:
            # VALIDAR LÍMITES DE ARCHIVOS POR USUARIO
            user_file_count = len(self.user_files.get(user_id, []))
            if user_file_count >= MAX_FILES_PER_USER:
                raise HTTPException(
                    status_code=429, 
                    detail=f"Máximo {MAX_FILES_PER_USER} archivos por usuario. Espera a que se eliminen automáticamente."
                )
            
            # VALIDAR LÍMITE TOTAL DE ARCHIVOS EN EL SISTEMA
            if len(self.uploaded_files) >= MAX_TOTAL_FILES:
                # Eliminar archivos más antiguos automáticamente
                await self._cleanup_oldest_files(5)  # Eliminar 5 archivos antiguos
                
                if len(self.uploaded_files) >= MAX_TOTAL_FILES:
                    raise HTTPException(
                        status_code=503, 
                        detail="Sistema temporalmente lleno. Intenta en unos minutos."
                    )
            
            # Generar ID único para el archivo
            file_id = str(uuid.uuid4())
            
            # Sanitizar nombre de archivo
            safe_filename = re.sub(r'[<>:"/\\|?*]', '', file.filename)
            file_extension = Path(safe_filename).suffix.lower()
            
            # Leer contenido del archivo
            content = await file.read()
            
            # CIFRAR EL ARCHIVO ANTES DE GUARDARLO
            encrypted_content = None
            if room_id == "general":
                # Usar clave del chat público
                encrypted_data = self.crypto.encrypt_file_content(content, None)
                if encrypted_data:
                    encrypted_content = encrypted_data["encrypted_content"]
                    logger.info(f"🔐 Archivo {safe_filename} cifrado para chat público")
            else:
                # Usar clave de la sala privada
                encrypted_data = self.crypto.encrypt_file_content(content, room_id)
                if encrypted_data:
                    encrypted_content = encrypted_data["encrypted_content"]
                    logger.info(f"🔐 Archivo {safe_filename} cifrado para sala {room_id}")
            
            # Si no se pudo cifrar, usar contenido original (fallback)
            content_to_save = encrypted_content if encrypted_content else content
            is_encrypted = encrypted_content is not None
            
            # Crear nombre único CON TIMESTAMP para evitar colisiones
            timestamp = int(time.time())
            unique_filename = f"{timestamp}_{file_id[:8]}_{safe_filename}"
            file_path = self.upload_dir / unique_filename
            
            # Guardar archivo (cifrado o original)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content_to_save)
            
            # Guardar información del archivo
            file_info = {
                "path": str(file_path),
                "filename": safe_filename,
                "size": len(content),  # Tamaño original
                "encrypted_size": len(content_to_save),  # Tamaño cifrado
                "mime_type": file.content_type,
                "uploaded_at": datetime.now(),
                "user_id": user_id,
                "room_id": room_id,
                "is_encrypted": is_encrypted
            }
            
            # Registrar archivo en tracking
            self.uploaded_files[file_id] = file_info
            self.user_files[user_id].append(file_id)
            
            encryption_status = "cifrado" if is_encrypted else "sin cifrar"
            logger.info(f"📁 Archivo guardado ({encryption_status}): {safe_filename} ({len(content)} bytes) - Usuario: {user_file_count + 1}/{MAX_FILES_PER_USER}")
            
            return {
                "file_id": file_id,
                "filename": safe_filename,
                "size": len(content),
                "mime_type": file.content_type,
                "url": f"/files/{file_id}",
                "is_encrypted": is_encrypted,
                "retention_minutes": FILE_RETENTION_TIME // 60
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error guardando archivo: {e}")
            raise HTTPException(status_code=500, detail="Error guardando archivo")
    
    async def remove_file(self, file_id: str) -> bool:
        """Eliminar archivo y su información"""
        try:
            if file_id in self.uploaded_files:
                file_data = self.uploaded_files[file_id]
                file_path = Path(file_data["path"])
                user_id = file_data.get("user_id")
                
                # Eliminar archivo físico
                if file_path.exists():
                    file_path.unlink()
                
                # Eliminar de tracking
                del self.uploaded_files[file_id]
                
                # Eliminar de tracking por usuario
                if user_id and user_id in self.user_files:
                    if file_id in self.user_files[user_id]:
                        self.user_files[user_id].remove(file_id)
                    
                    # Limpiar lista vacía
                    if not self.user_files[user_id]:
                        del self.user_files[user_id]
                
                logger.info(f"🗑️ Archivo eliminado: {file_data['filename']}")
                return True
                
        except Exception as e:
            logger.error(f"Error eliminando archivo {file_id}: {e}")
        
        return False
    
    async def _cleanup_oldest_files(self, count: int = 5):
        """Eliminar los archivos más antiguos del sistema"""
        try:
            # Ordenar archivos por fecha de subida
            sorted_files = sorted(
                self.uploaded_files.items(),
                key=lambda x: x[1]["uploaded_at"]
            )
            
            # Eliminar los más antiguos
            for i in range(min(count, len(sorted_files))):
                file_id = sorted_files[i][0]
                await self.remove_file(file_id)
                
            logger.info(f"🧹 Eliminados {min(count, len(sorted_files))} archivos antiguos por límite del sistema")
            
        except Exception as e:
            logger.error(f"Error en limpieza de archivos antiguos: {e}")
    
    def _cleanup_user_files_on_disconnect(self, user_id: str):
        """Limpiar archivos de un usuario cuando se desconecta (opcional para máxima privacidad)"""
        try:
            if user_id in self.user_files:
                file_ids_to_remove = self.user_files[user_id].copy()
                for file_id in file_ids_to_remove:
                    # Eliminar archivo de forma asíncrona
                    asyncio.create_task(self.remove_file(file_id))
                
                logger.info(f"🧹 Programada eliminación de {len(file_ids_to_remove)} archivos del usuario desconectado")
                
        except Exception as e:
            logger.error(f"Error limpiando archivos de usuario {user_id}: {e}")
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """Obtener información de un archivo"""
        return self.uploaded_files.get(file_id)
    
    def start_auto_cleanup(self):
        """Iniciar sistema de auto-eliminación de mensajes"""
        if not self.cleanup_task_started:
            try:
                asyncio.create_task(self.auto_cleanup_messages())
                self.cleanup_task_started = True
                logger.info("🧹 Sistema de auto-eliminación de mensajes iniciado (30 segundos)")
            except RuntimeError:
                # No hay loop de eventos corriendo, se iniciará más tarde
                logger.info("🧹 Sistema de auto-eliminación se iniciará cuando haya un loop de eventos")
                pass
    
    async def auto_cleanup_messages(self):
        """Tarea en segundo plano para eliminar mensajes automáticamente cada 30 segundos"""
        while True:
            try:
                await asyncio.sleep(30)  # Esperar 30 segundos
                current_time = datetime.now()
                
                # Limpiar mensajes del chat público que tienen más de 30 segundos
                messages_to_remove = []
                for i, message in enumerate(self.message_history):
                    message_id = message.get('id')
                    if message_id and message_id in self.message_timestamps:
                        message_time = self.message_timestamps[message_id]
                        if (current_time - message_time).total_seconds() > 30:
                            messages_to_remove.append(i)
                            del self.message_timestamps[message_id]
                
                # Eliminar mensajes en orden inverso para no afectar los índices
                for i in reversed(messages_to_remove):
                    del self.message_history[i]
                
                if messages_to_remove:
                    logger.info(f"🗑️ Auto-eliminados {len(messages_to_remove)} mensajes después de 30 segundos")
                
                # Limpiar mensajes de salas privadas también
                for room_id in list(self.private_rooms.keys()):
                    room_messages = self.private_rooms[room_id].get("messages", [])
                    room_messages_to_remove = []
                    
                    for i, message in enumerate(room_messages):
                        message_id = message.get('id')
                        if message_id and message_id in self.message_timestamps:
                            message_time = self.message_timestamps[message_id]
                            if (current_time - message_time).total_seconds() > 30:
                                room_messages_to_remove.append(i)
                                del self.message_timestamps[message_id]
                    
                    # Eliminar mensajes de la sala privada
                    for i in reversed(room_messages_to_remove):
                        del self.private_rooms[room_id]["messages"][i]
                    
                    if room_messages_to_remove:
                        logger.info(f"🗑️ Auto-eliminados {len(room_messages_to_remove)} mensajes de sala privada {room_id}")
                
                # Limpiar timestamps huérfanos (sin mensaje asociado)
                orphaned_timestamps = []
                for message_id in self.message_timestamps:
                    # Verificar si el message_id existe en algún historial
                    found = False
                    for message in self.message_history:
                        if message.get('id') == message_id:
                            found = True
                            break
                    
                    if not found:
                        # Verificar en salas privadas
                        for room in self.private_rooms.values():
                            for message in room.get("messages", []):
                                if message.get('id') == message_id:
                                    found = True
                                    break
                            if found:
                                break
                    
                    if not found:
                        orphaned_timestamps.append(message_id)
                
                for message_id in orphaned_timestamps:
                    del self.message_timestamps[message_id]
                
                if orphaned_timestamps:
                    logger.info(f"🧹 Limpiados {len(orphaned_timestamps)} timestamps huérfanos")
                    
            except Exception as e:
                logger.error(f"❌ Error en auto-limpieza de mensajes: {e}")
                # Continuar con la tarea aunque haya errores
    
    def _cleanup_duplicate_users(self):
        """Limpiar usuarios duplicados o conexiones rotas de manera más agresiva"""
        connections_to_remove = []
        
        # Verificar conexiones WebSocket válidas
        for ws in list(self.active_connections):
            try:
                # Verificar si la conexión está cerrada
                if hasattr(ws, 'client_state') and ws.client_state == 3:  # CLOSED
                    connections_to_remove.append(ws)
                elif ws not in self.connected_users:
                    connections_to_remove.append(ws)
                # Verificar si la conexión responde
                elif hasattr(ws, 'application_state') and ws.application_state == 3:  # CLOSED
                    connections_to_remove.append(ws)
            except Exception:
                # Si hay cualquier error, considerar la conexión como rota
                connections_to_remove.append(ws)
        
        # Verificar conexiones huérfanas en connected_users
        orphaned_users = []
        for ws in list(self.connected_users.keys()):
            if ws not in self.active_connections:
                orphaned_users.append(ws)
        
        # Remover conexiones rotas y huérfanas
        for ws in connections_to_remove + orphaned_users:
            if ws in self.active_connections:
                self.active_connections.remove(ws)
            if ws in self.connected_users:
                del self.connected_users[ws]
            if ws in self.user_rooms:
                del self.user_rooms[ws]
        
        # Sincronizar active_connections con connected_users
        self.active_connections = [ws for ws in self.active_connections if ws in self.connected_users]
        
        if connections_to_remove or orphaned_users:
            removed_count = len(connections_to_remove) + len(orphaned_users)
            logger.info(f"Cleanup: {removed_count} conexiones eliminadas. Activas: {len(self.active_connections)}")
        
        return len(connections_to_remove) + len(orphaned_users)
        
        self.active_connections = valid_connections
        
        logger.info(f"Cleanup: {len(connections_to_remove)} conexiones eliminadas. Activas: {len(self.active_connections)}")
    
    def _is_rate_limited(self, user_id: str) -> bool:
        """Verificar si el usuario está siendo rate limited"""
        now = datetime.now()
        user_times = self.user_message_times[user_id]
        
        # Limpiar timestamps antiguos (últimos 60 segundos)
        user_times[:] = [t for t in user_times if now - t < timedelta(seconds=60)]
        
        # Verificar límite (máximo 10 mensajes por minuto)
        if len(user_times) >= 10:
            return True
            
        return False
    
    def _is_user_banned(self, user_id: str) -> bool:
        """Verificar si el usuario está baneado temporalmente"""
        if user_id in self.banned_users:
            if datetime.now() < self.banned_users[user_id]:
                return True
            else:
                # Expiró el ban
                del self.banned_users[user_id]
        return False
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitizar mensaje para prevenir ataques XSS básicos"""
        # Escapar caracteres HTML básicos
        message = message.replace("<", "&lt;").replace(">", "&gt;")
        message = message.replace("&", "&amp;").replace('"', "&quot;")
        
        # Remover URLs sospechosas (básico)
        message = re.sub(r'https?://[^\s]+', '[URL removida]', message)
        
        # Limitar longitud
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH] + "..."
            
        return message.strip()
    
    def _validate_connection_limit(self) -> bool:
        """Validar que no se exceda el límite de conexiones"""
        return len(self.active_connections) < MAX_CONNECTIONS
    
    async def _close_duplicate_connections(self, client_ip: str, current_websocket: WebSocket):
        """Cerrar conexiones duplicadas del mismo cliente"""
        try:
            duplicates_found = 0
            connections_to_close = []
            
            # Buscar conexiones existentes del mismo IP
            for websocket in self.active_connections:
                if websocket != current_websocket:
                    user_info = self.connected_users.get(websocket)
                    if user_info and user_info.get("ip") == client_ip:
                        connections_to_close.append(websocket)
                        duplicates_found += 1
            
            # Cerrar conexiones duplicadas
            for old_websocket in connections_to_close:
                try:
                    user_info = self.connected_users.get(old_websocket)
                    username = user_info.get("username", "Usuario") if user_info else "Usuario"
                    logger.info(f"🧹 Cerrando conexión duplicada de {username} (IP: {client_ip})")
                    
                    await old_websocket.close(code=1000, reason="Conexión duplicada detectada")
                    self.disconnect(old_websocket)
                except Exception as e:
                    logger.error(f"Error cerrando conexión duplicada: {e}")
            
            if duplicates_found > 0:
                logger.info(f"🧹 Se cerraron {duplicates_found} conexiones duplicadas de IP {client_ip}")
                    
        except Exception as e:
            logger.error(f"Error detectando conexiones duplicadas: {e}")
    
    async def connect(self, websocket: WebSocket) -> Optional[str]:
        """Conectar un nuevo usuario al chat con detección de duplicados"""
        # Verificar límite de conexiones
        if not self._validate_connection_limit():
            await websocket.close(code=1008, reason="Máximo de usuarios alcanzado")
            logger.warning("Conexión rechazada: límite de usuarios alcanzado")
            return None
        
        try:
            await websocket.accept()
        except Exception as e:
            logger.error(f"Error aceptando conexión WebSocket: {e}")
            return None
        
        # Obtener información del cliente
        client_info = websocket.client
        client_ip = client_info.host if client_info else "unknown"
        
        # Detectar y cerrar conexiones duplicadas del mismo IP
        await self._close_duplicate_connections(client_ip, websocket)
        
        self.active_connections.append(websocket)
        
        # Iniciar tarea de limpieza si es la primera conexión
        if not self.cleanup_task_started:
            self.start_message_cleanup_task()
        
        # Generar nombre anónimo único
        self.anonymous_counter += 1
        user_id = str(uuid.uuid4())[:8]
        username = f"Anónimo_{self.anonymous_counter}"
        
        user_info = {
            "id": user_id,
            "username": username,
            "connected_at": datetime.now().isoformat(),
            "color": self._generate_user_color(user_id),
            "ip": client_ip,  # Guardar IP para detección de duplicados
            "message_count": 0
        }
        
        self.connected_users[websocket] = user_info
        
        try:
            # Enviar mensaje de bienvenida al usuario
            await self._send_personal_message(websocket, {
                "type": "welcome",
                "user_info": user_info,
                "message": f"¡Bienvenido al chat, {username}!"
            })
            
            # Enviar clave compartida del chat público inmediatamente
            await self._send_personal_message(websocket, {
                "type": "public_key_response",
                "public_key": self.public_chat_key
            })
            logger.info(f"🔐 Clave compartida enviada automáticamente a {username}")
            
            # Enviar historial de mensajes recientes
            await self._send_message_history(websocket)
            
            # Notificar a todos que un usuario se conectó
            await self.broadcast_system_message(SYSTEM_MESSAGES["user_joined"].format(username=username))
            
            # Enviar lista de usuarios conectados actualizada
            await self.broadcast_user_list()
            
            log_connection_event("CONNECTED", username, len(self.active_connections))
            return user_id
            
        except Exception as e:
            logger.error(f"Error en proceso de conexión: {e}")
            self.disconnect(websocket)
            return None
    
    def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """Desconectar un usuario del chat"""
        username = None
        
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                
                user_info = self.connected_users.get(websocket)
                if user_info:
                    username = user_info["username"]
                    user_id = user_info["id"]
                    
                    # Remover el usuario de todas las salas privadas
                    if websocket in self.user_rooms:
                        room_id = self.user_rooms[websocket]
                        if room_id in self.private_rooms and websocket in self.private_rooms[room_id]["users"]:
                            self.private_rooms[room_id]["users"].remove(websocket)
                        del self.user_rooms[websocket]
                    
                    # Limpiar datos del usuario
                    del self.connected_users[websocket]
                    
                    # Limpiar rate limiting data
                    if user_id in self.user_message_times:
                        del self.user_message_times[user_id]
                    
                    # Limpiar usuarios baneados vencidos
                    if user_id in self.banned_users:
                        if datetime.now() > self.banned_users[user_id]:
                            del self.banned_users[user_id]
                    
                    # Limpiar claves de cifrado del usuario
                    if user_id in self.user_public_keys:
                        del self.user_public_keys[user_id]
                    
                    # Para máxima privacidad, limpiar archivos del usuario al desconectarse
                    # (Opcional - descomenta la siguiente línea si quieres eliminar archivos al desconectar)
                    # self._cleanup_user_files_on_disconnect(user_id)
                    
                    log_connection_event("DISCONNECTED", username, len(self.active_connections))
                    
                    # Forzar limpieza de conexiones duplicadas
                    self._cleanup_duplicate_users()
                    
        except Exception as e:
            logger.error(f"Error en disconnect: {e}")
        
        return username
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Enviar mensaje a un usuario específico"""
        await self._send_personal_message(websocket, message)
    
    async def _send_personal_message(self, websocket: WebSocket, message: dict):
        """Método interno para enviar mensaje personal"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error enviando mensaje personal: {e}")
    
    async def broadcast_message(self, sender_websocket: WebSocket, message: str) -> bool:
        """Enviar mensaje de chat a todos los usuarios"""
        if sender_websocket not in self.connected_users:
            await self._send_personal_message(sender_websocket, {
                "type": "error",
                "message": "Usuario no válido"
            })
            return False
        
        sender_info = self.connected_users[sender_websocket]
        user_id = sender_info["id"]
        
        # Verificar si el usuario está baneado
        if self._is_user_banned(user_id):
            await self._send_personal_message(sender_websocket, {
                "type": "error",
                "message": "Estás temporalmente suspendido del chat"
            })
            return False
        
        # Verificar rate limiting
        if self._is_rate_limited(user_id):
            await self._send_personal_message(sender_websocket, {
                "type": "error",
                "message": "Estás enviando mensajes muy rápido. Espera un momento."
            })
            # Banear temporalmente si abusa
            self.banned_users[user_id] = datetime.now() + timedelta(minutes=5)
            return False
        
        # Sanitizar mensaje
        sanitized_message = self._sanitize_message(message)
        
        if not sanitized_message:
            await self._send_personal_message(sender_websocket, {
                "type": "error",
                "message": "Mensaje vacío o inválido"
            })
            return False
        
        # Registrar tiempo del mensaje para rate limiting
        self.user_message_times[user_id].append(datetime.now())
        
        # Incrementar contador de mensajes del usuario
        sender_info["message_count"] += 1
        
        chat_message = {
            "type": "chat_message",
            "id": str(uuid.uuid4()),
            "user_id": sender_info["id"],
            "username": sender_info["username"],
            "message": sanitized_message,
            "timestamp": datetime.now().isoformat(),
            "color": sender_info["color"]
        }
        
        # Guardar en historial
        self.message_history.append(chat_message)
        
        # Guardar timestamp para auto-eliminación
        if chat_message.get('id'):
            self.message_timestamps[chat_message['id']] = datetime.now()
        
        # Limitar historial
        if len(self.message_history) > MESSAGE_HISTORY_LIMIT:
            self.message_history = self.message_history[-MESSAGE_HISTORY_LIMIT:]
        
        # Enviar a todos los usuarios conectados
        await self._broadcast_to_all(chat_message)
        
        log_message_event(sender_info['username'], len(sanitized_message))
        return True
    
    async def broadcast_system_message(self, message: str):
        """Enviar mensaje del sistema a todos los usuarios"""
        system_message = {
            "type": "system_message",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._broadcast_to_all(system_message)
    
    async def broadcast_user_list(self):
        """Enviar lista actualizada de usuarios conectados"""
        # Limpiar usuarios duplicados antes de enviar la lista
        self._cleanup_duplicate_users()
        
        # Crear lista única de usuarios
        unique_users = {}
        for user_info in self.connected_users.values():
            user_id = user_info["id"]
            if user_id not in unique_users:
                unique_users[user_id] = {
                    "id": user_info["id"],
                    "username": user_info["username"],
                    "color": user_info["color"]
                }
        
        user_list = list(unique_users.values())
        
        user_list_message = {
            "type": "user_list",
            "users": user_list,
            "count": len(user_list)
        }
        
        await self._broadcast_to_all(user_list_message)
    
    async def _broadcast_to_all(self, message: dict):
        """Método interno para enviar mensaje a todos los usuarios"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error enviando mensaje broadcast: {e}")
                disconnected.append(connection)
        
        # Limpiar conexiones rotas
        for connection in disconnected:
            self.disconnect(connection)
    
    async def _send_message_history(self, websocket: WebSocket):
        """NO enviar historial de mensajes para máximo anonimato"""
        # Para máximo anonimato, no enviamos historial de mensajes
        # Los nuevos usuarios empiezan con una sala limpia
        logger.info("🧹 No se envió historial - modo anónimo total activado")
        pass
    
    def cleanup_inactive_data(self):
        """Limpiar datos de usuarios inactivos y caché"""
        try:
            # Limpiar usuarios baneados vencidos
            current_time = datetime.now()
            expired_bans = [uid for uid, ban_time in self.banned_users.items() if current_time > ban_time]
            for uid in expired_bans:
                del self.banned_users[uid]
            
            # Limpiar mensajes antiguos (mantener solo los últimos 100)
            if len(self.message_history) > MESSAGE_HISTORY_LIMIT:
                self.message_history = self.message_history[-MESSAGE_HISTORY_LIMIT:]
            
            # Limpiar rate limiting para usuarios desconectados
            active_user_ids = {info["id"] for info in self.connected_users.values()}
            inactive_users = [uid for uid in self.user_message_times.keys() if uid not in active_user_ids]
            for uid in inactive_users:
                del self.user_message_times[uid]
                
            logger.info(f"Limpieza completada: {len(expired_bans)} bans expirados, {len(inactive_users)} usuarios inactivos limpiados")
            
        except Exception as e:
            logger.error(f"Error en cleanup_inactive_data: {e}")

    def _generate_user_color(self, user_id: str) -> str:
        """Generar color único para el usuario basado en su ID"""
        # Usar hash del user_id para seleccionar color consistente
        hash_value = hash(user_id) % len(USER_COLORS)
        return USER_COLORS[hash_value]
    
    # *** MÉTODOS PARA CHATS PRIVADOS ***
    
    def create_private_room(self, room_name: str = None) -> str:
        """Crear una sala privada y retornar room_id (6 dígitos)"""
        # Generar ID de sala de 6 caracteres alfanuméricos
        import random
        import string
        import secrets
        import base64
        
        room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Asegurar que el ID sea único
        while room_id in self.private_rooms:
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Generar clave de cifrado para la sala
        room_key_bytes = secrets.token_bytes(32)  # 256 bits para AES-256
        room_key = base64.b64encode(room_key_bytes).decode('utf-8')
        
        self.private_rooms[room_id] = {
            "users": set(),
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "name": room_name or f"Sala {room_id}"
        }
        
        # Almacenar clave de la sala
        self.room_keys[room_id] = room_key
        
        logger.info(f"Sala privada creada: {room_id} con cifrado E2EE")
        return room_id
    
    async def join_private_room(self, websocket: WebSocket, room_id: str) -> bool:
        """Unirse a una sala privada usando room_id"""
        room_id = room_id.upper()  # Normalizar a mayúsculas
        
        if room_id not in self.private_rooms:
            return False
        
        # Remover usuario de otras salas si estaba en alguna
        if websocket in self.user_rooms:
            old_room = self.user_rooms[websocket]
            if old_room in self.private_rooms and websocket in self.private_rooms[old_room]["users"]:
                self.private_rooms[old_room]["users"].remove(websocket)
        
        # Añadir a la nueva sala
        self.private_rooms[room_id]["users"].add(websocket)
        self.user_rooms[websocket] = room_id
        
        user_info = self.connected_users.get(websocket)
        if user_info:
            username = user_info["username"]
            logger.info(f"Usuario {username} se unió a sala {room_id}")
            
            # Enviar clave de cifrado de la sala al usuario
            if room_id in self.room_keys:
                await self._send_personal_message(websocket, {
                    "type": "room_key_share",
                    "room_id": room_id,
                    "room_key": self.room_keys[room_id]
                })
                logger.info(f"Clave de sala {room_id} enviada a {username}")
            else:
                logger.error(f"No se encontró clave para sala {room_id}")
            
            # Notificar a otros usuarios en la sala
            await self.broadcast_to_room(room_id, {
                "type": "user_joined_room",
                "username": username,
                "room_id": room_id
            }, exclude=websocket)
            
            # Update user list in the room
            await self.broadcast_room_user_list(room_id)
            
            return True
        
        return False

    async def leave_room(self, websocket: WebSocket):
        """Salir de la sala actual"""
        if websocket not in self.user_rooms:
            return
            
        room_id = self.user_rooms[websocket]
        user_info = self.connected_users.get(websocket)
        
        # Remover de la sala
        if room_id in self.private_rooms:
            self.private_rooms[room_id]["users"].discard(websocket)
            
            # Notificar salida si hay otros usuarios
            if self.private_rooms[room_id]["users"] and user_info:
                await self.broadcast_to_room(room_id, {
                    "type": "system_message",
                    "message": f"{user_info['username']} ha salido de la sala",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Update user list
                await self.broadcast_room_user_list(room_id)
            
            # Si la sala está vacía, eliminarla
            if not self.private_rooms[room_id]["users"]:
                # Limpiar clave de la sala
                if room_id in self.room_keys:
                    del self.room_keys[room_id]
                del self.private_rooms[room_id]
                logger.info(f"Sala privada eliminada: {room_id}")
        
        del self.user_rooms[websocket]
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude: WebSocket = None):
        """Enviar mensaje a todos los usuarios de una sala específica"""
        if room_id not in self.private_rooms:
            return
            
        disconnected = []
        for ws in self.private_rooms[room_id]["users"]:
            if ws == exclude:
                continue
                
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error enviando mensaje a sala: {e}")
                disconnected.append(ws)
        
        # Limpiar conexiones rotas
        for ws in disconnected:
            self.private_rooms[room_id]["users"].discard(ws)
    
    async def broadcast_room_user_list(self, room_id: str):
        """Enviar lista de usuarios de una sala específica"""
        if room_id not in self.private_rooms:
            return
            
        users_in_room = []
        for ws in self.private_rooms[room_id]["users"]:
            if ws in self.connected_users:
                user_info = self.connected_users[ws]
                users_in_room.append({
                    "id": user_info["id"],
                    "username": user_info["username"],
                    "color": user_info["color"]
                })
        
        message = {
            "type": "room_user_list",
            "users": users_in_room,
            "count": len(users_in_room),
            "room_id": room_id,
            "room_name": self.private_rooms[room_id]["name"]
        }
        
        await self.broadcast_to_room(room_id, message)
    
    async def send_room_message(self, sender_websocket: WebSocket, message: str) -> bool:
        """Enviar mensaje a la sala donde está el usuario"""
        if sender_websocket not in self.user_rooms:
            # Usuario está en chat público
            return await self.broadcast_message(sender_websocket, message)
        
        room_id = self.user_rooms[sender_websocket]
        if room_id not in self.private_rooms:
            return False
            
        sender_info = self.connected_users.get(sender_websocket)
        if not sender_info:
            return False
        
        # Validaciones similares al chat público
        user_id = sender_info["id"]
        if self._is_user_banned(user_id) or self._is_rate_limited(user_id):
            return False
        
        sanitized_message = self._sanitize_message(message)
        if not sanitized_message:
            return False
        
        # Registrar tiempo del mensaje
        self.user_message_times[user_id].append(datetime.now())
        sender_info["message_count"] += 1
        
        chat_message = {
            "type": "room_message",
            "id": str(uuid.uuid4()),
            "user_id": sender_info["id"],
            "username": sender_info["username"],
            "message": sanitized_message,
            "timestamp": datetime.now().isoformat(),
            "color": sender_info["color"],
            "room_id": room_id
        }
        
        # Guardar en historial de la sala
        self.private_rooms[room_id]["messages"].append(chat_message)
        
        # Guardar timestamp para auto-eliminación
        if chat_message.get('id'):
            self.message_timestamps[chat_message['id']] = datetime.now()
        
        # Limitar historial de la sala
        if len(self.private_rooms[room_id]["messages"]) > MESSAGE_HISTORY_LIMIT:
            self.private_rooms[room_id]["messages"] = self.private_rooms[room_id]["messages"][-MESSAGE_HISTORY_LIMIT:]
        
        # Enviar a todos en la sala
        await self.broadcast_to_room(room_id, chat_message)
        
        log_message_event(sender_info['username'], len(sanitized_message))
        return True

    async def broadcast_message_encrypted(self, sender_websocket: WebSocket, message: str, encrypted_data: dict) -> bool:
        """Enviar mensaje cifrado al chat público"""
        if sender_websocket not in self.connected_users:
            await self._send_personal_message(sender_websocket, {
                "type": "error",
                "message": "Usuario no válido"
            })
            return False

        sender_info = self.connected_users[sender_websocket]
        user_id = sender_info["id"]

        # Validaciones de seguridad
        if self._is_user_banned(user_id) or self._is_rate_limited(user_id):
            return False

        # Determinar si usar cifrado o texto plano
        if encrypted_data:
            # Mensaje ya cifrado por el cliente
            display_message = "[Mensaje cifrado]"  # Solo para logs
            message_content = None  # No enviar texto plano
        else:
            # Mensaje en texto plano (fallback si no hay cifrado)
            if not message or not message.strip():
                return False
            sanitized_message = self._sanitize_message(message)
            if not sanitized_message:
                return False
            display_message = sanitized_message
            message_content = sanitized_message

        # Registrar tiempo del mensaje para rate limiting
        self.user_message_times[user_id].append(datetime.now())
        sender_info["message_count"] += 1

        chat_message = {
            "type": "chat_message",
            "id": str(uuid.uuid4()),
            "user_id": sender_info["id"],
            "username": sender_info["username"],
            "timestamp": datetime.now().isoformat(),
            "color": sender_info["color"]
        }

        # Agregar datos cifrados o mensaje en texto plano (pero no ambos)
        if encrypted_data:
            chat_message["encrypted"] = encrypted_data
            # No incluir campo "message" para mensajes cifrados
        else:
            chat_message["message"] = message_content
            # No incluir campo "encrypted" para mensajes en texto plano

        # Guardar en historial (solo metadatos si está cifrado)
        history_entry = chat_message.copy()
        if encrypted_data:
            history_entry["message"] = "[Mensaje cifrado]"
        self.message_history.append(history_entry)

        # Guardar timestamp para auto-eliminación
        if history_entry.get('id'):
            self.message_timestamps[history_entry['id']] = datetime.now()

        # Limitar historial
        if len(self.message_history) > MESSAGE_HISTORY_LIMIT:
            self.message_history = self.message_history[-MESSAGE_HISTORY_LIMIT:]

        # Enviar a todos los usuarios conectados
        await self._broadcast_to_all(chat_message)

        log_message_event(sender_info['username'], len(display_message))
        return True

    async def send_room_message_encrypted(self, sender_websocket: WebSocket, message: str, encrypted_data: dict) -> bool:
        """Enviar mensaje cifrado a la sala donde está el usuario"""
        if sender_websocket not in self.user_rooms:
            return await self.broadcast_message_encrypted(sender_websocket, message, encrypted_data)

        room_id = self.user_rooms[sender_websocket]
        if room_id not in self.private_rooms:
            return False

        sender_info = self.connected_users.get(sender_websocket)
        if not sender_info:
            return False

        # Validaciones similares al chat público
        user_id = sender_info["id"]
        if self._is_user_banned(user_id) or self._is_rate_limited(user_id):
            return False

        decrypted_message = None
        display_message = "[Mensaje cifrado]"
        
        if encrypted_data and self.crypto.verify_encrypted_data(encrypted_data):
            # Intentar descifrar usando la clave de la sala
            decrypted_message = self.crypto.decrypt_message(encrypted_data, room_id)
            if decrypted_message:
                display_message = f"[Cifrado sala: {len(decrypted_message)} chars]"
                logger.info(f"✅ Mensaje de sala {room_id} cifrado validado")
            else:
                logger.warning(f"⚠️ No se pudo descifrar mensaje de sala {room_id}")
        elif message and message.strip():
            sanitized_message = self._sanitize_message(message)
            if not sanitized_message:
                return False
            display_message = sanitized_message
            decrypted_message = sanitized_message
        else:
            return False

        # Registrar tiempo del mensaje
        self.user_message_times[user_id].append(datetime.now())
        sender_info["message_count"] += 1

        chat_message = {
            "type": "room_message",
            "id": str(uuid.uuid4()),
            "room_id": room_id,
            "user_id": sender_info["id"],
            "username": sender_info["username"],
            "timestamp": datetime.now().isoformat(),
            "color": sender_info["color"]
        }

        if encrypted_data and self.crypto.verify_encrypted_data(encrypted_data):
            chat_message["encrypted"] = encrypted_data
            chat_message["type"] = "room_message_encrypted"
        else:
            chat_message["message"] = decrypted_message

        # Guardar en historial de la sala
        history_entry = chat_message.copy()
        if encrypted_data:
            history_entry["message"] = "[Mensaje cifrado]"
        self.private_rooms[room_id]["messages"].append(history_entry)

        # Guardar timestamp para auto-eliminación
        if history_entry.get('id'):
            self.message_timestamps[history_entry['id']] = datetime.now()

        # Limitar historial de la sala
        if len(self.private_rooms[room_id]["messages"]) > MESSAGE_HISTORY_LIMIT:
            self.private_rooms[room_id]["messages"] = self.private_rooms[room_id]["messages"][-MESSAGE_HISTORY_LIMIT:]

        # Enviar a todos en la sala
        await self.broadcast_to_room(room_id, chat_message)

        log_message_event(sender_info['username'], len(display_message))
        return True

# ==================== ENDPOINTS PARA ARCHIVOS ====================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    room_id: str = Form(default="general")
):
    """Subir un archivo al chat"""
    try:
        # Validar usuario existe
        user_websocket = None
        for ws, user_info in manager.connected_users.items():
            if user_info["id"] == user_id:
                user_websocket = ws
                break
        
        if not user_websocket:
            raise HTTPException(status_code=401, detail="Usuario no conectado")
        
        # Validar tamaño del archivo
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"Archivo demasiado grande. Máximo {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validar tipo de archivo
        if file.content_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Tipo de archivo no permitido: {file.content_type}"
            )
        
        # Resetear stream del archivo
        await file.seek(0)
        
        # Guardar archivo
        file_info = await manager.save_file(file, user_id, room_id)
        
        # Crear mensaje de archivo
        user_info = manager.connected_users[user_websocket]
        file_message = {
            "type": "file_message",
            "id": str(uuid.uuid4()),
            "file_id": file_info["file_id"],
            "filename": file_info["filename"],
            "file_size": file_info["size"],
            "mime_type": file_info["mime_type"],
            "file_url": file_info["url"],
            "user_id": user_id,
            "username": user_info["username"],
            "color": user_info["color"],
            "timestamp": datetime.now().isoformat(),
            "room_id": room_id
        }
        
        # Enviar mensaje a la sala correspondiente
        if room_id == "general":
            # Chat público
            manager.message_history.append(file_message)
            manager.message_timestamps[file_message["id"]] = datetime.now()
            await manager.broadcast(file_message)
        else:
            # Sala privada
            if room_id in manager.private_rooms:
                manager.private_rooms[room_id]["messages"].append(file_message)
                manager.message_timestamps[file_message["id"]] = datetime.now()
                await manager.broadcast_to_room(room_id, file_message)
        
        logger.info(f"📁 Archivo subido: {file_info['filename']} por {user_info['username']}")
        
        return {
            "success": True,
            "message": "Archivo subido exitosamente",
            "file_info": file_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo archivo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/files/{file_id}")
async def get_file(file_id: str):
    """Descargar un archivo por su ID (descifrándolo si es necesario)"""
    try:
        file_info = manager.get_file_info(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        file_path = Path(file_info["path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Archivo no existe en el servidor")
        
        # Leer archivo del disco
        async with aiofiles.open(file_path, 'rb') as f:
            file_content = await f.read()
        
        # Si el archivo está cifrado, descifrarlo
        if file_info.get("is_encrypted", False):
            room_id = file_info.get("room_id")
            
            try:
                if room_id == "general":
                    # Descifrar con clave del chat público
                    decrypted_content = manager.crypto.decrypt_file_content(file_content, None)
                else:
                    # Descifrar con clave de la sala privada
                    decrypted_content = manager.crypto.decrypt_file_content(file_content, room_id)
                
                if decrypted_content:
                    file_content = decrypted_content
                    logger.info(f"🔓 Archivo {file_info['filename']} descifrado exitosamente")
                else:
                    logger.error(f"❌ No se pudo descifrar archivo {file_info['filename']}")
                    raise HTTPException(status_code=500, detail="Error descifrando archivo")
                    
            except Exception as e:
                logger.error(f"Error descifrando archivo: {e}")
                raise HTTPException(status_code=500, detail="Error descifrando archivo")
        
        # Crear respuesta temporal con el contenido descifrado
        import tempfile
        import os
        
        # Crear archivo temporal con el contenido descifrado
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_info["filename"]).suffix) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
        
        # Retornar archivo y programar limpieza
        def cleanup_temp_file():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        import atexit
        atexit.register(cleanup_temp_file)
        
        return FileResponse(
            path=temp_path,
            filename=file_info["filename"],
            media_type=file_info["mime_type"],
            background=cleanup_temp_file  # Limpiar después de enviar
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error descargando archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.delete("/files/{file_id}")
async def delete_file(file_id: str, user_id: str = Form(...)):
    """Eliminar un archivo (solo el propietario)"""
    try:
        file_info = manager.get_file_info(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Verificar que el usuario es el propietario
        if file_info["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este archivo")
        
        success = await manager.remove_file(file_id)
        if success:
            return {"success": True, "message": "Archivo eliminado exitosamente"}
        else:
            raise HTTPException(status_code=500, detail="Error eliminando archivo")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ==================== ENDPOINTS EXISTENTES ====================

@app.get("/stats")
async def get_stats():
    """Obtener estadísticas detalladas del chat"""
    users_info = []
    for user_info in manager.connected_users.values():
        users_info.append({
            "username": user_info["username"],
            "connected_at": user_info["connected_at"],
            "message_count": user_info.get("message_count", 0),
            "color": user_info["color"]
        })
    
    return {
        "server_stats": {
            "uptime_start": datetime.now().isoformat(),  # En una app real, guardar tiempo de inicio
            "total_users_ever": manager.anonymous_counter,
            "current_users": len(manager.active_connections),
            "message_history_size": len(manager.message_history),
            "banned_users_count": len(manager.banned_users)
        },
        "current_users": users_info,
        "recent_messages": manager.message_history[-5:] if manager.message_history else []
    }

@app.get("/users")
async def get_users():
    """Obtener lista de usuarios conectados"""
    return {
        "users": [
            {
                "id": user_info["id"],
                "username": user_info["username"],
                "color": user_info["color"],
                "connected_at": user_info["connected_at"],
                "message_count": user_info.get("message_count", 0)
            }
            for user_info in manager.connected_users.values()
        ],
        "count": len(manager.connected_users)
    }

@app.post("/rooms/create")
async def create_room():
    """Crear una nueva sala privada"""
    try:
        room_id = manager.create_private_room()
        return {
            "status": "success",
            "room_id": room_id,
            "message": "Sala privada creada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error creando sala privada: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Obtener información de una sala privada"""
    if room_id not in manager.private_rooms:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    
    room_data = manager.private_rooms[room_id]
    user_list = []
    
    for websocket in room_data["users"]:
        if websocket in manager.connected_users:
            user_info = manager.connected_users[websocket]
            user_list.append({
                "id": user_info["id"],
                "username": user_info["username"],
                "color": user_info["color"]
            })
    
    return {
        "room_id": room_id,
        "created_at": room_data["created_at"],
        "user_count": len(user_list),
        "users": user_list
    }

@app.post("/admin/cleanup")
async def admin_cleanup():
    """Endpoint para limpiar caché y datos inactivos"""
    try:
        manager.cleanup_inactive_data()
        return {
            "status": "success",
            "message": "Limpieza completada exitosamente",
            "active_connections": len(manager.active_connections),
            "total_messages": len(manager.message_history),
            "banned_users": len(manager.banned_users)
        }
    except Exception as e:
        logger.error(f"Error en limpieza: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/admin/broadcast")
async def admin_broadcast(message: dict):
    """Endpoint para que el admin envíe mensajes del sistema"""
    # En producción, añadir autenticación
    system_message = message.get("message", "")
    if system_message:
        await manager.broadcast_system_message(f"[ADMIN] {system_message}")
        return {"status": "message_sent", "message": system_message}
    else:
        raise HTTPException(status_code=400, detail="Mensaje requerido")

# Instancia global del manager de conexiones
manager = ConnectionManager()

async def cleanup_expired_files():
    """Tarea periódica para limpiar archivos expirados"""
    while True:
        try:
            now = time.time()
            expired_files = []
            
            for file_id, file_data in manager.uploaded_files.items():
                if now - file_data["uploaded_at"] > FILE_RETENTION_TIME:
                    expired_files.append(file_id)
            
            for file_id in expired_files:
                await manager.remove_file(file_id)
            
            if expired_files:
                logger.info(f"🧹 Limpieza automática: {len(expired_files)} archivos expirados eliminados")
            
        except Exception as e:
            logger.error(f"Error en limpieza automática de archivos: {e}")
        
        # Ejecutar cada 5 minutos
        await asyncio.sleep(300)

@app.get("/")
async def root():
    return {
        "message": "Chat Anónimo Backend API",
        "status": "running",
        "active_users": len(manager.active_connections),
        "endpoints": {
            "websocket": "/ws",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint de salud con métricas detalladas"""
    total_messages = sum(user_info.get("message_count", 0) for user_info in manager.connected_users.values())
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "active_connections": len(manager.active_connections),
            "total_messages_in_history": len(manager.message_history),
            "total_messages_sent": total_messages,
            "banned_users": len(manager.banned_users),
            "anonymous_counter": manager.anonymous_counter
        },
        "limits": {
            "max_connections": MAX_CONNECTIONS,
            "max_message_length": MAX_MESSAGE_LENGTH,
            "message_history_limit": MESSAGE_HISTORY_LIMIT
        }
    }

@app.post("/rooms/create")
async def create_room():
    """Crear una nueva sala privada"""
    try:
        room_id = manager.create_private_room()
        logger.info(f"🏠 Sala privada creada via REST API: {room_id}")
        return {"room_id": room_id, "status": "created"}
    except Exception as e:
        logger.error(f"Error creando sala via REST API: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/rooms/{room_id}/info")
async def get_room_info(room_id: str):
    """Obtener información de una sala"""
    try:
        room_id = room_id.upper()
        if room_id in manager.private_rooms:
            room_data = manager.private_rooms[room_id]
            return {
                "room_id": room_id,
                "exists": True,
                "user_count": len(room_data["users"]),
                "created_at": room_data["created_at"],
                "name": room_data.get("name", f"Sala {room_id}")
            }
        else:
            return {"room_id": room_id, "exists": False}
    except Exception as e:
        logger.error(f"Error obteniendo info de sala {room_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = await manager.connect(websocket)
    
    if user_id is None:
        # Conexión fue rechazada
        return
    
    # Configurar heartbeat para mantener conexión viva
    heartbeat_task = None
    
    try:
        # Iniciar heartbeat
        async def heartbeat():
            while True:
                try:
                    await asyncio.sleep(PING_INTERVAL)
                    await manager.send_personal_message(websocket, {"type": "ping"})
                except Exception:
                    break
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        while True:
            try:
                # Timeout para detectar conexiones muertas
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout en websocket, cerrando conexión")
                break
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "")
                
                if message_type == "request_public_key":
                    # Cliente solicita clave del chat público
                    user_info = manager.connected_users.get(websocket)
                    
                    # Enviar clave del chat público (clave simétrica compartida)
                    await manager.send_personal_message(websocket, {
                        "type": "public_key_response",
                        "public_key": manager.public_chat_key
                    })
                    
                    logger.info(f"🔐 Clave del chat público enviada a {user_info.get('username', 'Usuario') if user_info else 'Usuario'}")
                
                elif message_type == "chat_message":
                    # Obtener datos del mensaje (cifrado o texto plano)
                    message_content = message_data.get("message", "")
                    encrypted_data = message_data.get("encrypted")
                    room_id = message_data.get("room_id")
                    
                    # Verificar que haya contenido (texto plano o cifrado)
                    if message_content or encrypted_data:
                        if room_id:
                            # Primero unirse a la sala si no está ya en ella
                            if websocket not in manager.user_rooms or manager.user_rooms[websocket] != room_id:
                                await manager.join_private_room(websocket, room_id)
                            # Enviar mensaje a la sala (cifrado o texto plano)
                            success = await manager.send_room_message_encrypted(websocket, message_content, encrypted_data)
                        else:
                            # Mensaje para chat público (cifrado o texto plano)
                            success = await manager.broadcast_message_encrypted(websocket, message_content, encrypted_data)
                        
                        if not success:
                            # El mensaje fue rechazado, enviar confirmación negativa
                            await manager.send_personal_message(websocket, {
                                "type": "message_rejected",
                                "reason": "Mensaje no pudo ser enviado"
                            })
                
                elif message_type == "file_message":
                    # Manejar mensaje de archivo desde WebSocket (principalmente para notificaciones)
                    file_id = message_data.get("file_id")
                    room_id = message_data.get("room_id", "general")
                    
                    if file_id:
                        # Verificar que el archivo existe
                        file_info = manager.get_file_info(file_id)
                        if file_info:
                            user_info = manager.connected_users.get(websocket)
                            if user_info:
                                # El archivo ya fue procesado por el endpoint /upload
                                # Solo confirmar recepción
                                await manager.send_personal_message(websocket, {
                                    "type": "file_received",
                                    "file_id": file_id,
                                    "message": "Archivo procesado correctamente"
                                })
                        else:
                            await manager.send_personal_message(websocket, {
                                "type": "error",
                                "message": "Archivo no encontrado"
                            })
                
                elif message_type == "join_room":
                    room_id = message_data.get("room_id", "").strip()
                    if room_id:
                        success = await manager.join_private_room(websocket, room_id)
                        if success:
                            await manager.send_personal_message(websocket, {
                                "type": "room_joined",
                                "room_id": room_id,
                                "message": f"Te has unido a la sala {room_id}"
                            })
                        else:
                            await manager.send_personal_message(websocket, {
                                "type": "error",
                                "message": "No se pudo unir a la sala. Verifica el código de invitación."
                            })
                
                elif message_type == "leave_room":
                    room_id = message_data.get("room_id", "").strip()
                    if room_id:
                        await manager.leave_room(websocket)
                        await manager.send_personal_message(websocket, {
                            "type": "room_left",
                            "room_id": room_id,
                            "message": f"Has salido de la sala {room_id}"
                        })
                
                elif message_type == "ping":
                    # Responder a ping para mantener conexión viva
                    await manager.send_personal_message(websocket, {"type": "pong"})
                
                elif message_type == "pong":
                    # Cliente respondió a nuestro ping
                    pass
                
                elif message_type == "reaction":
                    # Reacción a un mensaje
                    user_info = manager.connected_users.get(websocket)
                    if user_info:
                        username = user_info.get('username') if isinstance(user_info, dict) else user_info
                        message_id = message_data.get("messageId")
                        emoji = message_data.get("emoji")
                        room_id = message_data.get("room", "general")
                        
                        if message_id and emoji:
                            # Broadcast reacción a otros usuarios en la sala
                            reaction_message = {
                                "type": "reaction_update",
                                "messageId": message_id,
                                "emoji": emoji,
                                "username": username,
                                "room": room_id
                            }
                            
                            # Almacenar la reacción en el historial del mensaje
                            for msg in manager.message_history:
                                if str(msg.get("id")) == str(message_id):
                                    if "reactions" not in msg:
                                        msg["reactions"] = {}
                                    if emoji not in msg["reactions"]:
                                        msg["reactions"][emoji] = 0
                                    msg["reactions"][emoji] += 1
                                    break
                            
                            # Enviar a todos los usuarios en la sala (incluyendo al que reaccionó)
                            if room_id == "general":
                                # Chat público - enviar a todos los usuarios que NO están en sala privada
                                for conn, user in manager.connected_users.items():
                                    if manager.user_rooms.get(conn) is None:
                                        await manager.send_personal_message(conn, reaction_message)
                            else:
                                # Sala privada - enviar a todos los usuarios en esa sala
                                room_data = manager.private_rooms.get(room_id)
                                if room_data and username in room_data["users"]:
                                    for conn, user in manager.connected_users.items():
                                        if manager.user_rooms.get(conn) == room_id:
                                            await manager.send_personal_message(conn, reaction_message)
                
                elif message_type == "typing":
                    # Indicador de escritura
                    user_info = manager.connected_users.get(websocket)
                    if user_info:
                        username = user_info.get('username') if isinstance(user_info, dict) else user_info
                        room_id = message_data.get("room", "general")
                        is_typing = message_data.get("isTyping", False)
                        
                        logger.info(f"🔤 Typing recibido: {username} isTyping={is_typing} room={room_id}")
                        
                        # Broadcast typing status a otros usuarios en la sala
                        typing_message = {
                            "type": "typing_status",
                            "username": username,
                            "isTyping": is_typing,
                            "room": room_id
                        }
                        
                        # Enviar a todos los usuarios en la sala excepto al remitente
                        if room_id == "general":
                            # Chat público - enviar a todos los usuarios que NO están en una sala privada
                            for conn, user in manager.connected_users.items():
                                if conn != websocket and manager.user_rooms.get(conn) is None:
                                    target_username = user.get('username') if isinstance(user, dict) else user
                                    logger.info(f"🔤 Enviando typing_status a {target_username}")
                                    await manager.send_personal_message(conn, typing_message)
                        else:
                            # Sala privada
                            room_data = manager.private_rooms.get(room_id)
                            if room_data and username in room_data["users"]:
                                for conn, user in manager.connected_users.items():
                                    if conn != websocket and manager.user_rooms.get(conn) == room_id:
                                        target_username = user.get('username') if isinstance(user, dict) else user
                                        logger.info(f"🔤 Enviando typing_status a {target_username} en sala {room_id}")
                                        await manager.send_personal_message(conn, typing_message)
                
                else:
                    logger.warning(f"Tipo de mensaje desconocido: {message_type}")
                    await manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": f"Tipo de mensaje no soportado: {message_type}"
                    })
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error decodificando JSON: {data[:100]}... Error: {e}")
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Formato de mensaje inválido"
                })
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}")
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Error interno del servidor"
                })
                
    except WebSocketDisconnect:
        logger.info("Cliente desconectado normalmente")
    except Exception as e:
        logger.error(f"Error inesperado en websocket: {e}")
    finally:
        # Cleanup
        if heartbeat_task:
            heartbeat_task.cancel()
            
        username = manager.disconnect(websocket)
        if username:
            try:
                await manager.broadcast_system_message(SYSTEM_MESSAGES["user_left"].format(username=username))
                await manager.broadcast_user_list()
            except Exception as e:
                logger.error(f"Error notificando desconexión: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
