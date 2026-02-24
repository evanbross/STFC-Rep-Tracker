

class FactionType:
    def __init__(self, id, code, name, color=None, reputation_table_name=None):
        self.id = id
        self.code = code
        self.name = name
        self.color = color
        self.reputation_table_name = reputation_table_name

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "color": self.color,
            "reputation_table_name": self.reputation_table_name
        }


class FactionTypes:
    entries = []
