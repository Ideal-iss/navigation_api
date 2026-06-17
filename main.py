from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, reset_graph, db_session
from routers import beacons, map, route, position
from fastapi.responses import FileResponse

API_VERSION = "1.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # инициализация БД при старте (заменяет устаревший on_event)
    yield


app = FastAPI(title="Indoor Navigation API", version=API_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/admin")
def admin():
    return FileResponse("admin.html")

app.include_router(beacons.router)
app.include_router(map.router)
app.include_router(route.router)
app.include_router(position.router)

@app.post("/admin/reset-graph")
def admin_reset_graph():
    with db_session() as conn:
        reset_graph(conn)
    return {"ok": True, "message": "Граф навигации перезагружен"}

@app.get("/")
def root():
    return {"status": "ok", "version": API_VERSION}

@app.get("/health")
def health():
    """Состояние сервиса и наполнение БД — для мониторинга и диагностики."""
    with db_session() as conn:
        beacons_n = conn.execute("SELECT COUNT(*) FROM beacons").fetchone()[0]
        nodes_n   = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges_n   = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return {
        "status":  "ok",
        "version": API_VERSION,
        "db": {"beacons": beacons_n, "nodes": nodes_n, "edges": edges_n},
    }