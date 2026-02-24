

class FactionType:
    def __init__(self, id, code, name, color=None):
        self.id = id
        self.code = code
        self.name = name
        self.color = color

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "color": self.color
        }


class FactionTypes:
    entries = []
