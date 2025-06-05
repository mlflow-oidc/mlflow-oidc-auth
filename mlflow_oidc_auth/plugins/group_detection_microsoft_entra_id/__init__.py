import requests


def get_user_groups(access_token):
    graph_url = "https://graph.microsoft.com/v1.0/me/memberOf"
    group_response = requests.get(
        graph_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    group_data = group_response.json()
    return list(dict.fromkeys([group["displayName"] for group in group_data["value"] if group.get("displayName") is not None]))
