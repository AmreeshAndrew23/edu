from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.locations import router as locations_router
from database import engine, async_session
from models import Base, Country, State
from sqlalchemy.future import select

app = FastAPI(title="Country State API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations_router)


@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed data if not present
    async with async_session() as session:
        result = await session.execute(select(Country))
        if not result.scalars().first():
            # Seed countries
            india = Country(code="IN", name="India")
            usa = Country(code="US", name="United States")
            session.add(india)
            session.add(usa)
            await session.flush()

            # India states
            india_states = [
                {"code": "AN", "name": "Andaman and Nicobar Islands"},
                {"code": "AP", "name": "Andhra Pradesh"},
                {"code": "AR", "name": "Arunachal Pradesh"},
                {"code": "AS", "name": "Assam"},
                {"code": "BR", "name": "Bihar"},
                {"code": "CH", "name": "Chandigarh"},
                {"code": "CG", "name": "Chhattisgarh"},
                {"code": "DN", "name": "Dadra and Nagar Haveli and Daman and Diu"},
                {"code": "DL", "name": "Delhi"},
                {"code": "GA", "name": "Goa"},
                {"code": "GJ", "name": "Gujarat"},
                {"code": "HR", "name": "Haryana"},
                {"code": "HP", "name": "Himachal Pradesh"},
                {"code": "JK", "name": "Jammu and Kashmir"},
                {"code": "JH", "name": "Jharkhand"},
                {"code": "KA", "name": "Karnataka"},
                {"code": "KL", "name": "Kerala"},
                {"code": "LA", "name": "Ladakh"},
                {"code": "LD", "name": "Lakshadweep"},
                {"code": "MP", "name": "Madhya Pradesh"},
                {"code": "MH", "name": "Maharashtra"},
                {"code": "MN", "name": "Manipur"},
                {"code": "ML", "name": "Meghalaya"},
                {"code": "MZ", "name": "Mizoram"},
                {"code": "NL", "name": "Nagaland"},
                {"code": "OD", "name": "Odisha"},
                {"code": "PY", "name": "Puducherry"},
                {"code": "PB", "name": "Punjab"},
                {"code": "RJ", "name": "Rajasthan"},
                {"code": "SK", "name": "Sikkim"},
                {"code": "TN", "name": "Tamil Nadu"},
                {"code": "TS", "name": "Telangana"},
                {"code": "TR", "name": "Tripura"},
                {"code": "UP", "name": "Uttar Pradesh"},
                {"code": "UK", "name": "Uttarakhand"},
                {"code": "WB", "name": "West Bengal"},
            ]
            for state in india_states:
                session.add(State(code=state["code"], name=state["name"], country_id=india.id))

            # USA states
            usa_states = [
                {"code": "AL", "name": "Alabama"},
                {"code": "AK", "name": "Alaska"},
                {"code": "AZ", "name": "Arizona"},
                {"code": "AR", "name": "Arkansas"},
                {"code": "CA", "name": "California"},
                {"code": "CO", "name": "Colorado"},
                {"code": "CT", "name": "Connecticut"},
                {"code": "DE", "name": "Delaware"},
                {"code": "DC", "name": "District of Columbia"},
                {"code": "FL", "name": "Florida"},
                {"code": "GA", "name": "Georgia"},
                {"code": "HI", "name": "Hawaii"},
                {"code": "ID", "name": "Idaho"},
                {"code": "IL", "name": "Illinois"},
                {"code": "IN", "name": "Indiana"},
                {"code": "IA", "name": "Iowa"},
                {"code": "KS", "name": "Kansas"},
                {"code": "KY", "name": "Kentucky"},
                {"code": "LA", "name": "Louisiana"},
                {"code": "ME", "name": "Maine"},
                {"code": "MD", "name": "Maryland"},
                {"code": "MA", "name": "Massachusetts"},
                {"code": "MI", "name": "Michigan"},
                {"code": "MN", "name": "Minnesota"},
                {"code": "MS", "name": "Mississippi"},
                {"code": "MO", "name": "Missouri"},
                {"code": "MT", "name": "Montana"},
                {"code": "NE", "name": "Nebraska"},
                {"code": "NV", "name": "Nevada"},
                {"code": "NH", "name": "New Hampshire"},
                {"code": "NJ", "name": "New Jersey"},
                {"code": "NM", "name": "New Mexico"},
                {"code": "NY", "name": "New York"},
                {"code": "NC", "name": "North Carolina"},
                {"code": "ND", "name": "North Dakota"},
                {"code": "OH", "name": "Ohio"},
                {"code": "OK", "name": "Oklahoma"},
                {"code": "OR", "name": "Oregon"},
                {"code": "PA", "name": "Pennsylvania"},
                {"code": "RI", "name": "Rhode Island"},
                {"code": "SC", "name": "South Carolina"},
                {"code": "SD", "name": "South Dakota"},
                {"code": "TN", "name": "Tennessee"},
                {"code": "TX", "name": "Texas"},
                {"code": "UT", "name": "Utah"},
                {"code": "VT", "name": "Vermont"},
                {"code": "VA", "name": "Virginia"},
                {"code": "WA", "name": "Washington"},
                {"code": "WV", "name": "West Virginia"},
                {"code": "WI", "name": "Wisconsin"},
                {"code": "WY", "name": "Wyoming"},
            ]
            for state in usa_states:
                session.add(State(code=state["code"], name=state["name"], country_id=usa.id))

            await session.commit()


@app.get("/health")
def health():
    return {"status": "ok"}
