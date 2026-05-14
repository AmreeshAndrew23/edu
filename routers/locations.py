from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import Country, State

router = APIRouter(prefix="/api", tags=["locations"])


@router.get("/countries")
async def get_countries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Country))
    countries = result.scalars().all()
    return {"countries": [{"code": c.code, "name": c.name} for c in countries]}


@router.get("/states/{country_code}")
async def get_states(country_code: str, db: AsyncSession = Depends(get_db)):
    code = country_code.upper()
    result = await db.execute(select(Country).where(Country.code == code))
    country = result.scalars().first()
    if not country:
        raise HTTPException(status_code=404, detail=f"No country found for code: {code}")
    result = await db.execute(select(State).where(State.country_id == country.id))
    states = result.scalars().all()
    return {"country_code": code, "states": [{"code": s.code, "name": s.name} for s in states]}
