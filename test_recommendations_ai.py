"""
Tests para el Sistema de Recomendación IA
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app, InteractionType

client = TestClient(app)


def test_recommendations_without_auth():
    """Test que recomendaciones funciona sin autenticación (cold start)"""
    response = client.get("/events/recommendations?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Verificar estructura
    if len(data) > 0:
        event = data[0]
        assert "id" in event
        assert "name" in event
        assert "recommendation_score" in event
        assert "reasons" in event
        assert event["recommendation_score"] == 50.0  # Cold start score
        assert "Evento destacado" in event["reasons"]


def test_track_interaction_requires_auth():
    """Test que tracking requiere autenticación"""
    response = client.post(
        "/events/1/interactions",
        json={"interaction_type": "view"}
    )
    assert response.status_code == 401  # Unauthorized


def test_user_stats_requires_auth():
    """Test que estadísticas requieren autenticación"""
    response = client.get("/users/me/stats")
    assert response.status_code == 401  # Unauthorized


def test_recommendations_with_event_id():
    """Test que recomendaciones filtran por event_id"""
    response = client.get("/events/recommendations?event_id=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    
    # No debe incluir el evento 1
    if len(data) > 0:
        event_ids = [e["id"] for e in data]
        assert 1 not in event_ids


def test_interaction_type_validation():
    """Test que valida tipos de interacción"""
    # Primero hacer login (asume que hay un usuario de prueba)
    login_response = client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "password123"}
    )
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Intentar tipo inválido
        response = client.post(
            "/events/1/interactions",
            json={"interaction_type": "invalid"},
            headers=headers
        )
        assert response.status_code == 400
        assert "Invalid interaction_type" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
