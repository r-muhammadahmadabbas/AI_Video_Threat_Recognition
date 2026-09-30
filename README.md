# AI Video Threat Recognition

A production-ready AI safety layer for existing surveillance infrastructure. Detects threats in video streams, requires human verification before alerting.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────►│    API      │────►│  PostgreSQL │
│  (React)    │     │  (FastAPI)  │     │   (Data)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌─────────┐  ┌──────────┐  ┌──────────┐
         │CV Worker│  │Evidence  │  │ Notify   │
         │(YOLO26) │  │ Worker   │  │ Worker   │
         └─────────┘  └──────────┘  └──────────┘
              │
              ▼
         ┌─────────┐
         │  Redis  │
         │ (Queue) │
         └─────────┘
```

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# 2. Start all services
docker compose -f docker/docker-compose.yml up -d

# 3. Access
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health/ready
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 5173 | React dashboard |
| API | 8000 | FastAPI REST API |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Queue & cache |
| CV Worker | - | Video inference (YOLO26) |
| Evidence Worker | - | Clip generation |
| Notification Worker | - | Alert delivery |

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload

# Start CV worker (separate terminal)
python -m workers.cv_worker.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Configuration

All settings via `backend/.env`:

```env
# Database
DB_HOST=localhost
DB_PASSWORD=your_password

# Auth (CHANGE IN PRODUCTION!)
AUTH_SECRET_KEY=your-32-char-secret-key

# Model
MODEL_DETECTOR_NAME=yolo26n
MODEL_INFERENCE_DEVICE=cpu
MODEL_INFERENCE_TARGET_FPS=5

# Video
VIDEO_CLIP_PRE_SECONDS=5
VIDEO_CLIP_POST_SECONDS=5
```

## API Endpoints

### Authentication
- `POST /auth/login` - Get access/refresh tokens
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Current user info

### Cameras
- `GET /cameras` - List cameras (paginated)
- `POST /cameras` - Add camera
- `PATCH /cameras/{id}` - Update camera
- `DELETE /cameras/{id}` - Delete camera

### Incidents
- `GET /incidents` - List incidents (filterable)
- `GET /incidents/{id}` - Incident details
- `POST /incidents/{id}/verify` - Verify incident
- `POST /incidents/{id}/dismiss` - Dismiss incident

### Zones & Rules
- `GET/POST/PATCH/DELETE /zones` - Zone management
- `GET/POST/PATCH/DELETE /rules` - Threat rule management

### Evidence
- `GET /evidence/incident/{id}` - List evidence for incident
- `GET /evidence/{id}/file` - Download clip/image
- `GET /evidence/{id}/thumbnail` - Get thumbnail

### Users & Audit (Admin only)
- `GET/POST/PATCH/DELETE /users` - User management
- `GET /audit` - Audit logs

## Threat Types

| Type | Description |
|------|-------------|
| `restricted_zone_entry` | Person enters restricted polygon |
| `loitering` | Person stays in zone > threshold |
| `person_down` | Fall + motionless detection |
| `fight` | Aggressive pairwise motion |
| `crowd_anomaly` | Abnormal collective movement |
| `weapon` | Visible weapon detection |

## Incident State Machine

```
DETECTED → PENDING_REVIEW → VERIFIED → NOTIFICATION_SENT
                ↓
           DISMISSED
                ↓
           MERGED (deduplication)
```

## Model

Uses **YOLO26-nano** (`yolo26n.pt`) - Ultralytics' latest edge-optimized model:
- 43% faster CPU inference than YOLO11n
- End-to-end NMS-free architecture
- Auto-downloads on first run (~6 MB)

## Production Deployment

1. Set `ENVIRONMENT=production`
2. Use PostgreSQL (not SQLite)
3. Set strong `AUTH_SECRET_KEY`
4. Configure `STORAGE_TYPE=s3` for evidence
5. Enable `LOG_FORMAT=json`
6. Set up reverse proxy (nginx/Traefik)
7. Configure SSL/TLS

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config/              # Pydantic settings
│   ├── db/                  # SQLAlchemy models + session
│   ├── auth/                # JWT + RBAC
│   ├── cameras/             # Camera CRUD
│   ├── incidents/           # Incident management
│   ├── zones/               # Zone polygons
│   ├── rules/               # Threat rules
│   ├── evidence/            # Media serving
│   ├── users/               # User management
│   ├── audit/               # Audit logging
│   └── health/              # Health endpoints
├── workers/
│   ├── cv_worker/           # Video inference
│   ├── evidence_worker/     # Clip generation
│   └── notification_worker/ # Alert delivery
└── alembic/                 # Migrations

frontend/
├── src/
│   ├── pages/               # Route components
│   ├── components/          # Shared UI
│   ├── contexts/            # React context
│   ├── services/            # API client
│   └── hooks/               # Custom hooks
```

## License

Internal use only.