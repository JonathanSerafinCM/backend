from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app, Event, User, UserRole, Ticket
from test_main import setup_database, get_test_db, create_user_and_get_token, create_event

client = TestClient(app)

def test_get_sales_by_category_as_organizer():
    db: Session = next(get_test_db())
    setup_database(db)

    # Create an organizer user
    organizer_token, _ = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)
    organizer_headers = {"Authorization": f"Bearer {organizer_token}"}

    # Create events with different categories
    event_music_data = {"name": "Concierto", "description": "", "date": "2025-12-01T20:00:00", "location": "", "price": 10.0, "total_tickets": 10, "category": "Música"}
    event_theater_data = {"name": "Obra", "description": "", "date": "2025-12-02T20:00:00", "location": "", "price": 20.0, "total_tickets": 5, "category": "Teatro"}
    event_sports_data = {"name": "Partido", "description": "", "date": "2025-12-03T20:00:00", "location": "", "price": 30.0, "total_tickets": 8, "category": "Deportes"}

    event_music = client.post("/events", json=event_music_data, headers=organizer_headers).json()
    event_theater = client.post("/events", json=event_theater_data, headers=organizer_headers).json()
    event_sports = client.post("/events", json=event_sports_data, headers=organizer_headers).json()

    # Create a buyer and purchase tickets
    buyer_token, buyer_wallet = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    # Purchase 2 music tickets
    client.post(f"/events/{event_music['id']}/purchase", headers=buyer_headers)
    client.post(f"/events/{event_music['id']}/purchase", headers=buyer_headers)

    # Purchase 1 theater ticket
    client.post(f"/events/{event_theater['id']}/purchase", headers=buyer_headers)

    # Purchase 3 sports tickets
    client.post(f"/events/{event_sports['id']}/purchase", headers=buyer_headers)
    client.post(f"/events/{event_sports['id']}/purchase", headers=buyer_headers)
    client.post(f"/events/{event_sports['id']}/purchase", headers=buyer_headers)

    # Get sales analytics as organizer
    response = client.get("/admin/analytics/sales-by-category", headers=organizer_headers)
    assert response.status_code == 200
    analytics_data = response.json()

    expected_analytics = [
        {"category": "Música", "tickets_sold": 2},
        {"category": "Teatro", "tickets_sold": 1},
        {"category": "Deportes", "tickets_sold": 3},
    ]

    # Sort both lists for consistent comparison
    analytics_data.sort(key=lambda x: x['category'])
    expected_analytics.sort(key=lambda x: x['category'])

    assert analytics_data == expected_analytics

    db.close()

def test_get_sales_by_category_as_buyer_forbidden():
    db: Session = next(get_test_db())
    setup_database(db)

    # Create a buyer user
    buyer_token, _ = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    # Attempt to get sales analytics as a buyer
    response = client.get("/admin/analytics/sales-by-category", headers=buyer_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access analytics"

    db.close()
