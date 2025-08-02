import pytest
import os
from fastapi.testclient import TestClient
from main import app, UserRole, get_db, User, get_w3
from test_auth import random_string
from sqlalchemy.orm import Session
from web3 import Web3

# Override the get_w3 dependency for testing
def get_w3_override():
    yield Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

app.dependency_overrides[get_w3] = get_w3_override

client = TestClient(app)

# --- Helpers ---
def create_user_and_get_token(role: UserRole = UserRole.COMPRADOR):
    email = f"test_{random_string()}@example.com"
    password = random_string(12)
    client.post("/auth/register", json={"email": email, "password": password})
    if role == UserRole.ORGANIZADOR:
        db: Session = next(get_db())
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = UserRole.ORGANIZADOR
            db.commit()
        db.close()
    login_response = client.post("/auth/login", data={"username": email, "password": password})
    return login_response.json()["access_token"]

def create_event_for_purchase():
    """Crea un evento para usar en las pruebas de compra."""
    token = create_user_and_get_token(role=UserRole.ORGANIZADOR)
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {
        "name": "Evento de Prueba para Comprar",
        "description": "Un evento para probar la compra de tickets NFT",
        "date": "2027-01-01T12:00:00",
        "location": "Lugar de Prueba",
        "price": 10.00,
        "total_tickets": 5
    }
    response = client.post("/events", json=event_data, headers=headers)
    return response.json()["id"]

# --- Tests de Blockchain ---
@pytest.fixture(scope="module")
def contract_address():
    """Obtiene la dirección del contrato desde las variables de entorno."""
    address = os.getenv("CONTRACT_ADDRESS")
    if not address:
        pytest.fail("La variable de entorno CONTRACT_ADDRESS no está definida. Por favor, despliega el contrato primero.")
    return address

def test_purchase_ticket(contract_address):
    """
    Prueba la compra de un ticket y el minteo de un NFT.
    """
    event_id = create_event_for_purchase()
    token = create_user_and_get_token(role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {token}"}
    
    # La dirección que recibirá el NFT (debe ser una de las cuentas de Ganache)
    owner_address = "0xAF791559189D2acF053c92Cf995BBeA1e4e694eF"
    purchase_data = {"owner_address": owner_address}
    
    response = client.post(f"/events/{event_id}/purchase", json=purchase_data, headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert "transaction_hash" in data
    assert "ticket_id" in data
    os.environ["LAST_TICKET_ID"] = str(data["ticket_id"])

def test_get_ticket_owner(contract_address):
    """
    Prueba que se puede obtener el dueño de un ticket NFT.
    """
    ticket_id = os.getenv("LAST_TICKET_ID")
    assert ticket_id is not None, "No se pudo obtener el ticket_id del test anterior"

    response = client.get(f"/tickets/{ticket_id}")
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket_id"] == int(ticket_id)
    assert data["owner"] == "0xAF791559189D2acF053c92Cf995BBeA1e4e694eF"