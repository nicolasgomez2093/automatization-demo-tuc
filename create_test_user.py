#!/usr/bin/env python3
"""
Script para crear usuario de prueba via API
"""

import requests
import json

def create_user():
    """Crear usuario de prueba via API"""
    url = "https://automatization-demo-tuc.onrender.com/api/auth/register"
    
    user_data = {
        "email": "admin@sistema.com",
        "username": "admin", 
        "password": "admin123",
        "full_name": "Administrador del Sistema",
        "role": "superadmin"
    }
    
    try:
        print("🔧 Creando usuario de prueba...")
        response = requests.post(url, json=user_data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Usuario creado exitosamente!")
            print("📧 Email: admin@sistema.com")
            print("🔑 Password: admin123")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    create_user()
