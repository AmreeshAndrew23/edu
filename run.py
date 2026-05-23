import uvicorn

# Railway's target port is fixed at 8000 (set in Railway Networking UI).
# Always bind to 8000 so Railway's proxy can reach the container.
print("[QuizThala] Binding to 0.0.0.0:8000", flush=True)

uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,
    log_level="info",
    access_log=True,
    loop="asyncio",
)
