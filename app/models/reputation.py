# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
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
