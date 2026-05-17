from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.country import Country
from app.models.state import State

router = APIRouter(
    prefix="/countries",
    tags=["Countries"]
)


@router.get("/")
async def get_countries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Country).order_by(Country.name)
    )

    countries = result.scalars().all()

    return {
        "success": True,
        "count": len(countries),
        "data": [
            {
                "id": country.id,
                "code": country.code,
                "name": country.name
            }
            for country in countries
        ]
    }


@router.get("/{country_code}/states")
async def get_states_by_country(
    country_code: str,
    db: AsyncSession = Depends(get_db)
):
    country_result = await db.execute(
        select(Country).where(
            Country.code == country_code.upper()
        )
    )

    country = country_result.scalars().first()

    if not country:
        raise HTTPException(
            status_code=404,
            detail="Country not found"
        )

    state_result = await db.execute(
        select(State)
        .where(State.country_id == country.id)
        .order_by(State.name)
    )

    states = state_result.scalars().all()

    return {
        "success": True,
        "country": {
            "id": country.id,
            "code": country.code,
            "name": country.name
        },
        "count": len(states),
        "data": [
            {
                "id": state.id,
                "code": state.code,
                "name": state.name
            }
            for state in states
        ]
    }
    