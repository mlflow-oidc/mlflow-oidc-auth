# Microsoft Entra ID

## Get started
Register to have [Microsoft Entra ID](https://www.microsoft.com/security/business/identity-access/microsoft-entra-id)

Register an [application](https://learn.microsoft.com/entra/identity-platform/quickstart-register-app) with the Microsoft identity platform

Please note, that for getting group membership information, the application should have ["GroupMember.Read.All"](https://learn.microsoft.com/graph/api/group-list-members) permission

## Configuration example

```bash
OIDC_DISCOVERY_URL = 'https://login.microsoftonline.com/<tenant_id>/v2.0/.well-known/openid-configuration'
OIDC_CLIENT_SECRET = '<super_secret>'
OIDC_CLIENT_ID = '<client_id>'
OIDC_PROVIDER_DISPLAY_NAME = "Login with Microsoft"
OIDC_GROUP_DETECTION_PLUGIN = 'mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id'
OIDC_SCOPE = "openid,profile,email"
OIDC_GROUP_NAME = "mlflow_users_group_name"
OIDC_ADMIN_GROUP_NAME = "mlflow_admins_group_name"
```
