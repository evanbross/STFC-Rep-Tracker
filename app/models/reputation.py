
class Reputation:
    def __init__(self, id=None, name=None, low_limit=None, high_limit=None):
        self.id = id
        self.name = name
        self.low_limit = low_limit
        self.high_limit = high_limit

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "low_limit": self.low_limit,
            "high_limit": self.high_limit
        }
