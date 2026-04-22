# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jabobo Backend is a FastAPI-based backend service for managing smart devices (Jabobo). It handles user authentication, device binding/unbinding, persona configuration, memory sync, and knowledge base (RAG) functionality.

## Development Commands

### Start the server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload
```

### Database management (Docker MySQL)
```bash
./db.sh start        # Start MySQL container
./db.sh list         # View all device bindings
./db.sh users        # View all user accounts
./db.sh index        # Check user_personas table indexes
./db.sh "SQL"        # Execute custom SQL
./db.sh              # Interactive MySQL terminal
```

### API Documentation
- Swagger UI: `http://localhost:8007/docs`
- ReDoc: `http://localhost:8007/redoc`

## Architecture

### Directory Structure
```
app/
├── main.py              # FastAPI app entry point, route registration
├── database.py          # MySQL connection class (MySQLConnector)
├── models/              # Pydantic request/response models
│   └── user.py          # LoginRequest, UserCreateRequest, etc.
├── routes/              # API route handlers by domain
│   ├── auth.py          # Login/logout, multi-platform token management
│   ├── users.py         # User CRUD operations
│   ├── jabobo_config.py # Device persona & memory sync
│   ├── jabobo_manager.py# Device bind/unbind/rebind operations
│   ├── jabobo_knowlege.py # Knowledge base management
│   ├── jabobo_voice.py  # Voice profile management
│   ├── chat_config.py   # Chat differentiation config
│   └── device_data_api.py # Device-side data endpoints
└── utils/
    ├── security.py      # Password hashing (bcrypt), token verification
    ├── dependencies.py  # FastAPI dependencies
    ├── logger.py        # Loguru logger config
    └── rag.py           # RAG (embedding, chunking, retrieval)
```

### Key Patterns

**Database Connection Pattern**: All route handlers follow this pattern:
```python
if not db.connect():
    raise HTTPException(status_code=500, detail="数据库连接失败")
try:
    # Business logic
finally:
    db.close()
```

**Multi-platform Authentication**: Supports web, android, ios tokens. The `CLIENT_TOKEN_MAP` maps client types to token fields in `user_login` table.

**User Verification**: `verify_user(x_username, authorization)` in `security.py` handles token validation across all platforms.

### Database Tables
- `user_login`: User accounts with multi-platform tokens (web_token, android_token, ios_token)
- `user_personas`: Device bindings with personas (JSON), memory, and version info. Has unique constraint on (username, jabobo_id)

### Environment Variables Required
Create a `.env` file in project root with:
```
DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_DATABASE, DB_CHARSET
ARK_API_KEY, ARK_EMBED_MODEL, ARK_BASE_URL  # For RAG functionality
CHUNK_MAX_CHARS, CHUNK_OVERLAP, TOP_K, SIMILARITY_THRESHOLD, BATCH_SIZE
```

### Device ID Format
Accepts either MAC address format (`xx:xx:xx:xx:xx:xx`) or 6-digit numeric code for pairing.

## Testing
Test files are in `test/` directory. Run individual tests with Python directly.
