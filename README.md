# league-site

The Django-based web application for Hamilton's Oldtimers Baseball Organization 55+ Division. It provides a public-facing league website for standings, schedules, leaderboards, and team/player information, while also supporting staff workflows for live game entry and newsletter signups.

## Overview

The project combines a traditional content site with a lightweight internal operations toolset. Visitors can review current season results and league data, while staff users can manage game state, lineups, substitutions, and plate appearances from a dedicated game-entry workspace.

## Key Features

- Public league home page with season highlights and announcements
- Standings, schedule, and leaderboards pages for the current season
- Team, player, and game detail views
- Staff-only game entry portal for managing lineups, substitutions, score state, and game events
- REST API endpoints for announcements, teams, seasons, players, games, and standings
- OpenAPI/Swagger documentation via drf-spectacular
- Newsletter signup and confirmation workflow with optional Resend email integration
- Tailwind-based responsive UI and admin experience

## Architecture

The application follows a modular Django structure under the apps directory:

- core: public site views such as home, standings, schedule, and leaderboards
- teams: team and season models plus related views and serializers
- players: player profiles, rosters, and detail pages
- games: game models, results, and standings computation services
- stats: batting and pitching stat aggregation logic
- game_entry: staff-facing game workspace and HTMX-style fragment updates
- newsletter: subscription forms and email confirmation handling

The project entry point is the Django project in league_site, with URL routing defined in league_site/urls.py and configuration in league_site/settings.py.

## Tech Stack

- Backend: Django 6.0.7, Django REST Framework
- API documentation: drf-spectacular
- Frontend: Django templates, Tailwind CSS via django-tailwind
- Admin: django-nested-admin
- Static files: WhiteNoise, Gunicorn
- Database: SQLite by default for local development; PostgreSQL is supported through DATABASE_URL for production
- Object storage: S3-compatible storage for uploaded media and CKEditor assets, including Railway Buckets
- Email: Resend integration for newsletter confirmations
- Production hosting: Railway with Gunicorn, Docker, and a managed PostgreSQL database

## Project Structure

- apps/: Django apps for the site domain and workflows
- templates/: shared templates for the public and admin-facing UI
- theme/: Tailwind theme assets and build configuration
- staticfiles/: collected static assets
- Dockerfile, Procfile: container and deployment support

## Getting Started

### Prerequisites

- Python 3.11+ (the project targets modern Python)
- Node.js and npm for Tailwind asset builds

### Setup

1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
   On Windows PowerShell:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables as needed
   ```bash
   export SECRET_KEY="your-secret-key"
   export DEBUG="True"
   export DATABASE_URL="sqlite:///db.sqlite3"
   ```

   The project also supports optional settings such as ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, RESEND_API_KEY, RESEND_FROM_EMAIL, RESEND_REPLY_TO, NEWSLETTER_SEND_WELCOME_EMAIL, and SITE_BASE_URL.

4. Run database migrations
   ```bash
   python manage.py migrate
   ```

5. Create an admin user
   ```bash
   python manage.py createsuperuser
   ```

6. Build Tailwind assets
   ```bash
   python manage.py tailwind build
   ```

7. Start the development server
   ```bash
   python manage.py runserver
   ```

## Running Tests

```bash
python manage.py test
```

## API and Documentation

The API is mounted under /api/ and includes routes for league data and schemas. Interactive API docs are available at:

- /api/schema/
- /api/docs/

## Deployment

Production is designed for Railway:

- The Docker image uses Python 3.12 and Node.js 22.
- The image installs Python dependencies, installs and builds Tailwind, and runs `collectstatic`.
- Railway supplies the `PORT` environment variable; the Procfile starts `league_site.wsgi` with Gunicorn.
- Production should use PostgreSQL through `DATABASE_URL` rather than the local SQLite fallback.
- Uploaded media and CKEditor files use the configured S3-compatible storage backend. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, and, where needed, `AWS_S3_ADDRESSING_STYLE` for Railway Buckets or another provider.
- Set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY`, and `DEBUG=False` in the deployment environment. `SITE_BASE_URL` and the `RESEND_*` settings are also needed for production newsletter emails.

### Backups

The GitHub Actions workflow in `.github/workflows/backup.yml` runs every five days at 03:00 UTC and can also be started manually. It:

- Creates and verifies a PostgreSQL custom-format dump from Railway, then uploads it to Cloudflare R2.
- Synchronizes Railway Bucket media to Cloudflare R2 and verifies every uploaded object.
- Retains PostgreSQL dumps for 30 days.
- Creates a GitHub issue when a backup run fails.

Configure the workflow's GitHub Actions secrets for the Railway database and bucket, plus the R2 credentials, endpoint, and bucket name, before relying on automated backups.

## Notes for Contributors

- Model changes should be followed by migrations with python manage.py makemigrations and python manage.py migrate.
- UI changes in the Tailwind theme may require a fresh build with python manage.py tailwind build.
- The game-entry workflow is staff-oriented and relies on Django authentication and admin access.
