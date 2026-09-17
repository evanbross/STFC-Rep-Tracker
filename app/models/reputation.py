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
