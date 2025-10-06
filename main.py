import os
import enum
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException, APIRouter, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import (Column, create_engine, DateTime, Enum, Float,
                        ForeignKey, Integer, String, func, Boolean)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from web3 import Web3

# Cargar variables de entorno
load_dotenv(encoding='utf-8', override=True)

# --- Configuración de la Base de Datos (PostgreSQL) ---
DATABASE_URL = os.getenv("DATABASE_URL") # Render inyectará esta variable

# Asegúrate de que DATABASE_URL no sea None en producción
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")


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
    image_url = Column(String, nullable=True)
    total_revenue = Column(Float, default=0.0) # To track revenue
    is_funds_withdrawn = Column(Boolean, default=False) # To simulate fund withdrawal
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="events")
    tickets = relationship("Ticket", back_populates="event") # Relación con tickets
    @property
    def contract_address(self):
        return os.getenv("CONTRACT_ADDRESS")

from datetime import datetime # Make sure this is at the top

# ... existing code ...

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id_onchain = Column(Integer, unique=True, index=True, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"))
    owner_wallet_address = Column(String, nullable=False)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    is_paid = Column(Boolean, default=False) # To simulate payment status
    event = relationship("Event", back_populates="tickets")


class InteractionType(str, enum.Enum):
    VIEW = "view"
    CLICK = "click"
    PURCHASE = "purchase"


class EventInteraction(Base):
    """
    Tabla para tracking de interacciones usuario-evento
    Usado por el sistema de recomendaciones IA
    """
    __tablename__ = "event_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relaciones
    user = relationship("User")
    event = relationship("Event")


# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

# Directory for storing event images
STATIC_UPLOAD_DIR = Path('static/event_images')
STATIC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --- Schemas (Pydantic) ---
class UserCreate(BaseModel):
    email: str
    password: str
    wallet_address: str | None = None
    role: UserRole | None = None

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
    image_url: str | None = None

class EventOut(EventCreate):
    id: int
    category: str | None = None
    image_url: str | None = None
    contract_address: str | None = None
    total_revenue: float | None = None
    is_funds_withdrawn: bool | None = None
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
    image_url: str | None = None
    contract_address: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

class InteractionCreate(BaseModel):
    interaction_type: str

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

@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health():
    return {"status": "ok"}

# --- CORS Middleware ---
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
if not allowed_origins:
    # fallback seguro en prod: front público
    allowed_origins = ["https://coffetimeevents.areadev.es"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

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
        role=user.role or UserRole.COMPRADOR
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

# --- Login con Web3 Wallet ---
class Web3LoginRequest(BaseModel):
    wallet_address: str
    signature: str
    message: str

@auth_router.post("/login/web3", response_model=Token)
def login_with_web3(login_data: Web3LoginRequest, db: Session = Depends(get_db)):
    """
    Autenticación usando firma de wallet Web3.
    El usuario debe firmar un mensaje con su wallet privada.
    """
    from eth_account.messages import encode_defunct
    from eth_account import Account
    
    try:
        # Verificar la firma
        message = encode_defunct(text=login_data.message)
        recovered_address = Account.recover_message(message, signature=login_data.signature)
        
        # Comparar direcciones (case-insensitive)
        if recovered_address.lower() != login_data.wallet_address.lower():
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Buscar o crear usuario con esta wallet
        user = db.query(User).filter(User.wallet_address == login_data.wallet_address.lower()).first()
        
        if not user:
            # Crear nuevo usuario con wallet
            # Email temporal basado en wallet
            temp_email = f"{login_data.wallet_address.lower()}@wallet.local"
            
            # Verificar si el email ya existe (no debería)
            existing_user = db.query(User).filter(User.email == temp_email).first()
            if existing_user:
                user = existing_user
            else:
                # Crear usuario nuevo
                user = User(
                    email=temp_email,
                    hashed_password=get_password_hash(str(uuid.uuid4())),  # Password random
                    wallet_address=login_data.wallet_address.lower(),
                    role=UserRole.COMPRADOR  # Por defecto comprador
                )
                db.add(user)
                db.commit()
                db.refresh(user)
        
        # Generar token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except Exception as e:
        print(f"Error in Web3 login: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

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


@users_router.get("/me/stats", tags=["AI"])
def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna estadísticas del comportamiento del usuario
    """
    total_views = db.query(EventInteraction).filter(
        EventInteraction.user_id == current_user.id,
        EventInteraction.interaction_type == InteractionType.VIEW
    ).count()
    
    total_clicks = db.query(EventInteraction).filter(
        EventInteraction.user_id == current_user.id,
        EventInteraction.interaction_type == InteractionType.CLICK
    ).count()
    
    total_purchases = db.query(EventInteraction).filter(
        EventInteraction.user_id == current_user.id,
        EventInteraction.interaction_type == InteractionType.PURCHASE
    ).count()
    
    # Categorías más compradas
    purchases = db.query(EventInteraction).filter(
        EventInteraction.user_id == current_user.id,
        EventInteraction.interaction_type == InteractionType.PURCHASE
    ).join(Event).all()
    
    category_counts = {}
    for interaction in purchases:
        cat = interaction.event.category or "Sin categoría"
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Precio promedio
    avg_price = 0
    if purchases:
        prices = [i.event.price for i in purchases]
        avg_price = sum(prices) / len(prices)
    
    return {
        "total_views": total_views,
        "total_clicks": total_clicks,
        "total_purchases": total_purchases,
        "favorite_categories": category_counts,
        "avg_ticket_price": round(avg_price, 2),
        "engagement_score": min(100, (total_clicks * 2 + total_purchases * 10))
    }


# --- Sistema de Recomendaciones IA ---

def calculate_recommendation_score(user_id: int, event: Event, db: Session) -> dict:
    """
    Calcula score personalizado (0-100) para un evento dado un usuario
    Retorna: {"score": float, "reasons": list[str]}
    """
    score = 0.0
    reasons = []
    
    # --- 1. PREFERENCIA DE CATEGORÍA (35%) ---
    user_purchases = db.query(EventInteraction).filter(
        EventInteraction.user_id == user_id,
        EventInteraction.interaction_type == InteractionType.PURCHASE
    ).join(Event).all()
    
    if user_purchases:
        category_counts = {}
        for interaction in user_purchases:
            cat = interaction.event.category or "Sin categoría"
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        total_purchases = len(user_purchases)
        event_category = event.category or "Sin categoría"
        
        if event_category in category_counts:
            category_pref = category_counts[event_category] / total_purchases
            score += 35 * category_pref
            
            if category_pref > 0.3:
                reasons.append(f"Te gusta {event_category}")
    
    # --- 2. SIMILITUD DE CONTENIDO (25%) ---
    if user_purchases:
        user_clicks = db.query(EventInteraction).filter(
            EventInteraction.user_id == user_id,
            EventInteraction.interaction_type.in_([InteractionType.CLICK, InteractionType.PURCHASE])
        ).join(Event).all()
        
        user_profile = {
            "categories": set(),
            "price_range": []
        }
        
        for interaction in user_clicks:
            if interaction.event.category:
                user_profile["categories"].add(interaction.event.category)
            user_profile["price_range"].append(interaction.event.price)
        
        content_sim = 0.0
        
        if event.category in user_profile["categories"]:
            content_sim += 0.7
            reasons.append("Similar a eventos que te interesan")
        
        if user_profile["price_range"]:
            avg_price = sum(user_profile["price_range"]) / len(user_profile["price_range"])
            price_diff = abs(event.price - avg_price) / avg_price if avg_price > 0 else 0
            
            if price_diff < 0.3:
                content_sim += 0.3
        
        score += 25 * content_sim
    
    # --- 3. POPULARIDAD (20%) ---
    recent_date = datetime.utcnow() - timedelta(days=7)
    
    event_views = db.query(EventInteraction).filter(
        EventInteraction.event_id == event.id,
        EventInteraction.interaction_type == InteractionType.VIEW,
        EventInteraction.created_at >= recent_date
    ).count()
    
    event_purchases = db.query(EventInteraction).filter(
        EventInteraction.event_id == event.id,
        EventInteraction.interaction_type == InteractionType.PURCHASE,
        EventInteraction.created_at >= recent_date
    ).count()
    
    max_expected_views = 100
    max_expected_purchases = 20
    
    popularity = (
        (min(event_views, max_expected_views) / max_expected_views) * 0.6 +
        (min(event_purchases, max_expected_purchases) / max_expected_purchases) * 0.4
    )
    
    score += 20 * popularity
    
    if event_purchases > 5:
        reasons.append("Popular esta semana")
    
    # --- 4. RECENCIA (10%) ---
    days_until_event = (event.date - datetime.utcnow()).days
    
    recency = 0.0
    
    if 7 <= days_until_event <= 30:
        recency = 1.0
        reasons.append("Próximamente")
    elif 0 <= days_until_event < 7:
        recency = 0.7
        reasons.append("¡Muy pronto!")
    elif 30 < days_until_event <= 60:
        recency = 0.5
    
    score += 10 * recency
    
    # --- 5. COMPATIBILIDAD DE PRECIO (5%) ---
    if user_purchases:
        prices = [i.event.price for i in user_purchases]
        avg_price = sum(prices) / len(prices)
        std_price = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5
        
        if std_price > 0:
            z_score = abs(event.price - avg_price) / std_price
            
            if z_score < 1:
                score += 5
                reasons.append("Precio acorde a tu histórico")
            elif z_score < 2:
                score += 2.5
    
    # --- 6. UBICACIÓN (5%) ---
    if user_purchases:
        location_counts = {}
        for interaction in user_purchases:
            loc = interaction.event.location
            location_counts[loc] = location_counts.get(loc, 0) + 1
        
        if location_counts:
            most_common_location = max(location_counts, key=location_counts.get)
            
            if event.location == most_common_location:
                score += 5
                reasons.append(f"En {event.location}")
    
    return {
        "score": round(score, 2),
        "reasons": reasons if reasons else ["Evento destacado"]
    }


def get_recommendations_for_user(user_id: int, event_id: int | None, limit: int, db: Session) -> list[dict]:
    """
    Obtiene recomendaciones personalizadas para un usuario
    """
    # Obtener eventos candidatos
    if event_id:
        base_event = db.query(Event).filter(Event.id == event_id).first()
        if not base_event:
            candidates = db.query(Event).filter(Event.date > datetime.utcnow()).all()
        else:
            candidates = db.query(Event).filter(
                Event.category == base_event.category,
                Event.id != event_id,
                Event.date > datetime.utcnow()
            ).all()
            
            if len(candidates) < limit * 2:
                other_candidates = db.query(Event).filter(
                    Event.id != event_id,
                    Event.date > datetime.utcnow()
                ).limit(limit * 2).all()
                candidates.extend(other_candidates)
    else:
        candidates = db.query(Event).filter(Event.date > datetime.utcnow()).all()
    
    # Eliminar duplicados
    candidates = list({e.id: e for e in candidates}.values())
    
    # Calcular score para cada candidato
    scored_events = []
    for event in candidates:
        result = calculate_recommendation_score(user_id, event, db)
        scored_events.append({
            "event": event,
            "score": result["score"],
            "reasons": result["reasons"]
        })
    
    # Ordenar por score
    scored_events.sort(key=lambda x: x["score"], reverse=True)
    
    return scored_events[:limit]


def get_cold_start_recommendations(event_id: int | None, limit: int, db: Session) -> list[Event]:
    """
    Para usuarios nuevos sin historial: eventos populares + próximos
    """
    recent_date = datetime.utcnow() - timedelta(days=7)
    
    if event_id:
        base_event = db.query(Event).filter(Event.id == event_id).first()
        if base_event:
            return db.query(Event).filter(
                Event.category == base_event.category,
                Event.id != event_id,
                Event.date > datetime.utcnow()
            ).order_by(Event.date).limit(limit).all()
    
    # Eventos populares (más ventas recientes)
    from sqlalchemy import desc
    popular_event_ids = db.query(
        EventInteraction.event_id,
        func.count(EventInteraction.id).label('count')
    ).filter(
        EventInteraction.interaction_type == InteractionType.PURCHASE,
        EventInteraction.created_at >= recent_date
    ).group_by(EventInteraction.event_id).order_by(desc('count')).limit(limit).all()
    
    if popular_event_ids:
        event_ids = [e.event_id for e in popular_event_ids]
        return db.query(Event).filter(
            Event.id.in_(event_ids),
            Event.date > datetime.utcnow()
        ).all()
    
    # Fallback: eventos próximos
    return db.query(Event).filter(Event.date > datetime.utcnow()).order_by(Event.date).limit(limit).all()


def get_current_user_optional(
    authorization: str | None = Depends(lambda: None),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Dependency que retorna el usuario si está autenticado, sino None
    """
    from fastapi import Header
    
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            return None
        
        user = db.query(User).filter(User.email == email).first()
        return user
    except:
        return None


# --- Endpoints de Eventos ---
@events_router.get("/recommendations", tags=["AI"])
def get_event_recommendations(
    event_id: int | None = None,
    limit: int = 10,
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    Endpoint de recomendaciones mejorado con IA
    
    - Si hay usuario autenticado → recomendaciones personalizadas
    - Si no hay usuario → eventos populares (cold start)
    - Si hay event_id → eventos similares a ese evento
    
    Retorna eventos con score y reasons
    """
    # Intentar obtener usuario autenticado
    current_user = None
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = db.query(User).filter(User.email == email).first()
        except:
            pass
    
    # Usuario autenticado → personalizado
    if current_user:
        has_history = db.query(EventInteraction).filter(
            EventInteraction.user_id == current_user.id
        ).first() is not None
        
        if has_history:
            recommendations = get_recommendations_for_user(current_user.id, event_id, limit, db)
            return [
                {
                    "id": rec["event"].id,
                    "name": rec["event"].name,
                    "description": rec["event"].description,
                    "date": rec["event"].date.isoformat(),
                    "location": rec["event"].location,
                    "price": rec["event"].price,
                    "total_tickets": rec["event"].total_tickets,
                    "category": rec["event"].category,
                    "image_url": rec["event"].image_url,
                    "owner_id": rec["event"].owner_id,
                    "recommendation_score": rec["score"],
                    "reasons": rec["reasons"]
                }
                for rec in recommendations
            ]
    
    # Usuario sin historial o no autenticado → cold start
    cold_start_events = get_cold_start_recommendations(event_id, limit, db)
    
    return [
        {
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "date": event.date.isoformat(),
            "location": event.location,
            "price": event.price,
            "total_tickets": event.total_tickets,
            "category": event.category,
            "image_url": event.image_url,
            "owner_id": event.owner_id,
            "recommendation_score": 50.0,
            "reasons": ["Evento destacado"]
        }
        for event in cold_start_events
    ]


@events_router.post("/{event_id}/interactions", tags=["AI"])
def track_event_interaction(
    event_id: int,
    interaction_data: InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra interacción del usuario con un evento
    
    Tipos: "view", "click", "purchase"
    """
    interaction_type = interaction_data.interaction_type
    
    # Validar tipo
    valid_types = ["view", "click", "purchase"]
    if interaction_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interaction_type. Must be one of: {valid_types}"
        )
    
    # Validar que el evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Evitar duplicados muy cercanos (debounce de 30 segundos para views)
    if interaction_type == "view":
        recent_interaction = db.query(EventInteraction).filter(
            EventInteraction.user_id == current_user.id,
            EventInteraction.event_id == event_id,
            EventInteraction.interaction_type == InteractionType.VIEW,
            EventInteraction.created_at >= datetime.utcnow() - timedelta(seconds=30)
        ).first()
        
        if recent_interaction:
            return {"status": "already_tracked", "message": "Recent view already tracked"}
    
    # Crear interacción
    interaction = EventInteraction(
        user_id=current_user.id,
        event_id=event_id,
        interaction_type=InteractionType(interaction_type),
        created_at=datetime.utcnow()
    )
    
    db.add(interaction)
    db.commit()
    
    return {
        "status": "success",
        "interaction_id": interaction.id,
        "message": f"Interaction '{interaction_type}' tracked for event {event_id}"
    }


@events_router.post("", response_model=EventOut)
async def create_event(
    name: str = Form(...),
    description: str | None = Form(None),
    date: str = Form(...),
    location: str = Form(...),
    price: float = Form(...),
    total_tickets: int = Form(...),
    category: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Only organizers can create events")

    try:
        event_date = datetime.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601 format.")

    image_url = None
    if image:
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if image.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Unsupported image type. Use JPEG, PNG, or WEBP.")
        extension = Path(image.filename or '').suffix.lower() or '.jpg'
        file_name = f"{uuid.uuid4()}" + extension
        file_path = STATIC_UPLOAD_DIR / file_name
        contents = await image.read()
        file_path.write_bytes(contents)
        image_url = f"/static/event_images/{file_name}"

    new_event = Event(
        name=name,
        description=description,
        date=event_date,
        location=location,
        price=price,
        total_tickets=total_tickets,
        category=category,
        image_url=image_url,
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

@events_router.post("/{event_id}/simulate-withdrawal")
def simulate_withdraw_funds(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id or current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Not authorized to withdraw funds for this event")
    if event.is_funds_withdrawn:
        raise HTTPException(status_code=400, detail="Funds already withdrawn for this event")

    # Simulate fund withdrawal
    event.is_funds_withdrawn = True
    db.commit()
    
    return {"message": f"Funds for event '{event.name}' marked as withdrawn (simulated).", "amount": event.total_revenue}


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
    # Simulate payment by tracking revenue
    event.total_revenue += event.price
    db.commit()

    transfer_events = contract.events.Transfer.process_receipt(tx_receipt)
    mint_event = next((e for e in transfer_events if e['args']['from'] == "0x0000000000000000000000000000000000000000"), None)

    if not mint_event:
        raise HTTPException(status_code=500, detail="Minting Transfer event not found in transaction receipt")

    ticket_id = mint_event['args']['tokenId']

    # Guardar el ticket en la base de datos with simulated payment
    new_ticket_db = Ticket(
        ticket_id_onchain=ticket_id,
        event_id=event.id,
        owner_wallet_address=current_user.wallet_address,
        is_paid=True, # Simulate payment
        purchase_date=datetime.utcnow()
    )
    db.add(new_ticket_db)
    db.commit()
    db.refresh(new_ticket_db)
    
    # --- Tracking automático de compra para sistema de recomendaciones ---
    try:
        purchase_interaction = EventInteraction(
            user_id=current_user.id,
            event_id=event.id,
            interaction_type=InteractionType.PURCHASE,
            created_at=datetime.utcnow()
        )
        db.add(purchase_interaction)
        db.commit()
    except Exception as e:
        # No fallar la compra si el tracking falla
        print(f"Warning: Could not track purchase interaction: {e}")

    return {
        "message": "Ticket purchased and minted successfully", 
        "transaction_hash": tx_hash.hex(),
        "ticket_id": ticket_id,
        "paid_amount": event.price,
        "purchase_date": new_ticket_db.purchase_date.isoformat()
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

# --- Endpoint para obtener tickets vendidos de un evento específico ---
@events_router.get("/{event_id}/purchases", tags=["Analytics"])
def get_event_purchases(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que el evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Verificar que el usuario actual es el organizador del evento
    if current_user.role != UserRole.ORGANIZADOR or event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to view purchases for this event")
    
    # Obtener todos los tickets vendidos para este evento con información del comprador
    tickets = db.query(Ticket).filter(Ticket.event_id == event_id).all()
    
    purchases = []
    for ticket in tickets:
        # Obtener información del comprador
        buyer = db.query(User).filter(User.wallet_address == ticket.owner_wallet_address).first()
        
        purchases.append({
            "ticket_id": ticket.ticket_id_onchain,
            "ticket_db_id": ticket.id,
            "buyer_email": buyer.email if buyer else "Desconocido",
            "buyer_wallet": ticket.owner_wallet_address,
            "purchase_date": ticket.purchase_date.isoformat() if ticket.purchase_date else None,
            "is_paid": ticket.is_paid,
            "price_paid": event.price
        })
    
    return {
        "event_id": event_id,
        "event_name": event.name,
        "total_purchases": len(purchases),
        "total_revenue": event.total_revenue,
        "purchases": purchases
    }

# --- Endpoint para obtener asistentes/clientes de un evento ---
@events_router.get("/{event_id}/attendees", tags=["Analytics"])
def get_event_attendees(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que el evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Verificar que el usuario actual es el organizador del evento
    if current_user.role != UserRole.ORGANIZADOR or event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to view attendees for this event")
    
    # Obtener todos los tickets vendidos para este evento
    tickets = db.query(Ticket).filter(Ticket.event_id == event_id).all()
    
    # Agrupar tickets por wallet address (cliente único)
    attendees_dict = {}
    
    for ticket in tickets:
        wallet = ticket.owner_wallet_address
        
        if wallet not in attendees_dict:
            # Buscar información del usuario
            buyer = db.query(User).filter(User.wallet_address == wallet).first()
            
            attendees_dict[wallet] = {
                "email": buyer.email if buyer else "Desconocido",
                "wallet_address": wallet,
                "tickets_count": 0,
                "total_spent": 0.0,
                "first_purchase_date": ticket.purchase_date,
                "last_purchase_date": ticket.purchase_date,
                "ticket_ids": []
            }
        
        # Actualizar información del asistente
        attendees_dict[wallet]["tickets_count"] += 1
        attendees_dict[wallet]["total_spent"] += event.price
        attendees_dict[wallet]["ticket_ids"].append(ticket.ticket_id_onchain)
        
        # Actualizar fechas
        if ticket.purchase_date:
            if not attendees_dict[wallet]["first_purchase_date"] or ticket.purchase_date < attendees_dict[wallet]["first_purchase_date"]:
                attendees_dict[wallet]["first_purchase_date"] = ticket.purchase_date
            
            if not attendees_dict[wallet]["last_purchase_date"] or ticket.purchase_date > attendees_dict[wallet]["last_purchase_date"]:
                attendees_dict[wallet]["last_purchase_date"] = ticket.purchase_date
    
    # Convertir a lista y formatear fechas
    attendees_list = []
    for attendee_data in attendees_dict.values():
        attendees_list.append({
            "email": attendee_data["email"],
            "wallet_address": attendee_data["wallet_address"],
            "tickets_count": attendee_data["tickets_count"],
            "total_spent": round(attendee_data["total_spent"], 2),
            "first_purchase_date": attendee_data["first_purchase_date"].isoformat() if attendee_data["first_purchase_date"] else None,
            "last_purchase_date": attendee_data["last_purchase_date"].isoformat() if attendee_data["last_purchase_date"] else None,
            "ticket_ids": attendee_data["ticket_ids"]
        })
    
    # Ordenar por cantidad de tickets (mayor a menor)
    attendees_list.sort(key=lambda x: x["tickets_count"], reverse=True)
    
    return {
        "event_id": event_id,
        "event_name": event.name,
        "total_attendees": len(attendees_list),
        "total_tickets_sold": len(tickets),
        "attendees": attendees_list
    }

# --- Endpoint para obtener estadísticas del organizador ---
@admin_router.get("/analytics/organizer-stats", tags=["Analytics"])
def get_organizer_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ORGANIZADOR:
        raise HTTPException(status_code=403, detail="Only organizers can access this endpoint")
    
    # Obtener todos los eventos del organizador
    organizer_events = db.query(Event).filter(Event.owner_id == current_user.id).all()
    event_ids = [event.id for event in organizer_events]
    
    # Estadísticas generales
    total_events = len(organizer_events)
    total_revenue = sum(event.total_revenue or 0 for event in organizer_events)
    
    # Tickets vendidos totales y de esta semana
    from datetime import datetime, timedelta
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    
    all_tickets = db.query(Ticket).filter(Ticket.event_id.in_(event_ids)).all()
    total_tickets_sold = len(all_tickets)
    
    tickets_this_week = db.query(Ticket).filter(
        Ticket.event_id.in_(event_ids),
        Ticket.purchase_date >= one_week_ago
    ).count()
    
    # Comparación con mes anterior para ingresos
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    tickets_last_30_days = db.query(Ticket).filter(
        Ticket.event_id.in_(event_ids),
        Ticket.purchase_date >= thirty_days_ago
    ).all()
    
    tickets_previous_30_days = db.query(Ticket).filter(
        Ticket.event_id.in_(event_ids),
        Ticket.purchase_date >= sixty_days_ago,
        Ticket.purchase_date < thirty_days_ago
    ).all()
    
    revenue_last_30_days = sum(
        db.query(Event).filter(Event.id == ticket.event_id).first().price 
        for ticket in tickets_last_30_days
    )
    
    revenue_previous_30_days = sum(
        db.query(Event).filter(Event.id == ticket.event_id).first().price 
        for ticket in tickets_previous_30_days
    )
    
    # Calcular porcentaje de cambio en ingresos
    if revenue_previous_30_days > 0:
        revenue_change_percentage = ((revenue_last_30_days - revenue_previous_30_days) / revenue_previous_30_days) * 100
    else:
        revenue_change_percentage = 100 if revenue_last_30_days > 0 else 0
    
    # Eventos que finalizan pronto (próximos 7 días)
    next_week = datetime.utcnow() + timedelta(days=7)
    events_ending_soon = db.query(Event).filter(
        Event.owner_id == current_user.id,
        Event.date >= datetime.utcnow(),
        Event.date <= next_week
    ).count()
    
    # Actividad reciente (últimas 10 ventas)
    recent_tickets = db.query(Ticket).filter(
        Ticket.event_id.in_(event_ids)
    ).order_by(Ticket.purchase_date.desc()).limit(10).all()
    
    recent_activity = []
    for ticket in recent_tickets:
        event = db.query(Event).filter(Event.id == ticket.event_id).first()
        if event:
            # Calcular tiempo transcurrido
            time_diff = datetime.utcnow() - ticket.purchase_date
            
            if time_diff.total_seconds() < 3600:  # Menos de 1 hora
                minutes = int(time_diff.total_seconds() / 60)
                time_ago = f"Hace {minutes} min" if minutes > 0 else "Hace un momento"
            elif time_diff.total_seconds() < 86400:  # Menos de 1 día
                hours = int(time_diff.total_seconds() / 3600)
                time_ago = f"Hace {hours} hora{'s' if hours > 1 else ''}"
            else:
                days = int(time_diff.total_seconds() / 86400)
                time_ago = f"Hace {days} día{'s' if days > 1 else ''}"
            
            recent_activity.append({
                "type": "sale",
                "title": "Nueva venta confirmada",
                "event_name": event.name,
                "time_ago": time_ago,
                "timestamp": ticket.purchase_date.isoformat()
            })
    
    # Agregar eventos recientes (creados o actualizados)
    recent_events = db.query(Event).filter(
        Event.owner_id == current_user.id
    ).order_by(Event.id.desc()).limit(5).all()
    
    for event in recent_events:
        # Solo agregar si es reciente (últimas 24 horas)
        # Como no tenemos campo de actualización, usamos la fecha del evento como referencia
        recent_activity.append({
            "type": "event",
            "title": "Evento disponible",
            "event_name": event.name,
            "time_ago": "Recientemente",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    # Ordenar por timestamp y limitar a 5
    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)
    recent_activity = recent_activity[:5]
    
    return {
        "total_events": total_events,
        "total_revenue": total_revenue,
        "total_tickets_sold": total_tickets_sold,
        "tickets_this_week": tickets_this_week,
        "revenue_change_percentage": round(revenue_change_percentage, 1),
        "events_ending_soon": events_ending_soon,
        "recent_activity": recent_activity
    }

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
