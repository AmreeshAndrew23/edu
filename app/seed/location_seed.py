from sqlalchemy import select

from app.models.country import Country
from app.models.state import State

from app.seed.location_data import (
    INDIA_STATES,
    USA_STATES
)


async def seed_locations(db):

    result = await db.execute(
        select(Country)
    )

    existing = result.scalars().first()

    if existing:
        return

    india = Country(
        code="IN",
        name="India"
    )

    usa = Country(
        code="US",
        name="United States"
    )

    db.add_all([india, usa])

    await db.flush()

    india_states = [
        State(
            code=state["code"],
            name=state["name"],
            country_id=india.id
        )
        for state in INDIA_STATES
    ]

    usa_states = [
        State(
            code=state["code"],
            name=state["name"],
            country_id=usa.id
        )
        for state in USA_STATES
    ]

    db.add_all(india_states + usa_states)

    await db.commit()