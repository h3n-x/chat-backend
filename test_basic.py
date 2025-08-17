import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from main import app, manager
from config import MAX_MESSAGE_LENGTH

client = TestClient(app)

def test_root_endpoint():
    """Test del endpoint raíz"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Chat Anónimo Backend API"
    assert data["status"] == "running"
    assert "active_users" in data

def test_health_endpoint():
    """Test del endpoint de salud"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "metrics" in data
    assert "limits" in data

def test_stats_endpoint():
    """Test del endpoint de estadísticas"""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "server_stats" in data
    assert "current_users" in data

def test_users_endpoint():
    """Test del endpoint de usuarios"""
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "count" in data
    assert isinstance(data["users"], list)

def test_admin_broadcast_valid():
    """Test del endpoint de broadcast admin con mensaje válido"""
    response = client.post("/admin/broadcast", json={"message": "Mensaje de prueba"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "message_sent"

def test_admin_broadcast_invalid():
    """Test del endpoint de broadcast admin con mensaje inválido"""
    response = client.post("/admin/broadcast", json={})
    assert response.status_code == 400

def test_message_sanitization():
    """Test de sanitización de mensajes"""
    # Test con el manager directamente
    test_message = "<script>alert('xss')</script>Hello"
    sanitized = manager._sanitize_message(test_message)
    assert "&lt;script&gt;" in sanitized
    assert "<script>" not in sanitized

def test_message_length_limit():
    """Test de límite de longitud de mensaje"""
    long_message = "a" * (MAX_MESSAGE_LENGTH + 100)
    sanitized = manager._sanitize_message(long_message)
    assert len(sanitized) <= MAX_MESSAGE_LENGTH + 3  # +3 por "..."

def test_rate_limiting():
    """Test básico de rate limiting"""
    user_id = "test_user_123"
    
    # Simular que el usuario no está siendo rate limited inicialmente
    assert not manager._is_rate_limited(user_id)
    
    # Simular muchos mensajes rápidos
    from datetime import datetime
    now = datetime.now()
    manager.user_message_times[user_id] = [now] * 11  # Más del límite
    
    # Ahora debería estar rate limited
    assert manager._is_rate_limited(user_id)

def test_user_color_generation():
    """Test de generación de colores únicos"""
    user_id1 = "user1"
    user_id2 = "user2"
    
    color1 = manager._generate_user_color(user_id1)
    color2 = manager._generate_user_color(user_id2)
    
    # Los colores deben ser códigos hex válidos
    assert color1.startswith("#")
    assert len(color1) == 7
    assert color2.startswith("#")
    assert len(color2) == 7
    
    # El mismo usuario debe obtener el mismo color
    color1_again = manager._generate_user_color(user_id1)
    assert color1 == color1_again

def test_connection_limit_validation():
    """Test de validación de límite de conexiones"""
    # Guardar estado original
    original_connections = len(manager.active_connections)
    
    # Simular muchas conexiones
    manager.active_connections = [None] * 150  # Más del límite
    
    assert not manager._validate_connection_limit()
    
    # Restaurar estado original
    manager.active_connections = manager.active_connections[:original_connections]

if __name__ == "__main__":
    # Ejecutar tests básicos
    print("Ejecutando tests básicos...")
    
    test_root_endpoint()
    print("✅ Test endpoint raíz pasado")
    
    test_health_endpoint()
    print("✅ Test endpoint salud pasado")
    
    test_message_sanitization()
    print("✅ Test sanitización pasado")
    
    test_rate_limiting()
    print("✅ Test rate limiting pasado")
    
    test_user_color_generation()
    print("✅ Test generación colores pasado")
    
    print("\n🎉 Todos los tests básicos pasaron correctamente!")
