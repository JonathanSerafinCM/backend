import pytest
from fastapi.testclient import TestClient
from main import app
import random
import string

client = TestClient(app)

def random_string(length=10):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

def test_read_users_me():
    """
    Prueba que un usuario autenticado puede obtener su propia información.
    """
    email = f"test_{random_string()}@example.com"
    password = random_string(12)

    # Registra y hace login para obtener un token
    client.post("/auth/register", json={"email": email, "password": password})
    login_response = client.post("/auth/login", data={"username": email, "password": password})
    token = login_response.json()["access_token"]

    # Llama al endpoint protegido
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/users/me", headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["email"] == email
    assert "id" in data

def test_login_for_access_token():
    """
    Prueba que un usuario puede iniciar sesión y recibir un token de acceso.
    """
    email = f"test_{random_string()}@example.com"
    password = random_string(12)

    # Primero, registra un usuario
    client.post("/auth/register", json={"email": email, "password": password})

    # Luego, intenta iniciar sesión
    response = client.post("/auth/login", data={"username": email, "password": password})
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_register_user():
    """
    Prueba que un nuevo usuario puede registrarse correctamente con datos aleatorios.
    """
    email = f"test_{random_string()}@example.com"
    password = random_string(12)

    response = client.post("/auth/register", json={
        "email": email,
        "password": password
    })
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["email"] == email
    assert "id" in data