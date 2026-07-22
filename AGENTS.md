# Agent Customization for league-site

This document helps AI coding agents understand and work effectively in the league-site codebase.

## Project Overview

**league-site** is a Django 6.0.7 + Django REST Framework application for managing a baseball league website for Hamilton's Oldtimers Baseball Organization 55+ Division.

- **Backend**: Django 6.0.7 with DRF (Django REST Framework)
- **Frontend**: Django templates with Tailwind CSS (via django-tailwind)
- **API Documentation**: drf-spectacular (Swagger/OpenAPI)
- **Deployment**: Docker + Gunicorn, Railway/Heroku-ready (Procfile)

See [README.md](README.md) for project roadmap.

## Architecture & Key Conventions

### App Structure
The project uses Django's multi-app architecture under `apps/`:
- **core**: Homepage, standings, leaderboards, schedule views
- **teams**: Team and Season models with detail views
- **players**: Player models with detail views  
- **games**: Game and GameResult models, game scheduling, result tracking
- **stats**: BattingStatLine and PitchingStatLine models for player stats

Each app follows Django conventions:
- `models.py`: Data models
- `serializers.py`: DRF serializers (ModelSerializer)
- `views.py`: ViewSets and function-based views
- `admin.py`: Django admin configuration (uses nested_admin for complex relationships)
- `urls.py`: URL routing (teams and players apps)
- `tests.py`: Test cases using Django TestCase

### API Patterns

**ViewSet Registration** (league_site/urls.py):
```
router = DefaultRouter()
router.register('teams', TeamViewSet)
router.register('seasons', SeasonViewSet)
router.register('players', PlayerViewSet)
router.register('games', GameViewSet)
```

- All ViewSets are **ReadOnlyModelViewSet** (GET only)
- API base path: `/api/`
- API schema: `/api/schema/`
- Swagger docs: `/api/docs/`

**URL Structure**:
- Web views: `/teams/`, `/players/<id>/`, `/games/<id>/`, `/standings/`, `/schedule/`, `/stats/`
- API endpoints: `/api/teams/`, `/api/seasons/`, `/api/players/`, `/api/games/`, `/api/standings/`

### Model Conventions

- Models are in `apps/<app>/models.py`
- Use related_name for reverse relationships (e.g., `related_name='games'`)
- Use Meta.ordering for default ordering
- Add validation in model's `clean()` method (e.g., Game validates home_team ≠ away_team)
- Status fields use CharField with STATUS_CHOICES

**Key Models**:
- **Game**: Home/away teams, date, time, status, venue
- **GameResult**: Inning scores, batting stats (hits, errors, runs)
- **Team**: Team name and info
- **Season**: Year identifier
- **Player**: Player profile with team association
- **BattingStatLine / PitchingStatLine**: Player statistics

### Serializer Patterns

Each app has a `serializers.py` using DRF:
- Use `ModelSerializer` for model-backed serializers
- Include related objects via nested serializers
- Example: GameSerializer includes away_team and home_team (nested TeamSerializer)

### Admin Customization

Uses **django-nested-admin** for complex inline relationships:
- `nested_admin.NestedModelAdmin` for models with nested inlines
- `InningScoreInline` in GameAdmin for nested game result data
- Custom admin displays using list_display, filters, search_fields

## Development & Build Commands

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Database migrations**:
   ```bash
   python manage.py migrate
   ```

3. **Create superuser**:
   ```bash
   python manage.py createsuperuser
   ```

4. **Run development server**:
   ```bash
   python manage.py runserver
   ```

5. **Build Tailwind CSS** (required for styles):
   ```bash
   python manage.py tailwind build  # One-time build
   # OR for watch mode (development):
   python manage.py tailwind install
   python manage.py tailwind dev
   ```

### Frontend/Theme Development

- **Location**: `theme/static_src/` (npm project)
- **Build script**: `npm run build` (PostCSS + Tailwind)
- **Watch mode**: `npm run dev`
- **Output**: `theme/static/css/dist/styles.css`

### Testing

- Use Django's TestCase in `apps/<app>/tests.py`
- Example pattern in `apps/games/tests.py`:
  ```python
  from django.test import TestCase
  from teams.models import Season, Team
  from games.models import Game
  
  class GameResultTests(TestCase):
      def setUp(self):
          self.season = Season.objects.create(year=2026)
          self.team_a = Team.objects.create(name="Hawks")
      
      def test_something(self):
          # Assertions
  ```

- Run tests:
  ```bash
  python manage.py test
  python manage.py test apps.games  # Specific app
  ```

## Configuration & Environment

**Settings** (league_site/settings.py):
- Uses `decouple` library for environment variables
- Key env vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- Database: `dj_database_url` for DATABASE_URL parsing (production)
- Installed apps: rest_framework, drf_spectacular, tailwind, theme, nested_admin

**Static Files**:
- Tailwind CSS build output: `theme/static/css/dist/styles.css`
- Admin and DRF static files collected via `collectstatic`
- Uses WhiteNoiseMiddleware for efficient serving

## Common Patterns & Conventions

1. **Import paths**: Apps are added to sys.path, so imports are `from teams.models import Team` not `from apps.teams.models`

2. **Nested relationships**: Use `nested_admin` for models with complex inline admin relationships

3. **Game status tracking**: Game model has defined STATUS_CHOICES for game workflow (TBP, Final, Canceled, etc.)

4. **Validation**: Model-level validation in `clean()` methods, serializer-level in serializer classes

5. **Ordering**: Most models have Meta.ordering defined for consistent default ordering

6. **Related names**: Always use descriptive related_name on ForeignKey/ManyToMany (e.g., 'games', 'home_games', 'away_games')

## Deployment

- **Docker**: Uses Python 3.12 slim base, Node.js 22 (for Tailwind builds), Gunicorn
- **Build steps** (Dockerfile):
  1. Install Python and Node.js dependencies
  2. Build Tailwind CSS
  3. Collect static files
  4. Run Gunicorn on port 8000
- **Procfile**: `web: gunicorn league_site.wsgi --log-file -` (Heroku/Railway)

## Helpful Tips

- Admin interface: `/admin/` - requires superuser account
- API documentation (interactive): `/api/docs/`
- Swagger schema: `/api/schema/`
- After model changes: `python manage.py makemigrations` → `python manage.py migrate`
- CSS changes in theme require rebuild: `python manage.py tailwind build`
- Import game services for standings/stats computation: `from games.services import compute_standings`

## Skills

- **API Endpoint Management**: See [.github/skills/api-endpoint-management.SKILL.md](.github/skills/api-endpoint-management.SKILL.md) — automates serializer, viewset, router registration, and test skeleton generation following project conventions.
