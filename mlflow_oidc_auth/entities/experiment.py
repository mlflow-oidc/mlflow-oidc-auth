
class ExperimentPermission:
    def __init__(self, experiment_id, permission, user_id=None, group_id=None):
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
            user_id=dictionary.get("user_id"),
            group_id=dictionary.get("group_id"),
        )


class ExperimentGroupRegexPermission:
    def __init__(
        self,
        id_,
        regex,
        priority,
        group_id,
        permission,
    ):
        self._id = id_
        self._regex = regex
        self._priority = priority
        self._group_id = group_id
        self._permission = permission

    @property
    def id(self):
        return self._id

    @property
    def regex(self):
        return self._regex

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, priority):
        self._priority = priority

    @property
    def group_id(self):
        return self._group_id

    @property
    def permission(self):
        return self._permission

    @permission.setter
    def permission(self, permission):
        self._permission = permission

    def to_json(self):
        return {
            "id": self.id,
            "regex": self.regex,
            "priority": self.priority,
            "group_id": self.group_id,
            "permission": self.permission,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            group_id=dictionary["group_id"],
            permission=dictionary["permission"],
        )


class ExperimentRegexPermission:
    def __init__(
        self,
        id_,
        regex,
        priority,
        user_id,
        permission,
    ):
        self._id = id_
        self._regex = regex
        self._priority = priority
        self._user_id = user_id
        self._permission = permission

    @property
    def id(self):
        return self._id

    @property
    def regex(self):
        return self._regex

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, priority):
        self._priority = priority

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
            "id": self.id,
            "regex": self.regex,
            "priority": self.priority,
            "user_id": self.user_id,
            "permission": self.permission,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            user_id=dictionary["user_id"],
            permission=dictionary["permission"],
        )
