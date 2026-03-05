import logging
import logging.config
import os

import yaml
from flasgger import Swagger
from flask import Flask, send_from_directory
from flask_cors import CORS

from app.database.database import Database
from app.views.capture_screen_view import capture_bp
from app.views.factions_view import factions_bp
from app.views.reputations_view import reputations_bp
from app.views.status_entries_view import status_entries_bp
from app.views.system_view import system_bp
from config import get_config

with open("logging.yaml") as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder="frontend/dist",
    static_folder="frontend/dist",
    static_url_path="/static",
)
app.config.from_object(get_config())
CORS(app, origins=app.config["CORS_ORIGINS"])
swagger = Swagger(app)
db = Database(app.config["DATABASE_PATH"])
app.config["DATABASE"] = db
app.register_blueprint(capture_bp, url_prefix="/api/capture-screen")
app.register_blueprint(status_entries_bp, url_prefix="/api/status_entries")
app.register_blueprint(factions_bp, url_prefix="/api/factions")
app.register_blueprint(reputations_bp, url_prefix="/api/reputations")
app.register_blueprint(system_bp, url_prefix="/api/system")

# @app.route("/api/factions", methods=["GET"])
# def get_factions():
#     result = db.get_factions_dao().get_all_factions()
#     return jsonify(result)
#
#
# @app.route("/api/factions", methods=["POST"])
# def add_faction():
#     """
#     Add a new faction
#     ---
#     tags:
#       - Factions
#     parameters:
#       - name: body
#         in: body
#         required: true
#         schema:
# type: object
#           required:
#             - name
#             - code
#           properties:
#             name:
# type: string
#             code:
# type: string
#             color:
# type: string
#             reputation_table_name:
# type: string
#             on_chart:
# type: integer
#               default: 0
#             display_order:
# type: integer
#     responses:
#       201:
#         description: Faction created successfully
#       400:
#         description: Missing required fields or faction already exists
#     """
#     data = request.json
#     name = data.get("name")
#     code = data.get("code")
#     color = data.get("color")
#     reputation_table_name = data.get("reputation_table_name")
#     on_chart = data.get("on_chart", 0)
#     display_order = data.get("display_order")
#
#     if not name or not code:
#         return jsonify({"error": "Missing name or code"}), 400
#
#     try:
#         result = db.factions.add_faction(
#             name,
#             code,
#             color,
#             reputation_table_name,
#             int(on_chart),
#             int(display_order) if display_order is not None else None,
#         )
#         return jsonify(result), 201
#     except ValueError as e:
#         return jsonify({"error": str(e)}), 400
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
#
#
# @app.route("/api/factions/<int:id>", methods=["PUT"])
# def update_faction(id):
#     """
#     Update an existing faction
#     ---
#     tags:
#       - Factions
#     parameters:
#       - name: id
#         in: path
# type: integer
#         required: true
#       - name: body
#         in: body
#         required: true
#         schema:
# type: object
#           required:
#             - name
#             - code
#           properties:
#             name:
# type: string
#             code:
# type: string
#             color:
# type: string
#             reputation_table_name:
# type: string
#             on_chart:
# type: integer
#             display_order:
# type: integer
#     responses:
#       200:
#         description: Faction updated successfully
#       404:
#         description: Faction not found
#     """
#     data = request.json
#     name = data.get("name")
#     code = data.get("code")
#     color = data.get("color")
#     reputation_table_name = data.get("reputation_table_name")
#     on_chart = data.get("on_chart", 0)
#     display_order = data.get("display_order")
#
#     if not name or not code:
#         return jsonify({"error": "Missing name or code"}), 400
#
#     try:
#         result = db.factions.update_faction(
#             id,
#             name,
#             code,
#             color,
#             reputation_table_name,
#             int(on_chart),
#             int(display_order) if display_order is not None else None,
#         )
#         return jsonify(result), 200
#     except ValueError as e:
#         return jsonify({"error": str(e)}), 404
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# @app.route("/api/reputations", methods=["GET"])
# def get_reputations():
#     """Get list of all fkr_reputations"""
#     dao = ReputationsDAO.get_dao_by_faction_name("fkr_reputations")
#     if not dao:
#         return jsonify({"error": "FKR reputation DAO not found"}), 404
#     reputations = dao.get_all()
#     return jsonify(reputations)
#
#
# @app.route("/api/reputations/all", methods=["GET"])
# def get_all_reputations_grouped():
#     """
#     Get all reputations grouped by their reputation table
#     ---
#     tags:
#       - Reputations
#     responses:
#       200:
#         description: All reputations grouped by table
#     """
#     daos = ReputationsDAO.get_all_dao_by_class_name()
#     # for dao_name in daos.keys():
#     #     dao = daos[dao_name]
#     #     try:
#     #         reps = dao.get_all(db)
#     #         yield {"table_name": dao.table_name, "data": reps}
#     #     except Exception as e:
#     #         logger.error(f"Error fetching reputations for {dao.table_name}: {e}")
#
#     # factions = db.factions.get_all_factions()
#     # groups = {}
#     # for f in factions:
#     #     table_name = f.get("reputation_table_name")
#     #     if not table_name:
#     #         continue
#     #     if table_name not in groups:
#     #         groups[table_name] = {
#     #             "table_name": table_name,
#     #             "factions": [],
#     #             "display_order": (
#     #                 f.get("display_order")
#     #                 if f.get("display_order") is not None
#     #                 else 999
#     #             ),
#     #         }
#     #     groups[table_name]["factions"].append(f["name"])
#     #     if (
#     #         f.get("display_order") is not None
#     #         and f["display_order"] < groups[table_name]["display_order"]
#     #     ):
#     #         groups[table_name]["display_order"] = f["display_order"]
#
#     result = []
#     for dao_name, dao in daos.items():
#         logger.info(f"Fetching reputations for {dao_name}")
#         try:
#             reps = dao.get_all(db)
#
#             title = f"{dao.get_table_name()} Reputation Tiers"
#
#             result.append(
#                 {
#                     "title": title,
#                     "data": reps,
#                 }
#             )
#         except Exception as e:
#             logger.error(f"Error fetching reputations for {dao_name}: {e}")
#
#     return jsonify(result)
#
#
# @app.route("/api/reputations/by-table/<table_name>", methods=["GET"])
# def get_reputations_by_table(table_name):
#     """
#     Get list of all reputations from a specific reputation table
#     ---
#     tags:
#       - Reputations
#     parameters:
#       - name: table_name
#         in: path
# type: string
#         required: true
#         description: Name of the reputation table
#     responses:
#       200:
#         description: A list of reputations
#       400:
#         description: Invalid table name
#     """
#     try:
#         dao = ReputationsDAO.get_dao_by_faction_name(table_name)
#         if not dao:
#             # Fallback for generic DAO if name isn't registered but it is a known table
#             dao = ReputationsDAO(db, table_name)
#         reputations = dao.get_all(db)
#         return jsonify(reputations)
#     except ValueError as e:
#         return jsonify({"error": str(e)}), 400
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# @app.route("/swagger")
# def swagger_redirect():
#     """Redirect /swagger to the interactive API docs"""
#     return redirect("/apidocs/")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve the React app's index.html for all frontend routes"""
    # If the path starts with 'api/', Flask will use the API routes instead of this catch-all
    # If the path is a file that exists in the static folder, Flask will serve it
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=5000)
