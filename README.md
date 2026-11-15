# Budget API

Flask backend for tracking planned vs. actual monthly spending. Each user
registers, logs in, and manages their own monthly budgets.

Live URL: _coming soon_

## Setup

1. Clone the repo and enter it:
   `git clone https://github.com/Rainboi69/budget-api.git && cd budget-api`
2. Create and activate a virtual environment:
   `python -m venv venv` then `source venv/Scripts/activate` (Git Bash on Windows) or `source venv/bin/activate` (macOS/Linux).
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in the values (see Environment variables).
5. Create the database tables: `flask db upgrade`

## Run

`flask run --debug`, then visit http://127.0.0.1:5000/

## Environment variables

| Name | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | Flask secret key. The app will not start without it. |
| `JWT_SECRET` | No | Signs login tokens. Falls back to `SECRET_KEY`. |
| `DATABASE_URL` | Production only | Database connection string. Development falls back to `sqlite:///dev.db`. |
| `TEST_DATABASE_URL` | No | Test database. Defaults to in-memory SQLite. |

## API endpoints

| Method | Path | Access | Success |
|---|---|---|---|
| POST | `/auth/register` | Public | 201 |
| POST | `/auth/login` | Public | 200 |
| GET | `/auth/profile` | Logged-in | 200 |
| POST | `/budgets` | Logged-in | 201 |
| GET | `/budgets` | Logged-in | 200 |
| GET | `/budgets/{id}` | Owner only | 200 |
| PATCH | `/budgets/{id}` | Owner only | 200 |
| DELETE | `/budgets/{id}` | Owner only | 204 |

Send the token from login as `Authorization: Bearer <token>`.
Errors: 400 bad input, 401 missing or invalid token, 403 not your budget, 404 not found.

## Project structure

- `app/__init__.py`: `create_app(config_name)` application factory
- `app/config.py`: development, testing and production config classes
- `app/extensions.py`: `db` and `migrate`
- `app/models.py`: `User` and `Budget` models
- `app/routes.py`: `api` blueprint with auth and budget endpoints
- `migrations/`: database migration history
- `wsgi.py`: entrypoint
