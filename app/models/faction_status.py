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
class FactionStatus:
    def __init__(self, minutes=0.0, delta=0, value_change=0, raw_change_per_minute=0.0, avg_change_per_minute=0.0, minutes_to_goal=0.0):
        self.minutes = minutes
        self.delta = delta
        self.value_change = value_change
        self.raw_change_per_minute = raw_change_per_minute
        self.avg_change_per_minute = avg_change_per_minute
        self.minutes_to_goal = minutes_to_goal

    def to_dict(self):
        return {
            "minutes": self.minutes,
            "delta": self.delta,
            "value_change": self.value_change,
            "raw_change_per_minute": self.raw_change_per_minute,
            "avg_change_per_minute": self.avg_change_per_minute,
            "minutes_to_goal": self.minutes_to_goal
        }
