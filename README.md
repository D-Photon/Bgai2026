# BGAI student exam registration

A FastAPI registration site for BGAI students. It stores submitted registrations in Neon PostgreSQL and lets each student download a PDF confirmation.

## Registration rules

- Departments: Science, Art, and Commercial.
- English and Mathematics are compulsory.
- Students choose up to three additional subjects, for five subjects maximum.
- Exam numbers follow `BGAI/GMCC/YYYY/XXX`; the final part increments from the highest existing number for that year, starts at `001` when that year has no registrations, and expands past three digits when needed.

## Local setup

1. Install Python 3.12 or newer.
2. Create a virtual environment and install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, then set `DATABASE_URL` to your Neon connection string. Include `?sslmode=require`.
4. Start the app with `uvicorn main:app --reload`.
5. Open `http://127.0.0.1:8000`.

The app requires Neon PostgreSQL. It loads `DATABASE_URL` from `.env` locally and from the service environment on Render. It does not fall back to SQLite.

## Neon schema

`schema.sql` contains the PostgreSQL DDL. The app executes `schema.sql` at startup, including a safe migration to add the normalized full-name key to existing registrations. Keep the Neon connection string out of source control. Store the Neon connection string in Render's `DATABASE_URL` environment variable; do not commit `.env` or credentials.

## Deploy on Render

This repository includes `render.yaml` and a `Dockerfile`. Create a Render web service from the repository, add the Neon connection string as `DATABASE_URL`, and deploy. The service listens on Render's `PORT`, and `/health` is its health check.

## API

- `GET /` registration form
- `POST /register` validate, reject duplicate full names, and save registration
- `GET /registration/{download_token}` show the confirmation page safely after redirect
- `GET /students/{download_token}/registration.pdf` download that student's registration PDF
- `GET /health` service health check





