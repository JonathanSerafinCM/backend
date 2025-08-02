import pytest
import os
from fastapi.testclient import TestClient
from main import app, UserRole, get_db, User, Event, get_w3
from test_auth import random_string
from sqlalchemy.orm import Session
from web3 import Web3

# Override the get_w3 dependency for testing
def get_w3_override():
    yield Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

app.dependency_overrides[get_w3] = get_w3_override

client = TestClient(app)

# --- Helpers ---
account_index = 0
def create_user_and_get_token(role: UserRole = UserRole.COMPRADOR, wallet_address: str | None = None):
    global account_index
    email = f"test_{random_string()}@example.com"
    password = random_string(12)
    
    w3 = next(get_w3_override())
    ganache_accounts = w3.eth.accounts

    if not wallet_address:
        wallet_address = ganache_accounts[account_index % len(ganache_accounts)]
        account_index += 1

    register_data = {"email": email, "password": password, "wallet_address": wallet_address}
    client.post("/auth/register", json=register_data)
    
    if role == UserRole.ORGANIZADOR:
        db: Session = next(get_db())
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = UserRole.ORGANIZADOR
            db.commit()
        db.close()
        
    login_response = client.post("/auth/login", data={"username": email, "password": password})
    token = login_response.json()["access_token"]
    return token, wallet_address

def create_event_for_purchase():
    token, _ = create_user_and_get_token(role=UserRole.ORGANIZADOR)
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

@pytest.fixture(autouse=True)
def clean_db():
    db = next(get_db())
    db.query(Event).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield

# --- Tests de Blockchain ---
@pytest.fixture(scope="module")
def contract_address():
    address = os.getenv("CONTRACT_ADDRESS")
    if not address:
        pytest.fail("La variable de entorno CONTRACT_ADDRESS no está definida.")
    return address

def test_purchase_ticket(contract_address):
    event_id = create_event_for_purchase()
    token, owner_address = create_user_and_get_token(role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(f"/events/{event_id}/purchase", headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert "transaction_hash" in data
    assert "ticket_id" in data
    # Guardar para el siguiente test
    os.environ["LAST_TICKET_ID"] = str(data["ticket_id"])
    os.environ["LAST_TICKET_OWNER_ADDRESS"] = owner_address

def test_get_ticket_owner(contract_address):
    ticket_id = os.getenv("LAST_TICKET_ID")
    owner_address = os.getenv("LAST_TICKET_OWNER_ADDRESS")
    assert ticket_id is not None, "No se pudo obtener el ticket_id del test anterior"
    assert owner_address is not None, "No se pudo obtener la owner_address del test anterior"

    response = client.get(f"/tickets/{ticket_id}/owner")
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket_id"] == int(ticket_id)
    assert data["owner"] == owner_address

def test_get_user_tickets(contract_address):
    token, wallet_address = create_user_and_get_token(role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {token}"}

    event_id = create_event_for_purchase()
    purchase_response = client.post(f"/events/{event_id}/purchase", headers=headers)
    assert purchase_response.status_code == 200
    ticket_id = purchase_response.json()["ticket_id"]

    response = client.get("/auth/users/me/tickets", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(ticket['ticket_id'] == ticket_id for ticket in data)
    assert all("owner" in ticket and "ticket_id" in ticket for ticket in data)

def test_get_ticket_history(contract_address):
    event_id = create_event_for_purchase()
    token, owner_address = create_user_and_get_token(role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {token}"}
    purchase_response = client.post(f"/events/{event_id}/purchase", headers=headers)
    assert purchase_response.status_code == 200
    ticket_id = purchase_response.json()["ticket_id"]

    response = client.get(f"/tickets/{ticket_id}/history")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket_id"] == ticket_id
    assert "history" in data
    history = data["history"]
    assert isinstance(history, list)
    assert len(history) > 0
    # El primer evento debe ser el minteo
    assert history[0]["from"] == "0x0000000000000000000000000000000000000000"
    assert history[0]["to"] == owner_address

def test_get_event_recommendations():
    response = client.get("/events/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0
    assert all("id" in event and "name" in event and "category" in event for event in data["events"])
