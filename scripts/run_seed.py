"""Run seed_all() standalone without server restart."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.seed.seed_all import seed_all


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_all(db)
    print("Seed complete.")


asyncio.run(main())
