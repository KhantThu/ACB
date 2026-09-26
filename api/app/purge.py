from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from .config import RETENTION_DAYS
from .db import SessionLocal
from .models import Feedback, Message, Ticket

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    with SessionLocal.begin() as db:
        for model in (Message, Ticket, Feedback):
            db.execute(delete(model).where(model.created_at < cutoff))
    print("Expired conversations, tickets and feedback removed")

if __name__ == "__main__":
    main()
