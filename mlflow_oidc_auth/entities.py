class User:
    def __init__(
        self,
        id_,
        username,
        password_hash,
        is_admin,
        display_name,
        experiment_permissions=None,
        registered_model_permissions=None,
    ):
        self._id = id_
        self._username = username
        self._password_hash = password_hash
        self._is_admin = is_admin
        self._experiment_permissions = experiment_permissions
        self._registered_model_permissions = registered_model_permissions
        self._display_name = display_name

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

    def to_json(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin,
            "display_name": self.display_name,
            "experiment_permissions": [p.to_json() for p in self.experiment_permissions],
            "registered_model_permissions": [p.to_json() for p in self.registered_model_permissions],
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            username=dictionary["username"],
            display_name=dictionary["display_name"],
            password_hash="REDACTED",
            is_admin=dictionary["is_admin"],
            experiment_permissions=[ExperimentPermission.from_json(p) for p in dictionary["experiment_permissions"]],
            registered_model_permissions=[
                RegisteredModelPermission.from_json(p) for p in dictionary["registered_model_permissions"]
            ],
        )


class ExperimentPermission:
    def __init__(
        self,
        experiment_id,
        user_id,
        permission,
    ):
        self._experiment_id = experiment_id
        self._user_id = user_id
        self._permission = permission

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

    def to_json(self):
        return {
            "experiment_id": self.experiment_id,
            "user_id": self.user_id,
            "permission": self.permission,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            experiment_id=dictionary["experiment_id"],
            user_id=dictionary["user_id"],
            permission=dictionary["permission"],
        )


class RegisteredModelPermission:
    def __init__(
        self,
        name,
        user_id,
        permission,
    ):
        self._name = name
        self._user_id = user_id
        self._permission = permission

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

    def to_json(self):
        return {
            "name": self.name,
            "user_id": self.user_id,
            "permission": self.permission,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            name=dictionary["name"],
            user_id=dictionary["user_id"],
            permission=dictionary["permission"],
        )
