import hmac
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import config
from .db import get_db, init_db
from .models import FAQ, Feedback, Message, Ticket
from .rag import choose, embed, grounded_answer

@asynccontextmanager
async def lifespan(app):
    if not config.ADMIN_API_KEY or config.ADMIN_API_KEY.startswith("CHANGE_"):
        raise RuntimeError("Set a strong ADMIN_API_KEY before startup")
    init_db()
    yield

app = FastAPI(title="XYZ support API", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Admin-Key"])

# Single-instance rate limit. At multiple replicas, move this to a shared gateway.
visits = defaultdict(deque)
@app.middleware("http")
async def limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = visits[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 30:
            return JSONResponse({"detail": "Too many requests"}, status_code=429)
        bucket.append(now)
    return await call_next(request)

class ChatIn(BaseModel):
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=2, max_length=1000)
    language: str = Field(pattern="^(en|my|th)$")

class EscalationIn(BaseModel):
    session_id: uuid.UUID
    contact: str = Field(min_length=5, max_length=200)
    consent: bool

class FeedbackIn(BaseModel):
    session_id: uuid.UUID
    rating: int = Field(ge=-1, le=1)

def admin(x_admin_key: str | None = Header(None)):
    if not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_API_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(FAQ.id).limit(1)).first()
    return {"status": "ok"}

FALLBACK = {
    "en": "I couldn't find a reliable answer in our approved information. Please request a human agent.",
    "my": "အတည်ပြုထားသော အချက်အလက်များတွင် ယုံကြည်စိတ်ချရသော အဖြေ မတွေ့ပါ။ လူသားဝန်ထမ်းနှင့် ဆက်သွယ်ရန် တောင်းဆိုပါ။",
    "th": "ฉันไม่พบคำตอบที่เชื่อถือได้ในข้อมูลที่อนุมัติ กรุณาติดต่อเจ้าหน้าที่",
}

@app.post("/api/chat")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    sid = str(body.session_id or uuid.uuid4())
    faqs = list(db.scalars(select(FAQ).where(FAQ.approved.is_(True), FAQ.language == body.language)))
    faq, confidence = choose(body.message, faqs, embed(body.message))
    answer = grounded_answer(body.message, faq) if faq else FALLBACK[body.language]
    db.add_all([
        Message(session_id=sid, role="user", content=body.message, language=body.language),
        Message(session_id=sid, role="assistant", content=answer, language=body.language, source_id=faq.id if faq else None),
    ])
    db.commit()
    return {"session_id": sid, "answer": answer, "source_id": faq.id if faq else None, "confidence": confidence, "escalate": faq is None}

@app.post("/api/escalations", status_code=201)
def escalate(body: EscalationIn, db: Session = Depends(get_db)):
    if body.consent is not True:
        raise HTTPException(status_code=422, detail="Consent is required")
    if not db.scalar(select(Message.id).where(Message.session_id == str(body.session_id)).limit(1)):
        raise HTTPException(status_code=404, detail="Session not found")
    ticket = Ticket(session_id=str(body.session_id), contact=body.contact)
    db.add(ticket)
    db.commit()
    return {"ticket_id": ticket.id, "status": ticket.status}

@app.post("/api/feedback", status_code=201)
def feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if body.rating == 0:
        raise HTTPException(status_code=422, detail="Use -1 or 1")
    if not db.scalar(select(Message.id).where(Message.session_id == str(body.session_id)).limit(1)):
        raise HTTPException(status_code=404, detail="Session not found")
    db.add(Feedback(session_id=str(body.session_id), rating=body.rating))
    db.commit()
    return {"status": "recorded"}

@app.get("/api/admin/tickets", dependencies=[Depends(admin)])
def tickets(db: Session = Depends(get_db)):
    rows = db.scalars(select(Ticket).order_by(Ticket.created_at.desc()).limit(100)).all()
    return [{"id": t.id, "session_id": t.session_id, "contact": t.contact, "status": t.status, "created_at": t.created_at} for t in rows]

@app.get("/api/admin/feedback", dependencies=[Depends(admin)])
def feedback_list(db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc()).limit(100)).all()
    return [{"session_id": f.session_id, "rating": f.rating, "created_at": f.created_at} for f in rows]
