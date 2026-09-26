"""Import reviewed FAQ CSV from stdin. Does not accept raw support transcripts."""
import csv
import sys
from sqlalchemy import select
from .db import SessionLocal, init_db
from .models import FAQ
from .rag import embed

def main():
    init_db()
    reader = csv.DictReader(sys.stdin)
    required = {"slug", "language", "category", "question", "answer", "approved"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise SystemExit(f"CSV columns required: {', '.join(sorted(required))}")
    count = 0
    with SessionLocal.begin() as db:
        for row in reader:
            if row["language"] not in {"en", "my", "th"}:
                raise SystemExit("Unsupported language")
            if row["approved"].strip().lower() not in {"true", "false"}:
                raise SystemExit("approved must be true or false")
            if any(not row[k].strip() for k in required - {"approved"}):
                raise SystemExit("Empty FAQ field")
            faq = db.scalar(select(FAQ).where(FAQ.slug == row["slug"], FAQ.language == row["language"]))
            if faq is None:
                faq = FAQ(slug=row["slug"], language=row["language"])
                db.add(faq)
            faq.category = row["category"]
            faq.question = row["question"]
            faq.answer = row["answer"]
            faq.approved = row["approved"].strip().lower() == "true"
            faq.embedding = embed(row["question"]) if faq.approved else None
            count += 1
    print(f"Imported {count} FAQ translations")

if __name__ == "__main__":
    main()
