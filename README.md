# Country State API

A FastAPI backend application that provides countries and their states, using PostgreSQL database.

## Features

- Get list of countries (India and USA)
- Get states for a specific country
- Automatic database table creation and seeding

## API Endpoints

- `GET /api/countries` - Returns list of countries
- `GET /api/states/{country_code}` - Returns states for the given country code (e.g., `/api/states/IN` for India, `/api/states/US` for USA)
- `GET /health` - Health check

## Deployment on Railway

1. Create a Railway account at https://railway.app
2. Connect your GitHub repository
3. Add a PostgreSQL database in the Railway dashboard
4. Deploy the application
5. Railway will automatically set the `DATABASE_URL` environment variable

## Local Development

For local development on Windows with Python 3.13, there are compatibility issues with SQLAlchemy. The application is designed to work on Railway with PostgreSQL.

### For Linux/Mac or different Python versions:

1. Install dependencies: `pip install -r requirements.txt`
2. Set `DATABASE_URL` environment variable to your PostgreSQL connection string
3. Run the application: `uvicorn main:app --reload`

## Database

The application uses SQLAlchemy with async PostgreSQL support. Tables are created automatically on startup, and initial data is seeded if the database is empty.

## Requirements

- Python 3.11+ (for Railway deployment)
- PostgreSQL database
- Railway account for deployment

The application uses SQLAlchemy with async PostgreSQL support. Tables are created automatically on startup, and initial data is seeded if the database is empty.