from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import beacons, map, route, position
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


app = FastAPI(title="Indoor Navigation API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/admin")
def admin():
    return FileResponse("admin.html")
    
@app.on_event("startup")
def startup():
    init_db()

app.include_router(beacons.router)
app.include_router(map.router)
app.include_router(route.router)
app.include_router(position.router)

@app.get("/")
def root():
    return {"status": "ok", "version": "1.0"}