# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
class StatEntry:
    def __init__(self, timestamp, value, _value_delta, faction_code=None):
        self.timestamp = timestamp
        self.value = value
        self.faction_code = faction_code
