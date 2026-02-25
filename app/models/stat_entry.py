class StatEntry:
    def __init__(self, timestamp, value, _value_delta, faction_id=None):
        self.timestamp = timestamp
        self.value = value
        self._value_delta = _value_delta
        self.faction_id = faction_id
