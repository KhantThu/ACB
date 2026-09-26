import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://xyzchat:xyzchat@localhost/xyzchat")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ALLOWED_ORIGINS = [s.strip() for s in os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",") if s.strip()]
ENABLE_AI = os.getenv("ENABLE_AI", "false").lower() == "true"
ENABLE_GENERATION = os.getenv("ENABLE_GENERATION", "false").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:3b")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
