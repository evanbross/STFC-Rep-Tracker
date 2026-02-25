from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
from app.database import fkr_reputations_dao, rogue_reputations_dao, augment_reputations_dao, bajoran_reputations_dao, terran_reputations_dao, dti_reputations_dao, section31_reputations_dao, ex_borg_reputations_dao, factions_dao, stat_entries_dao
from app.database.database import Database
from config import get_config
import os

app = Flask(__name__, template_folder='frontend/dist', static_folder='frontend/dist', static_url_path='/')
app.config.from_object(get_config())
CORS(app, origins=app.config['CORS_ORIGINS'])
db = Database(app.config['DATABASE_PATH'])


@app.route('/reputations.html')
def redirect_reputations():
    """Redirect legacy reputations.html to the new React route"""
    return redirect('/reputations', code=301)


@app.route('/factions.html')
def redirect_factions():
    """Redirect legacy factions.html to the new React route"""
    return redirect('/factions', code=301)


@app.route('/index.html')
def redirect_index():
    """Redirect legacy index.html to the new React route"""
    return redirect('/', code=301)


@app.route('/faction-types.html')
def redirect_faction_types():
    """Redirect legacy faction-types.html to the new React route"""
    return redirect('/factions', code=301)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """Serve the React app's index.html for all frontend routes"""
    # If the path starts with 'api/', Flask will use the API routes instead of this catch-all
    # If the path is a file that exists in the static folder, Flask will serve it
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return app.send_static_file(path)
    return render_template('index.html')


@app.route('/api/factions', methods=['GET'])
def get_factions():
    """Get list of all factions"""
    result = factions_dao.get_all_factions(db)
    return jsonify(result)


@app.route('/api/factions', methods=['POST'])
def add_faction():
    """Add a new faction"""
    data = request.json
    name = data.get('name')
    code = data.get('code')
    color = data.get('color')
    reputation_table_name = data.get('reputation_table_name')
    on_chart = data.get('on_chart', 0)
    display_order = data.get('display_order')
    on_column = data.get('on_column', 0)

    if not name or not code:
        return jsonify({'error': 'Missing name or code'}), 400

    try:
        result = factions_dao.add_faction(db, name, code, color, reputation_table_name, int(on_chart), 
                                         int(display_order) if display_order is not None else None,
                                         int(on_column))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/factions/<int:id>', methods=['PUT'])
def update_faction(id):
    """Update an existing faction"""
    data = request.json
    name = data.get('name')
    code = data.get('code')
    color = data.get('color')
    reputation_table_name = data.get('reputation_table_name')
    on_chart = data.get('on_chart', 0)
    display_order = data.get('display_order')
    on_column = data.get('on_column', 0)

    if not name or not code:
        return jsonify({'error': 'Missing name or code'}), 400

    try:
        result = factions_dao.update_faction(db, id, name, code, color, reputation_table_name, int(on_chart),
                                            int(display_order) if display_order is not None else None,
                                            int(on_column))
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/factions/summary', methods=['GET'])
def get_faction_summary():
    """Get summary data for all factions"""
    summary = factions_dao.get_faction_summary(db)
    return jsonify(summary)


@app.route('/api/entries', methods=['GET'])
def get_all_entries():
    """Get all stat entries for all factions"""
    entries = stat_entries_dao.get_all_factions_with_entries(db)
    return jsonify(entries)


@app.route('/api/entries/<faction_name>', methods=['GET'])
def get_faction_entries(faction_name):
    """Get stat entries for a specific faction"""
    entries = stat_entries_dao.get_faction_entries(db, faction_name)
    return jsonify(entries)


@app.route('/api/entries', methods=['POST'])
def add_entry():
    """Add a new stat entry"""
    data = request.json
    faction_name = data.get('faction')
    value = data.get('value')

    if not faction_name or value is None:
        return jsonify({'error': 'Missing faction or value'}), 400

    try:
        entry = stat_entries_dao.add_stat_entry(db, faction_name, int(value))
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reputations', methods=['GET'])
def get_reputations():
    """Get list of all fkr_reputations"""
    reputations = fkr_reputations_dao.get_all_reputations(db)
    return jsonify(reputations)


@app.route('/api/augment-reputations', methods=['GET'])
def get_augment_reputations():
    """Get list of all augment reputations"""
    reputations = augment_reputations_dao.get_all_augment_reputations(db)
    return jsonify(reputations)


@app.route('/api/rogue-reputations', methods=['GET'])
def get_rogue_reputations():
    """Get list of all rogue reputations"""
    reputations = rogue_reputations_dao.get_all_rogue_reputations(db)
    return jsonify(reputations)


@app.route('/api/bajoran-reputations', methods=['GET'])
def get_bajoran_reputations():
    """Get list of all bajoran reputations"""
    reputations = bajoran_reputations_dao.get_all_bajoran_reputations(db)
    return jsonify(reputations)


@app.route('/api/terran-reputations', methods=['GET'])
def get_terran_reputations():
    """Get list of all terran reputations"""
    reputations = terran_reputations_dao.get_all_terran_reputations(db)
    return jsonify(reputations)


@app.route('/api/dti-reputations', methods=['GET'])
def get_dti_reputations():
    """Get list of all dti reputations"""
    reputations = dti_reputations_dao.get_all_dti_reputations(db)
    return jsonify(reputations)


@app.route('/api/section31-reputations', methods=['GET'])
def get_section31_reputations():
    """Get list of all section 31 reputations"""
    reputations = section31_reputations_dao.get_all_section31_reputations(db)
    return jsonify(reputations)


@app.route('/api/ex-borg-reputations', methods=['GET'])
def get_ex_borg_reputations():
    """Get list of all ex-borg reputations"""
    reputations = ex_borg_reputations_dao.get_all_ex_borg_reputations(db)
    return jsonify(reputations)


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], port=5000)
