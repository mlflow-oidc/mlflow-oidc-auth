class User:
    def __init__(
        self,
        id_,
        username,
        password_hash,
        is_admin,
        is_service_account,
        display_name,
        experiment_permissions=None,
        registered_model_permissions=None,
        groups=None,
    ):
        self._id = id_
        self._username = username
        self._password_hash = password_hash
        self._is_admin = is_admin
        self._is_service_account = is_service_account
        self._experiment_permissions = experiment_permissions
        self._registered_model_permissions = registered_model_permissions
        self._display_name = display_name
        self._groups = groups

    @property
    def id(self):
        return self._id

    @property
    def username(self):
        return self._username

    @property
    def password_hash(self):
        return self._password_hash

    @property
    def is_admin(self):
        return self._is_admin

    @is_admin.setter
    def is_admin(self, is_admin):
        self._is_admin = is_admin

    @property
    def is_service_account(self):
        return self._is_service_account

    @is_service_account.setter
    def is_service_account(self, is_service_account):
        self._is_service_account = is_service_account

    @property
    def experiment_permissions(self):
        return self._experiment_permissions

    @experiment_permissions.setter
    def experiment_permissions(self, experiment_permissions):
        self._experiment_permissions = experiment_permissions

    @property
    def registered_model_permissions(self):
        return self._registered_model_permissions

    @registered_model_permissions.setter
    def registered_model_permissions(self, registered_model_permissions):
        self._registered_model_permissions = registered_model_permissions

    @property
    def display_name(self):
        return self._display_name

    @display_name.setter
    def display_name(self, display_name):
        self._display_name = display_name

    @property
    def groups(self):
        return self._groups

    @groups.setter
    def groups(self, groups):
        self._groups = groups

    def to_json(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin,
            "is_service_account": self.is_service_account,
            "display_name": self.display_name,
            "groups": [g.to_json() for g in self.groups] if self.groups else [],
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            username=dictionary["username"],
            display_name=dictionary["display_name"],
            password_hash="REDACTED",
            is_admin=dictionary["is_admin"],
            is_service_account=dictionary.get("is_service_account", False),
            experiment_permissions=[ExperimentPermission.from_json(p) for p in dictionary["experiment_permissions"]],
            registered_model_permissions=[
                RegisteredModelPermission.from_json(p) for p in dictionary["registered_model_permissions"]
            ],
            groups=[Group.from_json(g) for g in dictionary["groups"]],
        )


class ExperimentPermission:
    def __init__(
        self,
        experiment_id,
        permission,
        user_id=None,
        group_id=None,
    ):
        self._experiment_id = experiment_id
        self._user_id = user_id
        self._permission = permission
        self._group_id = group_id

    @property
    def experiment_id(self):
        return self._experiment_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def permission(self):
        return self._permission

    @permission.setter
    def permission(self, permission):
        self._permission = permission

    @property
    def group_id(self):
        return self._group_id

    @group_id.setter
    def group_id(self, group_id):
        self._group_id = group_id

    def to_json(self):
        return {
            "experiment_id": self.experiment_id,
            "permission": self.permission,
            "user_id": self.user_id,
            "group_id": self.group_id,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            experiment_id=dictionary["experiment_id"],
            permission=dictionary["permission"],
            user_id=dictionary["user_id"],
            group_id=dictionary.get("group_id"),
        )


class RegisteredModelPermission:
    def __init__(
        self,
        name,
        permission,
        user_id=None,
        group_id=None,
        prompt=False,
    ):
        self._name = name
        self._user_id = user_id
        self._permission = permission
        self._group_id = group_id
        self._prompt = prompt

    @property
    def name(self):
        return self._name

    @property
    def user_id(self):
        return self._user_id

    @property
    def permission(self):
        return self._permission

    @permission.setter
    def permission(self, permission):
        self._permission = permission

    @property
    def group_id(self):
        return self._group_id

    @group_id.setter
    def group_id(self, group_id):
        self._group_id = group_id

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, prompt):
        self._prompt = prompt

    def to_json(self):
        return {
            "name": self.name,
            "user_id": self.user_id,
            "permission": self.permission,
            "group_id": self.group_id,
            "prompt": self.prompt,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            name=dictionary["name"],
            user_id=dictionary["user_id"],
            permission=dictionary["permission"],
            group_id=dictionary.get("group_id"),
            prompt=bool(dictionary.get("prompt", False)),
        )


class Group:
    def __init__(self, id_, group_name):
        self._id = id_
        self._group_name = group_name

    @property
    def id(self):
        return self._id

    @property
    def group_name(self):
        return self._group_name

    def to_json(self):
        return {
            "id": self.id,
            "group_name": self.group_name,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            group_name=dictionary["group_name"],
        )


class UserGroup:
    def __init__(self, user_id, group_id):
        self._user_id = user_id
        self._group_id = group_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def group_id(self):
        return self._group_id

    def to_json(self):
        return {
            "user_id": self.user_id,
            "group_id": self.group_id,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            user_id=dictionary["user_id"],
            group_id=dictionary["group_id"],
        )
