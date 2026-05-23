import os
import uvicorn

port = int(os.environ.get("PORT", 8000))
print(f"[QuizThala] Binding to 0.0.0.0:{port}", flush=True)

uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    access_log=True,
    loop="asyncio",   # disable uvloop — avoids known asyncpg/uvloop conflicts
)
