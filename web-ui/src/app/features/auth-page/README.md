# Auth Page Feature

This feature provides authentication handling for the MLflow OIDC application.

## Overview

The auth page is displayed when the backend configuration indicates that the user is not authenticated (`authenticated: false` in config.json).

## Configuration

The auth page expects the following configuration from the backend via `config.json`:

```json
{
  "basePath": "",
  "uiPath": "/oidc/ui",
  "provider": "Login with Test",
  "authenticated": false
}
```

### Required Fields

- `authenticated`: Boolean indicating if the user is authenticated
- `basePath`: Base path for the application (used for constructing login URL)
- `uiPath`: UI path for the application
- `provider`: Display name for the login provider (optional, defaults to "Login with Test")

## Flow

1. Application loads and checks `config.json`
2. If `authenticated` is `false`, user is redirected to `/auth` route
3. Auth page displays login button with configured provider name
4. Login button redirects to `{basePath}/login` endpoint
5. After successful authentication, backend should serve config with `authenticated: true`

## Components

- **AuthPageComponent**: Main component that displays the login interface
- **RuntimeConfigService**: Service that manages configuration state
- **AuthConfigResolver**: Resolver that provides config to the auth page

## Error Handling

The auth page can display error messages passed via query parameters:
- Single error: `?error=Error message`
- Multiple errors: `?error=Error 1&error=Error 2`

## Styling

The auth page features:
- Responsive design
- Material Design components
- Gradient background
- Animated error messages
- Clean, modern interface

## Testing

The feature includes comprehensive unit tests for all components and services.
