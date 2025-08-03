from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app, Event, Ticket, User, UserRole
from test_main import setup_database, get_test_db

client = TestClient(app)

def test_get_ticket_metadata():
    db: Session = next(get_test_db())
    setup_database(db)

    # Crear un evento de prueba
    organizer = db.query(User).filter(User.email == "organizer@test.com").first()
    test_event = Event(
        name="Evento para Metadata",
        description="Descripción del evento de metadata",
        date="2025-12-25T20:00:00Z",
        location="Lugar de Prueba",
        price=100.0,
        total_tickets=50,
        owner_id=organizer.id,
        category="Test"
    )
    db.add(test_event)
    db.commit()
    db.refresh(test_event)

    # Crear un ticket asociado al evento
    test_ticket = Ticket(
        ticket_id_onchain=999,
        event_id=test_event.id,
        owner_wallet_address="0x123456789"
    )
    db.add(test_ticket)
    db.commit()

    # Probar el endpoint de metadata
    response = client.get(f"/metadata/tickets/{test_ticket.ticket_id_onchain}")
    
    assert response.status_code == 200
    
    metadata = response.json()
    assert metadata["name"] == test_event.name
    assert metadata["description"] == test_event.description
    assert "image" in metadata
    assert isinstance(metadata["attributes"], list)
    
    # Verificar que los atributos contienen la información correcta
    attributes = {attr["trait_type"]: attr["value"] for attr in metadata["attributes"]}
    assert attributes["Location"] == test_event.location
    assert attributes["Date"] == test_event.date.isoformat()

    # Probar con un ticket que no existe
    response_404 = client.get("/metadata/tickets/111111")
    assert response_404.status_code == 404
    assert response_404.json()["detail"] == "Ticket metadata not found"

    db.close()
