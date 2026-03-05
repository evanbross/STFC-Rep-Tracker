import logging

from flask import Blueprint, jsonify, current_app

from app.database.reputations_dao import ReputationsDAO

logger = logging.getLogger(__name__)

reputations_bp = Blueprint("reputations", __name__)

@reputations_bp.route("", methods=["GET"])
def get_reputations():
    """Get list of all fkr_reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("fkr_reputations")
    if not dao:
        return jsonify({"error": "FKR reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/augment", methods=["GET"])
def get_augment_reputations():
    """Get list of all augment reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("augment_reputations")
    if not dao:
        return jsonify({"error": "Augment reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/rogue", methods=["GET"])
def get_rogue_reputations():
    """Get list of all rogue reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("rogue_reputations")
    if not dao:
        return jsonify({"error": "Rogue reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/bajoran", methods=["GET"])
def get_bajoran_reputations():
    """Get list of all bajoran reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("bajoran_reputations")
    if not dao:
        return jsonify({"error": "Bajoran reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/terran", methods=["GET"])
def get_terran_reputations():
    """Get list of all terran reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("terran_reputations")
    if not dao:
        return jsonify({"error": "Terran reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/dti", methods=["GET"])
def get_dti_reputations():
    """Get list of all dti reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("dti_reputations")
    if not dao:
        return jsonify({"error": "DTI reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/section31", methods=["GET"])
def get_section31_reputations():
    """Get list of all section 31 reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("section31_reputations")
    if not dao:
        return jsonify({"error": "Section 31 reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/ex-borg", methods=["GET"])
def get_ex_borg_reputations():
    """Get list of all ex-borg reputations"""
    dao = ReputationsDAO.get_dao_by_faction_name("ex_borg_reputations")
    if not dao:
        return jsonify({"error": "Ex-Borg reputation DAO not found"}), 404
    reputations = dao.get_all()
    return jsonify(reputations)


@reputations_bp.route("/all", methods=["GET"])
def get_all_reputations_grouped():
    """
    Get all reputations grouped by their reputation table
    ---
    tags:
      - Reputations
    responses:
      200:
        description: All reputations grouped by table
    """
    db = current_app.config["DATABASE"]
    daos = ReputationsDAO.get_all_dao_by_class_name()
    result = []
    for dao_name, dao in daos.items():
        logger.info(f"Fetching reputations for {dao_name}")
        try:
            reps = dao.get_all(db)
            title = f"{dao.get_table_name()} Reputation Tiers"
            result.append(
                {
                    "title": title,
                    "data": reps,
                }
            )
        except Exception as e:
            logger.error(f"Error fetching reputations for {dao_name}: {e}")

    return jsonify(result)


@reputations_bp.route("/by-table/<table_name>", methods=["GET"])
def get_reputations_by_table(table_name):
    """
    Get list of all reputations from a specific reputation table
    ---
    tags:
      - Reputations
    parameters:
      - name: table_name
        in: path
        type: string
        required: true
        description: Name of the reputation table
    responses:
      200:
        description: A list of reputations
      400:
        description: Invalid table name
    """
    db = current_app.config["DATABASE"]
    try:
        dao = ReputationsDAO.get_dao_by_faction_name(table_name)
        if not dao:
            # Fallback for generic DAO if name isn't registered but it is a known table
            dao = ReputationsDAO(db, table_name)
        reputations = dao.get_all(db)
        return jsonify(reputations)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
