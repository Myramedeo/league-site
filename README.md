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
- Database: SQLite by default, with support for PostgreSQL-style DATABASE_URL configuration
- Email: Resend integration for newsletter confirmations

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

The repository includes Docker support and a Procfile for deployment to platforms such as Railway or Heroku. The container build installs Python and Node dependencies, builds Tailwind assets, collects static files, and starts Gunicorn.

## Notes for Contributors

- Model changes should be followed by migrations with python manage.py makemigrations and python manage.py migrate.
- UI changes in the Tailwind theme may require a fresh build with python manage.py tailwind build.
- The game-entry workflow is staff-oriented and relies on Django authentication and admin access.

## Roadmap

- [ ] Rework visuals to be more similar to League Lineup's
- [ ] Import previous dataset
- [ ] Image storage
- [ ] Rework entry / scoring flow
- [ ] Improve player viewing
