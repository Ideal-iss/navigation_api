import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, reset_graph, db_session
from routers import beacons, map, route, position, floors, rooms
from fastapi.responses import FileResponse

ADMIN_KEY = os.getenv("ADMIN_KEY", "changeme")

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
app.include_router(floors.router)
app.include_router(rooms.router)

@app.post("/admin/reset-graph")
def admin_reset_graph(x_admin_key: str = Header(default="")):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(401, "Неверный admin-ключ")
    with db_session() as conn:
        reset_graph(conn)
    return {"ok": True, "message": "Граф навигации перезагружен"}

@app.post("/admin/floor-plan/{floor}/image")
async def upload_floor_plan_image(
    floor: int,
    file: UploadFile = File(...),
    x_admin_key: str = Header(default=""),
):
    """Загрузить PNG/SVG план этажа как фоновое изображение для редактора графа."""
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(401, "Неверный admin-ключ")
    allowed = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(400, f"Неподдерживаемый тип файла: {file.content_type}")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "png"
    path = f"floor_plan_{floor}.{ext}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"ok": True, "path": path, "floor": floor}


@app.get("/admin/floor-plan/{floor}/image")
def get_floor_plan_image(floor: int):
    """Отдать загруженное изображение плана этажа."""
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        path = f"floor_plan_{floor}.{ext}"
        if os.path.exists(path):
            return FileResponse(path)
    raise HTTPException(404, "Изображение плана не найдено")

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