We are working on migration from Flask to FastAPI. You don't need to keep backward compatibility, reimplement anything with FastAPI-native constructs and remove unused files and flask imports.

Migration plan:
* Move routes implemented in routes.py from Flask application to FastAPI application (remove mount from app.py and move it to fastapi)
* Rework Authentication and Authorization logic to use as FastAPI middleware
* Rework flask before_request and after_request hooks to FastAPI middleware
* Bring native FastAPI session instead of Flask session
* Get rid of flask caching in favor of FastAPI caching
* Rework default page from jinja template to Angular default page

Middlewares:
- AuthMiddleware (handle authentication and authorization, support basic, bearer token and session-based)
- Legacy (handle WSGIMiddleware with Flask app)
- SessionMiddleware (handle user sessions)
- PermissionsMiddleware (handle filtering content and access management, line in before_request, after_request)

Routers:
- ui (serve static SPA)
- auth (handle OIDC auth)
- permissions (handle API for permission management)
- mlflow (mounted to / to provide MLflow)

Do not modify Flask-related code, build new one in parallel with FastAPI implementation. Use FastAPI-native constructs and features wherever possible. Follow best practices for FastAPI development.
