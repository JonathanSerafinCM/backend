from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app, Event, User, UserRole
from test_main import setup_database, get_test_db, create_user_and_get_token, create_event

client = TestClient(app)

def test_get_event_recommendations_by_category():
    db: Session = next(get_test_db())
    setup_database(db)

    # Create an organizer and some events with categories
    org_token, _ = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)

    event1_data = {"name": "Concierto de Rock", "description": "", "date": "2025-12-01T20:00:00", "location": "", "price": 10.0, "total_tickets": 100, "category": "Música"}
    event2_data = {"name": "Festival de Jazz", "description": "", "date": "2025-12-02T20:00:00", "location": "", "price": 15.0, "total_tickets": 100, "category": "Música"}
    event3_data = {"name": "Obra de Teatro", "description": "", "date": "2025-12-03T20:00:00", "location": "", "price": 20.0, "total_tickets": 100, "category": "Teatro"}

    event1 = client.post("/events", json=event1_data, headers={"Authorization": f"Bearer {org_token}"}).json()
    event2 = client.post("/events", json=event2_data, headers={"Authorization": f"Bearer {org_token}"}).json()
    event3 = client.post("/events", json=event3_data, headers={"Authorization": f"Bearer {org_token}"}).json()

    # Test recommendations for a specific event (Event1 - Música)
    response = client.get(f"/events/recommendations?event_id={event1['id']}")
    assert response.status_code == 200
    recommendations = response.json()["events"]
    assert len(recommendations) == 1  # Only event2 should be recommended
    assert recommendations[0]["id"] == event2["id"]

    # Test recommendations without a specific event_id (should return all events)
    response_all = client.get("/events/recommendations")
    assert response_all.status_code == 200
    recommendations_all = response_all.json()["events"]
    assert len(recommendations_all) == 3 # All events should be returned

    db.close()
