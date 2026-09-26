"""Integration tests require TEST_DATABASE_URL pointing at disposable pgvector Postgres."""
import os
import pytest

if not os.getenv("TEST_DATABASE_URL"):
    pytest.skip("Set TEST_DATABASE_URL for database integration tests", allow_module_level=True)

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ADMIN_API_KEY"] = "test-secret-not-for-production"
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import FAQ

@pytest.fixture
def client():
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        db.add(FAQ(slug="shipping", language="en", category="delivery", question="Where can I see delivery status?", answer="See your Orders page.", approved=True))
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)

def test_chat_answer_and_escalation(client):
    result = client.post("/api/chat", json={"message":"Where can I see delivery status?","language":"en"})
    assert result.status_code == 200
    assert result.json()["answer"] == "See your Orders page."
    assert result.json()["source_id"] is not None
    unknown = client.post("/api/chat", json={"message":"Reset two factor authentication","language":"en"}).json()
    assert unknown["escalate"] is True
    ticket = client.post("/api/escalations", json={"session_id":unknown["session_id"],"contact":"test@example.com","consent":True})
    assert ticket.status_code == 201

def test_admin_auth_and_validation(client):
    assert client.get("/api/admin/tickets").status_code == 403
    assert client.post("/api/chat", json={"message":"x","language":"en"}).status_code == 422
    assert client.post("/api/chat", json={"message":"valid question","language":"fr"}).status_code == 422
