import unittest
from unittest.mock import patch
from mlflow_oidc_auth.token_utils import token_get_user_groups, token_get_user_is_admin
from mlflow_oidc_auth.config import config


@patch("mlflow_oidc_auth.token_utils.config.OIDC_GROUP_FILTER_PATTERNS", new=["mlflow-*"])
@patch("mlflow_oidc_auth.token_utils.config.OIDC_ADMIN_GROUP_NAME", new="admin-mlflow")
class TestGroupMemberships(unittest.TestCase):

    def test_user_in_all_groups_and_admin_group(self):

        token = {
            "userinfo": {
                config.OIDC_GROUPS_ATTRIBUTE: [
                    "mlflow-user-team1",
                    "mlflow-user-team2",
                    config.OIDC_ADMIN_GROUP_NAME,
                ]
            }
        }

        user_groups = token_get_user_groups(token)
        is_admin = token_get_user_is_admin(user_groups)

        self.assertEqual(len(user_groups), len(token["userinfo"][config.OIDC_GROUPS_ATTRIBUTE]))
        self.assertTrue(is_admin)

    def test_user_in_no_groups_but_in_admin_group(self):

        token = {
            "userinfo": {
                config.OIDC_GROUPS_ATTRIBUTE: [
                    "otherapp-team1",
                    "otherapp-team2",
                    config.OIDC_ADMIN_GROUP_NAME,
                ]
            }
        }

        user_groups = token_get_user_groups(token)
        is_admin = token_get_user_is_admin(user_groups)

        self.assertEqual(len(user_groups), 1)
        self.assertTrue(is_admin)

    def test_user_in_no_groups_not_in_admin_group(self):

        token = {
            "userinfo": {
                config.OIDC_GROUPS_ATTRIBUTE: [
                    "otherapp-team1",
                    "otherapp-team2",
                ]
            }
        }

        user_groups = token_get_user_groups(token)
        is_admin = token_get_user_is_admin(user_groups)

        self.assertEqual(len(user_groups), 0)
        self.assertFalse(is_admin)

    def test_user_in_groups_not_in_admin_group(self):

        token = {
            "userinfo": {
                config.OIDC_GROUPS_ATTRIBUTE: [
                    "otherapp-team1",
                    "otherapp-team2",
                    "mlflow-user-team1",
                    "mlflow-user-team2",
                ]
            }
        }

        user_groups = token_get_user_groups(token)
        is_admin = token_get_user_is_admin(user_groups)

        self.assertEqual(len(user_groups), 2)
        self.assertFalse(is_admin)
