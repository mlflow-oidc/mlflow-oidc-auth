from authlib.integrations.starlette_client import OAuth
from mlflow_oidc_auth.config import config

oauth = OAuth()
oauth.register(
    name="oidc",
    client_id=config.OIDC_CLIENT_ID,
    client_secret=config.OIDC_CLIENT_SECRET,
    server_metadata_url=config.OIDC_DISCOVERY_URL,
    client_kwargs={"scope": config.OIDC_SCOPE},
)
