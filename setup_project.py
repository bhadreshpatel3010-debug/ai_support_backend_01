from pathlib import Path

# Uses your currently open folder instead of creating a duplicate
project_root = Path(".")

files = [
    "app/__init__.py",
    "app/main.py",
    "app/core/__init__.py",
    "app/core/config.py",
    "app/core/database.py",
    "app/core/redis_client.py",
    "app/core/security.py",
    "app/models/__init__.py",
    "app/models/domain.py",
    "app/schemas/__init__.py",
    "app/schemas/api_schemas.py",
    "app/services/__init__.py",
    "app/services/rag_service.py",
    "app/routers/__init__.py",
    "app/routers/auth.py",
    "app/routers/documents.py",
    "app/routers/chat.py",
    "app/routers/ws_chat.py",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "requirements.txt",
    ".env",
]

for file_path in files:
    full_path = project_root / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.touch(exist_ok=True)

print("✅ All folders and files created directly inside your project!")
