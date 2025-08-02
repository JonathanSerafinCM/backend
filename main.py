import os
import enum
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy import create_engine, Column, Integer, String, Enum, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from passlib.context import CryptContext
from web3 import Web3
import json
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import relationship, declarative_base

# Cargar variables de entorno
load_dotenv(encoding='utf-8')

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
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="events")

    def __init__(self, name, description, date, location, price, total_tickets, owner):
        self.name = name
        self.description = description
        self.date = date
        self.location = location
        self.price = price
        self.total_tickets = total_tickets
        self.owner = owner

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

# --- Schemas (Pydantic) ---
class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole
    class Config:
        orm_mode = True

class EventCreate(BaseModel):
    name: str
    description: str | None = None
    date: datetime
    location: str
    price: float
    total_tickets: int

class EventOut(EventCreate):
    id: int
    class Config:
        orm_mode = True

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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
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

# --- Routers ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
events_router = APIRouter(prefix="/events", tags=["Events"])
web3_router = APIRouter(tags=["Web3"])

# --- Endpoints de Autenticación ---
@auth_router.post("/register", response_model=UserOut)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password, role=UserRole.COMPRADOR)
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

# --- Endpoints de Eventos ---
@events_router.post("", response_model=EventOut)
def create_event(event: EventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Only organizers can create events")
    new_event = Event(
        name=event.name,
        description=event.description,
        date=event.date,
        location=event.location,
        price=event.price,
        total_tickets=event.total_tickets,
        owner=current_user
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@events_router.get("", response_model=list[EventOut])
def get_all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events


# --- Blockchain (Web3) Endpoints ---
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")
if not ALCHEMY_API_KEY:
    raise ValueError("No se ha configurado la ALCHEMY_API_KEY en las variables de entorno.")

w3 = Web3(Web3.HTTPProvider(f"https://polygon-amoy.g.alchemy.com/v2/{ALCHEMY_API_KEY}"))

with open("TicketManager.abi", "r") as f:
    abi = json.load(f)

with open("TicketManager.bin", "r") as f:
    bytecode = f.read()

def get_contract_address():
    contract_address = os.environ.get("CONTRACT_ADDRESS")
    if not contract_address:
        raise HTTPException(status_code=500, detail="La dirección del contrato no está configurada.")
    return contract_address

PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
ACCOUNT_ADDRESS = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

@web3_router.post("/deploy")
def deploy_contract():
    if not PRIVATE_KEY:
        raise HTTPException(status_code=500, detail="La clave privada no está configurada.")

    TicketManagerContract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)
    constructor = TicketManagerContract.constructor()
    gas_estimate = constructor.estimate_gas({'from': ACCOUNT_ADDRESS, 'nonce': nonce})
    transaction = constructor.build_transaction({
        'chainId': 80002,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"message": "Contrato desplegado", "contract_address": tx_receipt.contractAddress}

@web3_router.post("/tickets")
def create_ticket_endpoint(owner_address: str, contract_address: str = Depends(get_contract_address)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)
    create_ticket_function = contract.functions.createTicket(owner_address)
    gas_estimate = create_ticket_function.estimate_gas({'from': ACCOUNT_ADDRESS, 'nonce': nonce})
    tx_data = create_ticket_function.build_transaction({
        'chainId': 80002,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"message": "Ticket creado exitosamente", "transaction_hash": tx_hash.hex()}

@web3_router.get("/tickets/{ticket_id}")
def get_ticket_owner(ticket_id: int, contract_address: str = Depends(get_contract_address)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    owner = contract.functions.ticketOwners(ticket_id).call()
    return {"ticket_id": ticket_id, "owner": owner}

@web3_router.get("/events/recommendations")
def get_event_recommendations():
    return {
        "events": [
            {"id": 1, "name": "Concierto de Rock", "category": "Música"},
            {"id": 2, "name": "Obra de Teatro", "category": "Teatro"},
            {"id": 3, "name": "Festival de Jazz", "category": "Música"},
        ]
    }

# Incluir routers en la app
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(web3_router)

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la Ticketera API"}