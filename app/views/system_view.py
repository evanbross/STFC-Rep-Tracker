# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from flask import Blueprint, Response, redirect

system_bp = Blueprint("system", __name__)


@system_bp.route("/swagger", methods=["GET"])
def swagger_redirect() -> Response:
    return redirect("/apidocs")
