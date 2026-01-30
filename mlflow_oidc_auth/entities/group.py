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
