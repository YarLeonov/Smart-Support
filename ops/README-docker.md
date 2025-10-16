# Smart Support — Docker Deployment

This docker setup builds:
- **backend** (FastAPI/uvicorn) on port `8000`
- **frontend** (Nginx serving built Vite app) on port `8080`, proxying `/api` to backend

## Structure
```
backend/
frontend/
kb/
  index.json
  entities.json
  synonyms.json
  articles/*.md
docker/
  Dockerfile.backend
  Dockerfile.frontend
  nginx.conf
docker-compose.yml
```

## Build & Run
```bash
docker compose build
docker compose up -d
```

- UI: http://localhost:8080
- API: http://localhost:8000/health (or via proxy: http://localhost:8080/api/health)

## Notes
- Frontend is built with `VITE_API_URL=/api`, so browser calls go to same origin and Nginx proxies to backend.
- KB is mounted from `./kb` into `/app/kb` (read-only) in backend container, so you can update KB without rebuild.
- Optional env for backend: `MIN_HIT_SCORE=0.000001` to hide near-zero matches server-side.
