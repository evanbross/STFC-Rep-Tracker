from app.models.stat_entry import StatEntry
from app.models.faction_status import FactionStatus


class Faction:
    def __init__(self, id, name, code, color=None, reputation_table_name=None, on_chart=0, display_order=0, stat_entries=None, status=None):
        self.id = id
        self.name = name
        self.code = code
        self.color = color
        self.reputation_table_name = reputation_table_name
        self.on_chart = on_chart
        self.display_order = display_order
        self.stat_entries = stat_entries if stat_entries is not None else []
        self.status = status if status is not None else FactionStatus()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "color": self.color,
            "reputation_table_name": self.reputation_table_name,
            "on_chart": self.on_chart,
            "display_order": self.display_order
        }
