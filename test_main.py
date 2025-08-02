import pytest
import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def deployed_contract():
    """Despliega el contrato una vez por sesión de prueba y establece la variable de entorno."""
    response = client.post("/deploy")
    assert response.status_code == 200
    data = response.json()
    contract_address = data["contract_address"]
    os.environ["CONTRACT_ADDRESS"] = contract_address
    return contract_address

def test_create_ticket(deployed_contract):
    owner_address = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    response = client.post(f"/tickets?owner_address={owner_address}")
    assert response.status_code == 200
    data = response.json()
    assert "transaction_hash" in data

def test_get_ticket_owner(deployed_contract):
    # Asumimos que el ticket con ID 1 fue creado en la prueba anterior
    response = client.get("/tickets/1")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == 1
    assert data["owner"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
