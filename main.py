import os
import enum
import json
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import (Column, create_engine, DateTime, Enum, Float,
                        ForeignKey, Integer, String, func)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from web3 import Web3

# Cargar variables de entorno
load_dotenv(encoding='utf-8', override=True)

# --- Configuración de la Base de Datos (PostgreSQL) ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ticketera")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Enums ---
class UserRole(str, enum.Enum):
    COMPRADOR = "comprador"
    ORGANIZADOR = "organizador"

# --- Modelos de la Base de Datos (SQLAlchemy) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    wallet_address = Column(String, unique=True, index=True, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.COMPRADOR, nullable=False)
    events = relationship("Event", back_populates="owner")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    date = Column(DateTime, nullable=False)
    location = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    total_tickets = Column(Integer, nullable=False)
    category = Column(String, nullable=True) # Nueva columna para la categoría
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="events")
    tickets = relationship("Ticket", back_populates="event") # Relación con tickets

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id_onchain = Column(Integer, unique=True, index=True, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"))
    owner_wallet_address = Column(String, nullable=False)
    event = relationship("Event", back_populates="tickets")

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

# --- Schemas (Pydantic) ---
class UserCreate(BaseModel):
    email: str
    password: str
    wallet_address: str | None = None

class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole
    wallet_address: str | None = None
    class Config:
        from_attributes = True

class EventCreate(BaseModel):
    name: str
    description: str | None = None
    date: datetime
    location: str
    price: float
    total_tickets: int
    category: str | None = None

class EventOut(EventCreate):
    id: int
    category: str | None = None
    class Config:
        from_attributes = True

class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date: datetime | None = None
    location: str | None = None
    price: float | None = None
    total_tickets: int | None = None
    category: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

# --- Seguridad y Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "a_super_secret_key_that_should_be_in_env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependencias ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

# --- Aplicación Principal de FastAPI ---
app = FastAPI(
    title="Ticketera IA + Blockchain API",
    description="Backend para la gestión de eventos, tickets NFT y recomendaciones con IA.",
    version="0.1.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, deberías restringir esto a tu dominio de frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Users"]) # Router para usuarios
events_router = APIRouter(prefix="/events", tags=["Events"])
web3_router = APIRouter(prefix="/tickets", tags=["Blockchain"])
metadata_router = APIRouter(prefix="/metadata", tags=["Metadata"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

# --- Endpoints de Autenticación ---
@auth_router.post("/register", response_model=UserOut)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email, 
        hashed_password=hashed_password, 
        wallet_address=user.wallet_address, 
        role=UserRole.COMPRADOR
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@auth_router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.get("/users/me", response_model=UserOut)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@users_router.get("/me/tickets", tags=["Blockchain"], response_model=list[dict])
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.wallet_address:
        raise HTTPException(status_code=400, detail="User does not have a wallet address registered.")

    tickets_db = db.query(Ticket).filter(Ticket.owner_wallet_address == current_user.wallet_address).all()
    
    tickets_out = []
    for ticket in tickets_db:
        tickets_out.append({"ticket_id": ticket.ticket_id_onchain, "owner": ticket.owner_wallet_address})
            
    return tickets_out

# --- Endpoints de Eventos ---
@events_router.get("/recommendations", tags=["AI"], response_model=list[EventOut])
def get_event_recommendations(event_id: int | None = None, db: Session = Depends(get_db)):
    if event_id:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        recommendations = db.query(Event).filter(Event.category == event.category, Event.id != event_id).all()
    else:
        recommendations = db.query(Event).all()
    return recommendations

@events_router.post("", response_model=EventOut)
def create_event(event: EventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Only organizers can create events")
    new_event = Event(**event.model_dump(), owner=current_user)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@events_router.get("", response_model=list[EventOut])
def get_all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events

@events_router.get("/{event_id}", response_model=EventOut)
def get_event_by_id(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@events_router.put("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int, 
    event_update: EventUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.owner_id != current_user.id or current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Not authorized to update this event")

    update_data = event_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    
    db.commit()
    db.refresh(event)
    return event

@events_router.delete("/{event_id}")
def delete_event(
    event_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.owner_id != current_user.id or current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Not authorized to delete this event")

    db.delete(event)
    db.commit()
    return {"detail": "Event deleted successfully"}

@events_router.post("/{event_id}/purchase", tags=["Blockchain"])
def purchase_ticket(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    contract_address: str = Depends(lambda: get_contract_address()),
    w3: Web3 = Depends(lambda: get_w3())
):
    if current_user.role != UserRole.COMPRADOR:
        raise HTTPException(status_code=403, detail="Only buyers can purchase tickets")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.total_tickets <= 0:
        raise HTTPException(status_code=400, detail="No tickets left for this event")

    if not current_user.wallet_address:
        raise HTTPException(status_code=400, detail="User does not have a wallet address registered.")

    contract = w3.eth.contract(address=contract_address, abi=abi)
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)
    
    # Generar un ID de ticket único
    token_uri = f"https://api.ticketera.com/metadata/tickets/{event.id}"

    mint_function = contract.functions.safeMint(current_user.wallet_address, token_uri)
    
    tx_data = mint_function.build_transaction({
        'from': ACCOUNT_ADDRESS,
        'chainId': 80002,
        'gas': 500000,  # Usar un valor de gas fijo y suficientemente alto
        'gasPrice': w3.to_wei(30, 'gwei'),
        'nonce': nonce,
    })

    signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    event.total_tickets -= 1
    db.commit()

    transfer_events = contract.events.Transfer.process_receipt(tx_receipt)
    mint_event = next((e for e in transfer_events if e['args']['from'] == "0x0000000000000000000000000000000000000000"), None)

    if not mint_event:
        raise HTTPException(status_code=500, detail="Minting Transfer event not found in transaction receipt")

    ticket_id = mint_event['args']['tokenId']

    # Guardar el ticket en la base de datos
    new_ticket_db = Ticket(
        ticket_id_onchain=ticket_id,
        event_id=event.id,
        owner_wallet_address=current_user.wallet_address
    )
    db.add(new_ticket_db)
    db.commit()
    db.refresh(new_ticket_db)

    return {
        "message": "Ticket purchased and minted successfully", 
        "transaction_hash": tx_hash.hex(),
        "ticket_id": ticket_id
    }

# --- Blockchain (Web3) ---
def get_w3():
    # Usa la URL del RPC de la testnet desde las variables de entorno, con fallback al nodo local
    rpc_url = os.getenv("TESTNET_RPC_URL", "http://127.0.0.1:8545")
    return Web3(Web3.HTTPProvider(rpc_url))

with open("TicketManager.abi", "r") as f:
    abi = json.load(f)

def get_contract_address():
    contract_address = os.environ.get("CONTRACT_ADDRESS")
    if not contract_address:
        raise HTTPException(status_code=500, detail="La dirección del contrato no está configurada.")
    return contract_address

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise ValueError("No PRIVATE_KEY set for the application")
ACCOUNT_ADDRESS = Web3().eth.account.from_key(PRIVATE_KEY).address

@web3_router.get("/{ticket_id}/owner")
def get_ticket_owner(ticket_id: int, contract_address: str = Depends(get_contract_address), w3: Web3 = Depends(get_w3)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    try:
        owner = contract.functions.ownerOf(ticket_id).call()
        return {"ticket_id": ticket_id, "owner": owner}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ticket not found or error: {e}")

@web3_router.get("/{ticket_id}/history")
def get_ticket_history(ticket_id: int, contract_address: str = Depends(get_contract_address), w3: Web3 = Depends(get_w3)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    try:
        transfer_event_filter = contract.events.Transfer.create_filter(
            from_block='earliest',
            argument_filters={'tokenId': ticket_id}
        )
        logs = transfer_event_filter.get_all_entries()
        
        if not logs:
             raise HTTPException(status_code=404, detail="No history found for this ticket.")

        history = []
        for log in logs:
            event = log['args']
            history.append({
                "from": event["from"],
                "to": event["to"],
                "blockNumber": log["blockNumber"],
                "transactionHash": log["transactionHash"].hex()
            })
        return {"ticket_id": ticket_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving ticket history: {e}")


@metadata_router.get("/tickets/{ticket_id}", tags=["Metadata"])
def get_ticket_metadata(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id_onchain == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket metadata not found")

    event = db.query(Event).filter(Event.id == ticket.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found for this ticket")

    metadata = {
        "name": event.name,
        "description": event.description,
        "image": "https://example.com/ticket_image.png", # Placeholder image
        "attributes": [
            {"trait_type": "Event ID", "value": event.id},
            {"trait_type": "Location", "value": event.location},
            {"trait_type": "Date", "value": event.date.isoformat()},
            {"trait_type": "Price", "value": event.price},
            {"trait_type": "Category", "value": event.category},
            {"trait_type": "Owner Wallet", "value": ticket.owner_wallet_address},
        ],
    }
    return metadata

@admin_router.get("/analytics/sales-by-category")
def get_sales_by_category(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Not authorized to access analytics")

    sales_data = db.query(
        Event.category,
        func.count(Ticket.id).label("tickets_sold")
    ).join(Ticket, Event.id == Ticket.event_id).group_by(Event.category).all()

    return [{"category": category, "tickets_sold": tickets_sold} for category, tickets_sold in sales_data]

# --- Endpoint temporal para pruebas (NO USAR EN PRODUCCIÓN) ---
@admin_router.post("/promote-to-organizer/{user_email}")
def promote_to_organizer_temp(
    user_email: str,
    db: Session = Depends(get_db),
    # No requerimos autenticación para este endpoint temporal
):
    # Buscar el usuario por email
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Promover a organizador
    user.role = UserRole.ORGANIZADOR
    db.commit()
    db.refresh(user)
    
    return {"message": f"User {user_email} promoted to organizer successfully", "user": user.email, "new_role": user.role}

# Incluir routers en la app
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(events_router)
app.include_router(web3_router)
app.include_router(metadata_router)
app.include_router(admin_router)

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la Ticketera API"}
