from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Carbon ESG API",
    version="0.1.0",
    description="API for auditable organizational greenhouse-gas accounting.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "carbon-esg-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Carbon ESG API",
        "version": "0.1.0",
        "docs": "/docs",
    }
