# API Endpoint Management Skill

Purpose
- Automate creation and maintenance of API endpoints following the league-site conventions.

When to use
- Add new resource endpoints (models → serializer → viewset → router).
- Generate or update serializers and ViewSets for existing models.
- Register viewsets on the project's `DefaultRouter` in `league_site/urls.py`.
- Generate simple read-only tests for new endpoints.

Capabilities
- Create a `ModelSerializer` in `apps/<app>/serializers.py` that nests related objects when appropriate.
- Create a `ReadOnlyModelViewSet` in `apps/<app>/views.py` with `queryset` and `serializer_class` set.
- Add router registration entries in `league_site/urls.py` (use `router.register('<plural>', <ViewSet>)`).
- Add minimal `tests.py` TestCase skeletons for endpoint coverage.

Conventions & Rules
- Use project import style: `from teams.models import Team` (not `from apps.teams.models`).
- All API ViewSets should be read-only (`ReadOnlyModelViewSet`).
- Serializers should use `ModelSerializer` and include `Meta.fields = '__all__'` unless otherwise requested.
- Follow existing naming: `TeamSerializer`, `TeamViewSet`, router path `teams`.
- When adding router registrations, place them near existing registrations in `league_site/urls.py` and keep alphabetic ordering when practical.

Safe-guards
- Do not run migrations, installs, or tests automatically. Suggest commands for the developer to run:

```
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

- If a file already exists, prefer to add minimal, non-destructive edits and preserve existing code style.

Example prompts for this skill
- "Create a serializer and viewset for `Batter` in `stats` and register it on the API router."
- "Add a read-only API for `teams.Team` including nested `Season` data in the serializer."

Limitations
- This skill will not infer complex business logic; add manual checks for permissions, filters, or custom queryset logic.
- Will not modify production deployment configs.

Location
- Place this skill documentation at `.github/skills/api-endpoint-management.SKILL.md` in the repository.
