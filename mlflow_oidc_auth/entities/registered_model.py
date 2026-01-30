class RegisteredModelPermission:
    def __init__(self, name, permission, user_id=None, group_id=None, prompt=False):
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
            user_id=dictionary.get("user_id"),
            permission=dictionary["permission"],
            group_id=dictionary.get("group_id"),
            prompt=bool(dictionary.get("prompt", False)),
        )


class RegisteredModelGroupRegexPermission:
    def __init__(
        self,
        id_,
        regex,
        priority,
        group_id,
        permission,
        prompt=False,
    ):
        self._id = id_
        self._regex = regex
        self._priority = priority
        self._group_id = group_id
        self._permission = permission
        self._prompt = prompt

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

    @property
    def prompt(self):
        return self._prompt

    def to_json(self):
        return {
            "id": self.id,
            "regex": self.regex,
            "priority": self.priority,
            "group_id": self.group_id,
            "permission": self.permission,
            "prompt": self.prompt,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            group_id=dictionary["group_id"],
            permission=dictionary["permission"],
            prompt=bool(dictionary.get("prompt", False)),
        )


class RegisteredModelRegexPermission:
    def __init__(
        self,
        id_,
        regex,
        priority,
        user_id,
        permission,
        prompt=False,
    ):
        self._id = id_
        self._regex = regex
        self._priority = priority
        self._user_id = user_id
        self._permission = permission
        self._prompt = prompt

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

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, prompt):
        self._prompt = prompt

    def to_json(self):
        return {
            "id": self.id,
            "regex": self.regex,
            "priority": self.priority,
            "user_id": self.user_id,
            "permission": self.permission,
            "prompt": self.prompt,
        }

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            user_id=dictionary["user_id"],
            permission=dictionary["permission"],
            prompt=bool(dictionary.get("prompt", False)),
        )

