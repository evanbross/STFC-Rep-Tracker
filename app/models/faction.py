# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from app.models.faction_status import FactionStatus


class Faction:
    def __init__(
        self,
        id,
        name,
        code,
        color=None,
        reputation_table_name=None,
        on_chart=0,
        display_order=0,
        reputation_dao_name=None,
        status_entries=None,
        status=None,
    ):
        self.id = id
        self.name = name
        self.code = code
        self.color = color
        self.reputation_table_name = reputation_table_name
        self.reputation_dao_name = reputation_dao_name
        self.on_chart = on_chart
        self.display_order = display_order
        self.status_entries = status_entries if status_entries is not None else []
        self.status = status if status is not None else FactionStatus()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "color": self.color,
            "reputation_table_name": self.reputation_table_name,
            "reputation_dao_name": self.reputation_dao_name,
            "on_chart": self.on_chart,
            "display_order": self.display_order,
        }
