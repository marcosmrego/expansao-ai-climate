from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.climate_alerts import router as climate_alert_router


app = FastAPI(
    title="Expansão AI Climate API",
    description="API para dados climáticos, NOAA, ONI, SST e alertas operacionais.",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(climate_alert_router)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Expansão AI Climate API"
    }