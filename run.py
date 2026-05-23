import os
import uvicorn

# Railway injects PORT. Hardcode fallback to 8080 (confirmed from Railway logs).
port = int(os.environ.get("PORT", 8080))
print(f"[QuizThala] Binding to 0.0.0.0:{port}", flush=True)

uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    access_log=True,
    loop="asyncio",
)
