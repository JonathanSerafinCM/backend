import pytest
import os
from fastapi.testclient import TestClient
from main import app, UserRole, get_db, User, Event, Ticket, get_w3, SessionLocal, Base, engine, get_password_hash
from test_auth import random_string
from sqlalchemy.orm import Session
from web3 import Web3

def setup_database(db):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Create a default organizer user
    organizer_email = "organizer@test.com"
    organizer_password = "testpassword"
    hashed_password = get_password_hash(organizer_password)
    organizer_user = User(
        email=organizer_email,
        hashed_password=hashed_password,
        role=UserRole.ORGANIZADOR
    )
    db.add(organizer_user)
    db.commit()
    db.refresh(organizer_user)

def get_test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override the get_w3 dependency for testing
def get_w3_override():
    yield Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

app.dependency_overrides[get_w3] = get_w3_override

client = TestClient(app)

# --- Helpers ---
account_index = 0
def create_user_and_get_token(db: Session, role: UserRole = UserRole.COMPRADOR, wallet_address: str | None = None):
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
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = UserRole.ORGANIZADOR
            db.commit()
        
    login_response = client.post("/auth/login", data={"username": email, "password": password})
    token = login_response.json()["access_token"]
    return token, wallet_address

def create_event(db: Session, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    event_data = {
        "name": f"Evento de Prueba {random_string(5)}",
        "description": "Un evento para probar la compra de tickets NFT",
        "date": "2027-01-01T12:00:00",
        "location": "Lugar de Prueba",
        "price": 10.00,
        "total_tickets": 5
    }
    response = client.post("/events", json=event_data, headers=headers)
    assert response.status_code == 200, response.text
    event_id = response.json()["id"]
    return db.query(Event).filter(Event.id == event_id).first()

# --- Fixtures ---
@pytest.fixture(scope="function")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope='function', autouse=True)
def clean_db(db_session):
    setup_database(db_session)
    yield
    db_session.query(Ticket).delete()
    db_session.query(Event).delete()
    db_session.query(User).delete()
    db_session.commit()

# --- Tests de Blockchain ---

def test_purchase_ticket(db_session):
    # 1. Crear Organizador y Evento
    org_token, _ = create_user_and_get_token(db_session, role=UserRole.ORGANIZADOR)
    event = create_event(db_session, org_token)

    # 2. Crear Comprador
    buyer_token, _ = create_user_and_get_token(db_session, role=UserRole.COMPRADOR)
    headers = {"Authorization": f"Bearer {buyer_token}"}
    
    # 3. Comprar Ticket
    response = client.post(f"/events/{event.id}/purchase", headers=headers)
    
    # 4. Verificar
    assert response.status_code == 200, response.text
    data = response.json()
    assert "transaction_hash" in data
    assert "ticket_id" in data
    assert data["ticket_id"] is not None

def test_get_ticket_owner(db_session):
    # 1. Crear y comprar un ticket
    org_token, _ = create_user_and_get_token(db_session, role=UserRole.ORGANIZADOR)
    event = create_event(db_session, org_token)
    buyer_token, buyer_address = create_user_and_get_token(db_session, role=UserRole.COMPRADOR)
    purchase_res = client.post(f"/events/{event.id}/purchase", headers={"Authorization": f"Bearer {buyer_token}"})
    ticket_id = purchase_res.json()["ticket_id"]

    # 2. Obtener el dueño del ticket
    response = client.get(f"/tickets/{ticket_id}/owner")
    
    # 3. Verificar
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket_id"] == ticket_id
    assert data["owner"] == buyer_address

def test_get_user_tickets(db_session):
    # 1. Crear y comprar un ticket
    org_token, _ = create_user_and_get_token(db_session, role=UserRole.ORGANIZADOR)
    event = create_event(db_session, org_token)
    buyer_token, _ = create_user_and_get_token(db_session, role=UserRole.COMPRADOR)
    purchase_res = client.post(f"/events/{event.id}/purchase", headers={"Authorization": f"Bearer {buyer_token}"})
    ticket_id = purchase_res.json()["ticket_id"]

    # 2. Obtener los tickets del usuario
    response = client.get("/auth/users/me/tickets", headers={"Authorization": f"Bearer {buyer_token}"})

    # 3. Verificar
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(ticket['ticket_id'] == ticket_id for ticket in data)

def test_get_ticket_history(db_session):
    # 1. Crear y comprar un ticket
    org_token, _ = create_user_and_get_token(db_session, role=UserRole.ORGANIZADOR)
    event = create_event(db_session, org_token)
    buyer_token, buyer_address = create_user_and_get_token(db_session, role=UserRole.COMPRADOR)
    purchase_res = client.post(f"/events/{event.id}/purchase", headers={"Authorization": f"Bearer {buyer_token}"})
    ticket_id = purchase_res.json()["ticket_id"]

    # 2. Obtener el historial del ticket
    response = client.get(f"/tickets/{ticket_id}/history")

    # 3. Verificar
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket_id"] == ticket_id
    assert "history" in data
    history = data["history"]
    assert isinstance(history, list)
    assert len(history) > 0
    assert history[0]["from"] == "0x0000000000000000000000000000000000000000"
    assert history[0]["to"] == buyer_address

# --- Test de IA (Placeholder) ---
def test_get_event_recommendations():
    response = client.get("/events/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)