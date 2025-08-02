import pytest
from fastapi.testclient import TestClient
from main import app, UserRole, User, get_db
from test_auth import random_string # Reutilizamos la función para datos aleatorios
from sqlalchemy.orm import Session

client = TestClient(app)

# --- Helper para crear usuarios y obtener tokens ---
def create_user_and_get_token(role: UserRole = UserRole.COMPRADOR):
    email = f"test_{random_string()}@example.com"
    password = random_string(12)
    
    # Registra el usuario
    client.post("/auth/register", json={"email": email, "password": password})
    
    # Actualiza el rol a Organizador si es necesario
    if role == UserRole.ORGANIZADOR:
        db: Session = next(get_db())
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = UserRole.ORGANIZADOR
            db.commit()
        db.close()

    # Inicia sesión para obtener el token
    login_response = client.post("/auth/login", data={"username": email, "password": password})
    token = login_response.json()["access_token"]
    return token

# --- Pruebas de Eventos ---
def test_create_event_as_organizador():
    """
    Prueba que un Organizador puede crear un evento.
    """
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    
    event_data = {
        "name": "Concierto de Prueba",
        "description": "Un evento increible",
        "date": "2025-12-25T20:00:00",
        "location": "Estadio Nacional",
        "price": 50.00,
        "total_tickets": 100
    }
    
    response = client.post("/events", json=event_data, headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == event_data["name"]
    assert "id" in data

def test_create_event_as_comprador():
    """
    Prueba que un Comprador NO puede crear un evento.
    """
    token = create_user_and_get_token(role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {token}"}
    
    event_data = {
        "name": "Intento de Evento",
        "description": "Esto no deberia funcionar",
        "date": "2025-12-25T20:00:00",
        "location": "Mi Casa",
        "price": 10.00,
        "total_tickets": 10
    }
    
    response = client.post("/events", json=event_data, headers=headers)
    
    assert response.status_code == 403 # Forbidden

def test_get_all_events():
    """
    Prueba que se pueden obtener todos los eventos.
    """
    initial_response = client.get("/events")
    assert initial_response.status_code == 200
    initial_events_count = len(initial_response.json())

    # Crear un evento como organizador
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {
        "name": "Evento para listar",
        "description": "Un evento para probar la lista",
        "date": "2025-11-15T10:00:00",
        "location": "Centro de Convenciones",
        "price": 25.00,
        "total_tickets": 50
    }
    client.post("/events", json=event_data, headers=headers)

    # Obtener todos los eventos de nuevo
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == initial_events_count + 1
    # Verificar que el evento creado está en la lista
    found_event = False
    for event in response.json():
        if event["name"] == event_data["name"]:
            found_event = True
            break
    assert found_event, f"Event with name {event_data["name"]} not found in the list."

def test_get_event_by_id():
    """
    Prueba que se puede obtener un evento por su ID.
    """
    # Crear un evento para obtener
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {
        "name": "Evento Específico",
        "description": "Un evento para buscar por ID",
        "date": "2026-01-01T12:00:00",
        "location": "Teatro Principal",
        "price": 75.00,
        "total_tickets": 200
    }
    create_response = client.post("/events", json=event_data, headers=headers)
    assert create_response.status_code == 200
    event_id = create_response.json()["id"]

    # Obtener el evento por ID
    response = client.get(f"/events/{event_id}")
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == event_id
    assert data["name"] == event_data["name"]

def test_get_event_by_id_not_found():
    """
    Prueba que se devuelve un 404 si el evento no existe.
    """
    response = client.get("/events/999999") # Un ID que probablemente no exista
    assert response.status_code == 404

def test_update_event_as_organizador():
    """
    Prueba que un Organizador puede actualizar su propio evento.
    """
    # Crear un evento
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {
        "name": "Evento Original",
        "description": "Descripción original",
        "date": "2026-02-10T19:00:00",
        "location": "Lugar Original",
        "price": 100.00,
        "total_tickets": 500
    }
    create_response = client.post("/events", json=event_data, headers=headers)
    event_id = create_response.json()["id"]

    # Actualizar el evento
    updated_data = {"name": "Evento Actualizado"}
    response = client.put(f"/events/{event_id}", json=updated_data, headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Evento Actualizado"
    assert data["description"] == "Descripción original" # No debería cambiar

def test_update_event_as_comprador():
    """
    Prueba que un Comprador NO puede actualizar un evento.
    """
    # Crear un evento con un organizador
    organizador_token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    event_data = {"name": "Evento Secreto", "date": "2026-03-01T12:00:00", "location": "Club", "price": 10.0, "total_tickets": 10}
    create_response = client.post("/events", json=event_data, headers={"Authorization": f"Bearer {organizador_token}"})
    event_id = create_response.json()["id"]

    # Intentar actualizar con un comprador
    comprador_token = create_user_and_get_token(role=UserRole.COMPRADOR)
    updated_data = {"name": "Intento de Hackeo"}
    response = client.put(f"/events/{event_id}", json=updated_data, headers={"Authorization": f"Bearer {comprador_token}"})
    
    assert response.status_code == 403

def test_delete_event_as_organizador():
    """
    Prueba que un Organizador puede eliminar su propio evento.
    """
    # Crear un evento
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {"name": "Evento a Eliminar", "date": "2026-04-01T12:00:00", "location": "Lugar", "price": 10.0, "total_tickets": 10}
    create_response = client.post("/events", json=event_data, headers=headers)
    event_id = create_response.json()["id"]

    # Eliminar el evento
    response = client.delete(f"/events/{event_id}", headers=headers)
    
    assert response.status_code == 200, response.text
    assert response.json()["detail"] == "Event deleted successfully"

    # Verificar que el evento ya no existe
    get_response = client.get(f"/events/{event_id}")
    assert get_response.status_code == 404

def test_delete_event_as_comprador():
    """
    Prueba que un Comprador NO puede eliminar un evento.
    """
    # Crear un evento con un organizador
    organizador_token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    event_data = {"name": "Evento Protegido", "date": "2026-05-01T12:00:00", "location": "Club", "price": 10.0, "total_tickets": 10}
    create_response = client.post("/events", json=event_data, headers={"Authorization": f"Bearer {organizador_token}"})
    event_id = create_response.json()["id"]

    # Intentar eliminar con un comprador
    comprador_token = create_user_and_get_token(role=UserRole.COMPRADOR)
    response = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {comprador_token}"})
    
    assert response.status_code == 403