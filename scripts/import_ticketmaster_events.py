#!/usr/bin/env python3
"""Populate the local database with live Ticketmaster events.

Fetches the Valencia discover feed, extracts event metadata (date, venue,
description, price, image) and upserts everything under a shared organiser
account so that test purchases work out of the box.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from requests import Session

DEFAULT_CITY_URL = "https://www.ticketmaster.es/discover/valencia"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
}
REQUEST_TIMEOUT = 20
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
DEFAULT_TOTAL_TICKETS = 500
DEFAULT_FALLBACK_PRICE = 50.0
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class EventPayload:
    event_id: str
    name: str
    description: str
    start_date: datetime
    location: str
    price: float
    total_tickets: int
    category: Optional[str]
    image_url: Optional[str]
    source_url: str


class TicketmasterError(RuntimeError):
    """Raised when scraping Ticketmaster fails."""


def ensure_database_url(project_root: Path) -> None:
    """Ensure DATABASE_URL is available before importing the FastAPI app."""

    if os.getenv("DATABASE_URL"):
        return

    sqlite_path = project_root / "test.db"
    if sqlite_path.exists():
        os.environ["DATABASE_URL"] = f"sqlite:///{sqlite_path.resolve()}"
    else:
        raise RuntimeError(
            "DATABASE_URL is not set and no fallback test.db database was found."
        )


def parse_next_data(html_text: str) -> Dict[str, Any]:
    match = NEXT_DATA_RE.search(html_text)
    if not match:
        raise TicketmasterError("Unable to locate __NEXT_DATA__ payload in page")
    return json.loads(html.unescape(match.group(1)))


def flatten_events_jsonld(raw_jsonld: Any) -> Dict[str, Dict[str, Any]]:
    """Flatten the JSON-LD structure to a url->metadata lookup."""

    result: Dict[str, Dict[str, Any]] = {}
    if not raw_jsonld:
        return result

    blocks: Iterable[Any]
    if isinstance(raw_jsonld, list):
        blocks = raw_jsonld
    else:
        blocks = [raw_jsonld]

    for block in blocks:
        if isinstance(block, list):
            for entry in block:
                url = entry.get("url")
                if url:
                    result[url] = entry
        elif isinstance(block, dict):
            url = block.get("url")
            if url:
                result[url] = block
    return result


def parse_datetime(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    cleaned = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise TicketmasterError(f"Invalid datetime string: {raw_value}") from exc


def clean_description(raw_text: Optional[str]) -> str:
    if not raw_text:
        return ""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def fetch_json(session: Session, url: str, *, referer: Optional[str] = None) -> Dict[str, Any]:
    headers = DEFAULT_HEADERS.copy()
    if referer:
        headers["Referer"] = referer
    try:
        response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TicketmasterError(f'GET {url} failed: {exc}') from exc
    try:
        return response.json()
    except ValueError as exc:
        raise TicketmasterError(f'Invalid JSON payload from {url}') from exc



def build_city_page_url(base_url: str, page: int) -> str:
    parsed = urlsplit(base_url)
    query = dict(parse_qsl(parsed.query))
    query['page'] = str(page)
    new_query = urlencode(query, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def fetch_city_payload(session: Session, city_url: str, *, limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    aggregated_events: List[Dict[str, Any]] = []
    aggregated_jsonld: Dict[str, Dict[str, Any]] = {}
    total_available: Optional[int] = None
    page = 0
    while True:
        page_url = build_city_page_url(city_url, page)
        response = session.get(page_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        next_data = parse_next_data(response.text)
        page_props = next_data["props"]["pageProps"]
        state = page_props["initialReduxState"]
        queries = state["api"]["queries"]
        city_key = next((key for key in queries if key.startswith("cityEvents")), None)
        if not city_key:
            raise TicketmasterError("cityEvents query not found in initial Redux state")

        data = queries[city_key]["data"]
        events = data.get("events", []) or []
        if not events:
            break

        aggregated_events.extend(events)
        aggregated_jsonld.update(flatten_events_jsonld(page_props.get("eventsJsonLD")))

        if total_available is None:
            total_available = data.get("total")

        if limit is not None and len(aggregated_events) >= limit:
            break
        if total_available is not None and len(aggregated_events) >= total_available:
            break

        page += 1

    if limit is not None and len(aggregated_events) > limit:
        aggregated_events = aggregated_events[:limit]
    return aggregated_events, aggregated_jsonld


def extract_price(ticket_selection: Dict[str, Any]) -> Optional[float]:
    prices: List[float] = []
    for ticket_type in ticket_selection.get("ticketTypes", []) or []:
        for price_entry in ticket_type.get("prices", []) or []:
            value = price_entry.get("faceValue")
            if value is not None:
                prices.append(float(value))
    if prices:
        return min(prices)
    return None


def download_image(session: Session, image_url: str, image_dir: Path, event_id: str) -> Optional[str]:
    if not image_url:
        return None

    image_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        suffix = ".jpg"
    file_name = f"ticketmaster_{event_id}{suffix}"
    destination = image_dir / file_name

    try:
        response = session.get(image_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        destination.write_bytes(response.content)
    except requests.RequestException:
        return None

    return f"/static/event_images/{file_name}"


def build_event_payloads(
    session: Session,
    events: List[Dict[str, Any]],
    jsonld_map: Dict[str, Dict[str, Any]],
    *,
    limit: Optional[int],
    total_tickets: int,
    download_images: bool,
    image_dir: Path,
    fallback_price: float,
) -> List[EventPayload]:
    payloads: List[EventPayload] = []
    seen_event_ids: set[str] = set()
    for entry in events:
        if limit is not None and len(payloads) >= limit:
            break

        event_id = str(entry.get("id"))
        if not event_id or event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)
        source_url = entry.get("url") or ""
        jsonld = jsonld_map.get(source_url, {})

        start_date = parse_datetime(entry.get("dates", {}).get("startDate"))
        if start_date is None:
            continue

        name = entry.get("title") or jsonld.get("name") or f"Evento {event_id}"
        venue = entry.get("venue", {})
        location_parts = [venue.get("name"), venue.get("city")]
        location = ", ".join(part for part in location_parts if part)

        try:
            event_info = fetch_json(session, f"https://www.ticketmaster.es/api/eventinfo/{event_id}", referer=source_url)
        except TicketmasterError as exc:
            print(f"Skipping {event_id}: {exc}")
            continue
        description = clean_description(event_info.get("webInfoNoHtml") or jsonld.get("description"))
        category = None
        if event_info.get("subCategory"):
            category = event_info["subCategory"].get("title")
        elif event_info.get("primaryCategory"):
            category = event_info["primaryCategory"].get("title")

        price = fallback_price
        try:
            ticket_selection = fetch_json(
                session,
                f"https://www.ticketmaster.es/api/ticketselection/{event_id}",
                referer=source_url,
            )
        except TicketmasterError as exc:
            print(f"Price unavailable for {event_id}: {exc}. Using fallback {fallback_price:.2f}.")
        else:
            extracted_price = extract_price(ticket_selection)
            if extracted_price is not None:
                price = extracted_price
            else:
                print(f"Price data missing for {event_id}; using fallback {fallback_price:.2f}.")

        image_url = event_info.get("imageUrl")
        if download_images and image_url:
            local_path = download_image(session, image_url, image_dir, event_id)
            if local_path:
                image_url = local_path

        payloads.append(
            EventPayload(
                event_id=event_id,
                name=name,
                description=description,
                start_date=start_date,
                location=location,
                price=round(price, 2),
                total_tickets=total_tickets,
                category=category,
                image_url=image_url,
                source_url=source_url,
            )
        )

    return payloads


def ensure_organiser(session, email: str, password: str):
    from main import User, UserRole, get_password_hash, verify_password

    organiser = session.query(User).filter(User.email == email).first()
    created = False
    if organiser is None:
        organiser = User(
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ORGANIZADOR,
        )
        session.add(organiser)
        session.commit()
        session.refresh(organiser)
        created = True
    else:
        updated = False
        if organiser.role != UserRole.ORGANIZADOR:
            organiser.role = UserRole.ORGANIZADOR
            updated = True
        if not verify_password(password, organiser.hashed_password):
            organiser.hashed_password = get_password_hash(password)
            updated = True
        if updated:
            session.commit()
            session.refresh(organiser)
    return organiser, created


def upsert_event(session, organiser, payload: EventPayload, dry_run: bool = False) -> str:
    from main import Event

    existing = (
        session.query(Event)
        .filter(Event.name == payload.name, Event.date == payload.start_date)
        .first()
    )

    if existing:
        changes: Dict[str, Any] = {}
        if existing.description != payload.description:
            changes["description"] = payload.description
        if existing.location != payload.location:
            changes["location"] = payload.location
        if existing.price != payload.price:
            changes["price"] = payload.price
        if existing.total_tickets != payload.total_tickets:
            changes["total_tickets"] = payload.total_tickets
        if existing.category != payload.category:
            changes["category"] = payload.category
        if existing.image_url != payload.image_url:
            changes["image_url"] = payload.image_url
        if existing.owner_id != organiser.id:
            changes["owner_id"] = organiser.id

        if not changes:
            return "skipped"

        if dry_run:
            return "would_update"

        for field, value in changes.items():
            setattr(existing, field, value)
        session.commit()
        return "updated"

    if dry_run:
        return "would_create"

    new_event = Event(
        name=payload.name,
        description=payload.description,
        date=payload.start_date,
        location=payload.location,
        price=payload.price,
        total_tickets=payload.total_tickets,
        category=payload.category,
        image_url=payload.image_url,
        owner=organiser,
    )
    session.add(new_event)
    session.commit()
    return "created"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    ensure_database_url(project_root)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-url", default=DEFAULT_CITY_URL, help="Ticketmaster Discover page to scrape")
    parser.add_argument("--limit", type=int, default=None, help="Limit how many events to import")
    parser.add_argument("--organiser-email", default="organizador@example.com", help="Email for the shared organiser account")
    parser.add_argument("--organiser-password", default="organizador123", help="Password for the organiser account")
    parser.add_argument("--total-tickets", type=int, default=DEFAULT_TOTAL_TICKETS, help="Tickets to assign to each imported event")
    parser.add_argument("--fallback-price", type=float, default=DEFAULT_FALLBACK_PRICE, help="Fallback price in EUR when Ticketmaster hides ticket prices")
    parser.add_argument("--keep-remote-images", action="store_true", help="Store Ticketmaster image URLs instead of downloading copies")
    parser.add_argument("--dry-run", action="store_true", help="Only print the actions without touching the database")

    args = parser.parse_args()

    from main import SessionLocal

    session = Session()
    try:
        events, jsonld_map = fetch_city_payload(session, args.city_url, limit=args.limit)
        payloads = build_event_payloads(
            session,
            events,
            jsonld_map,
            limit=args.limit,
            total_tickets=max(1, args.total_tickets),
            download_images=not args.keep_remote_images,
            image_dir=project_root / "static" / "event_images",
            fallback_price=max(0.0, args.fallback_price),
        )
    finally:
        session.close()

    if not payloads:
        print("No events retrieved from Ticketmaster.")
        return

    db_session = SessionLocal()
    try:
        organiser, created = ensure_organiser(db_session, args.organiser_email, args.organiser_password)
        if created:
            print(f"Created organiser account: {organiser.email}")

        summary = {"created": 0, "updated": 0, "skipped": 0, "would_create": 0, "would_update": 0}
        for payload in payloads:
            status = upsert_event(db_session, organiser, payload, dry_run=args.dry_run)
            summary[status] = summary.get(status, 0) + 1
            print(f"{status:>12} :: {payload.name} ({payload.start_date.date()})")

        print("\nSummary:")
        for key, value in summary.items():
            if value:
                print(f"  {key.replace('_', ' ').title()}: {value}")
        if args.dry_run:
            print("Dry-run mode: no database changes were applied.")
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
