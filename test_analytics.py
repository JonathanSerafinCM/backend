from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app, Event, User, UserRole, Ticket, EventInteraction, InteractionType
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


def test_organizer_analytics_overview_with_data():
    db: Session = next(get_test_db())
    setup_database(db)

    organizer_token, organizer_wallet = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)
    organizer = db.query(User).filter(User.wallet_address == organizer_wallet).first()
    organizer_headers = {"Authorization": f"Bearer {organizer_token}"}

    event_date = (datetime.utcnow() + timedelta(days=10)).replace(microsecond=0)
    event_payload = {
        "name": "Concierto Test",
        "description": "Evento de prueba",
        "date": event_date.isoformat(),
        "location": "Madrid",
        "price": "30.0",
        "total_tickets": "100",
        "category": "Música",
    }

    response = client.post("/events", data=event_payload, headers=organizer_headers)
    assert response.status_code == 200, response.text
    event_id = response.json()["id"]
    event = db.query(Event).filter(Event.id == event_id).first()

    buyer1_token, buyer1_wallet = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer1 = db.query(User).filter(User.wallet_address == buyer1_wallet).first()
    buyer2_token, buyer2_wallet = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer2 = db.query(User).filter(User.wallet_address == buyer2_wallet).first()

    now = datetime.utcnow()
    interactions = [
        EventInteraction(user_id=buyer1.id, event_id=event_id, interaction_type=InteractionType.VIEW, created_at=now - timedelta(hours=3)),
        EventInteraction(user_id=buyer1.id, event_id=event_id, interaction_type=InteractionType.CLICK, created_at=now - timedelta(hours=2)),
        EventInteraction(user_id=buyer1.id, event_id=event_id, interaction_type=InteractionType.PURCHASE, created_at=now - timedelta(hours=1)),
        EventInteraction(user_id=buyer2.id, event_id=event_id, interaction_type=InteractionType.VIEW, created_at=now - timedelta(hours=5)),
    ]
    db.add_all(interactions)

    ticket = Ticket(
        ticket_id_onchain=int(now.timestamp()),
        event_id=event_id,
        owner_wallet_address=buyer1_wallet,
        purchase_date=now - timedelta(hours=1),
        is_paid=True
    )
    db.add(ticket)
    event.total_tickets -= 1
    db.commit()

    overview_response = client.get("/organizer/analytics/overview?days=30", headers=organizer_headers)
    assert overview_response.status_code == 200, overview_response.text
    data = overview_response.json()

    assert data["kpis"]["ctr_pct"] == 50.0
    assert data["kpis"]["rec_conversion_pct"] == 100.0
    assert data["kpis"]["coverage_pct"] == 50.0
    assert data["kpis"]["avg_interactions_per_user"] == 2.0

    today_str = now.date().isoformat()
    today_entry = next((row for row in data["timeseries"]["daily"] if row["date"] == today_str), None)
    assert today_entry is not None
    assert today_entry["views"] == 2
    assert today_entry["clicks"] == 1
    assert today_entry["purchases"] == 1

    assert data["tops"]["events_by_sales"]
    assert data["tops"]["events_by_sales"][0]["event_id"] == event_id
    assert data["inventory"]
    inventory_row = data["inventory"][0]
    assert inventory_row["event_id"] == event_id
    assert inventory_row["sold"] == 1
    assert inventory_row["available"] == 99

    db.close()


def test_organizer_analytics_overview_forbidden_for_buyer():
    db: Session = next(get_test_db())
    setup_database(db)

    buyer_token, _ = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    response = client.get("/organizer/analytics/overview", headers=buyer_headers)
    assert response.status_code == 403

    db.close()


def test_organizer_analytics_overview_event_not_owned_returns_403():
    db: Session = next(get_test_db())
    setup_database(db)

    organizer_a_token, organizer_a_wallet = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)
    organizer_a = db.query(User).filter(User.wallet_address == organizer_a_wallet).first()
    organizer_a_headers = {"Authorization": f"Bearer {organizer_a_token}"}

    organizer_b_token, organizer_b_wallet = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)
    organizer_b = db.query(User).filter(User.wallet_address == organizer_b_wallet).first()
    organizer_b_headers = {"Authorization": f"Bearer {organizer_b_token}"}

    future_date = (datetime.utcnow() + timedelta(days=15)).replace(microsecond=0).isoformat()
    payload = {
        "name": "Evento Org A",
        "description": "",
        "date": future_date,
        "location": "Valencia",
        "price": "20.0",
        "total_tickets": "50",
        "category": "Teatro",
    }
    event_a_response = client.post("/events", data=payload, headers=organizer_a_headers)
    assert event_a_response.status_code == 200

    payload_b = {
        "name": "Evento Org B",
        "description": "",
        "date": (datetime.utcnow() + timedelta(days=20)).replace(microsecond=0).isoformat(),
        "location": "Bilbao",
        "price": "25.0",
        "total_tickets": "80",
        "category": "Música",
    }
    event_b_response = client.post("/events", data=payload_b, headers=organizer_b_headers)
    assert event_b_response.status_code == 200
    event_b_id = event_b_response.json()["id"]

    forbidden_response = client.get(f"/organizer/analytics/overview?event_id={event_b_id}", headers=organizer_a_headers)
    assert forbidden_response.status_code == 403

    db.close()


def test_admin_analytics_overview_with_organizer_filter():
    db: Session = next(get_test_db())
    setup_database(db)

    organizer_token, organizer_wallet = create_user_and_get_token(db, role=UserRole.ORGANIZADOR)
    organizer = db.query(User).filter(User.wallet_address == organizer_wallet).first()
    organizer_headers = {"Authorization": f"Bearer {organizer_token}"}

    admin_token, admin_wallet = create_user_and_get_token(db, role=UserRole.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin = db.query(User).filter(User.wallet_address == admin_wallet).first()

    event_date = (datetime.utcnow() + timedelta(days=8)).replace(microsecond=0).isoformat()
    payload = {
        "name": "Evento Admin",
        "description": "",
        "date": event_date,
        "location": "Barcelona",
        "price": "40.0",
        "total_tickets": "70",
        "category": "Conferencia",
    }
    event_response = client.post("/events", data=payload, headers=organizer_headers)
    assert event_response.status_code == 200
    event_id = event_response.json()["id"]

    buyer_token, buyer_wallet = create_user_and_get_token(db, role=UserRole.COMPRADOR)
    buyer = db.query(User).filter(User.wallet_address == buyer_wallet).first()

    timestamp = datetime.utcnow()
    db.add_all([
        EventInteraction(user_id=buyer.id, event_id=event_id, interaction_type=InteractionType.VIEW, created_at=timestamp - timedelta(hours=6)),
        EventInteraction(user_id=buyer.id, event_id=event_id, interaction_type=InteractionType.CLICK, created_at=timestamp - timedelta(hours=5)),
        EventInteraction(user_id=buyer.id, event_id=event_id, interaction_type=InteractionType.PURCHASE, created_at=timestamp - timedelta(hours=4)),
    ])
    db.add(Ticket(
        ticket_id_onchain=int(timestamp.timestamp()),
        event_id=event_id,
        owner_wallet_address=buyer_wallet,
        purchase_date=timestamp - timedelta(hours=4),
        is_paid=True
    ))
    db.commit()

    response = client.get(f"/organizer/analytics/overview?days=30&organizer_id={organizer.id}", headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["filters"]["organizer_id"] == organizer.id
    assert data["tops"]["events_by_sales"]
    assert data["tops"]["events_by_sales"][0]["event_id"] == event_id

    db.close()
