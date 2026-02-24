from app.models.stat_entry import StatEntry
from app.models.faction_type import FactionType, FactionTypes
from app.models.faction_status import FactionStatus


class Faction:
    def __init__(self, faction_type, on_chart=0, stat_entries=None, status=None):
        self.faction_type = faction_type
        self.on_chart = on_chart
        self.stat_entries = stat_entries if stat_entries is not None else []
        self.status = status if status is not None else FactionStatus()
