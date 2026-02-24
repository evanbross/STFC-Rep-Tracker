from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from app.database.database import Database
from config import get_config
import os

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config.from_object(get_config())
CORS(app, origins=app.config['CORS_ORIGINS'])
db = Database(app.config['DATABASE_PATH'])


@app.route('/')
def index():
    """Serve the index.html file"""
    return render_template('index.html')


@app.route('/faction-types.html')
def faction_types_page():
    """Serve the faction-types.html file"""
    return render_template('faction-types.html')


@app.route('/factions.html')
def factions_page():
    """Serve the factions.html file"""
    return render_template('factions.html')


@app.route('/reputations.html')
def reputations_page():
    """Serve the reputations.html file"""
    return render_template('reputations.html')


@app.route('/api/faction-types', methods=['GET'])
def get_faction_types():
    """Get list of all faction types"""
    faction_types = db.get_all_faction_types()
    return jsonify(faction_types)


@app.route('/api/faction-types', methods=['POST'])
def add_faction_type():
    """Add a new faction type"""
    data = request.json
    code = data.get('code')
    name = data.get('name')
    color = data.get('color')
    reputation_table_name = data.get('reputation_table_name')

    if not code or not name:
        return jsonify({'error': 'Missing code or name'}), 400

    try:
        faction_type = db.add_faction_type(code, name, color, reputation_table_name)
        return jsonify(faction_type), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/faction-types/<int:id>', methods=['PUT'])
def update_faction_type(id):
    """Update an existing faction type"""
    data = request.json
    code = data.get('code')
    name = data.get('name')
    color = data.get('color')
    reputation_table_name = data.get('reputation_table_name')

    if not code or not name:
        return jsonify({'error': 'Missing code or name'}), 400

    try:
        faction_type = db.update_faction_type(id, code, name, color, reputation_table_name)
        return jsonify(faction_type), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/factions', methods=['GET'])
def get_factions():
    """Get list of all factions"""
    factions = db.get_all_factions()
    return jsonify(factions)


@app.route('/api/factions', methods=['POST'])
def add_faction():
    """Add a new faction"""
    data = request.json
    name = data.get('name')
    faction_type_id = data.get('faction_type_id')
    on_column = data.get('on_column', 0)

    if not name or not faction_type_id:
        return jsonify({'error': 'Missing name or faction_type_id'}), 400

    try:
        faction = db.add_faction(name, int(faction_type_id), int(on_column))
        return jsonify(faction), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/factions/<int:id>', methods=['PUT'])
def update_faction(id):
    """Update an existing faction"""
    data = request.json
    name = data.get('name')
    faction_type_id = data.get('faction_type_id')
    on_column = data.get('on_column', 0)

    if not name or not faction_type_id:
        return jsonify({'error': 'Missing name or faction_type_id'}), 400

    try:
        faction = db.update_faction(id, name, int(faction_type_id), int(on_column))
        return jsonify(faction), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/factions/summary', methods=['GET'])
def get_faction_summary():
    """Get summary data for all factions"""
    summary = db.get_faction_summary()
    return jsonify(summary)


@app.route('/api/entries', methods=['GET'])
def get_all_entries():
    """Get all stat entries for all factions"""
    entries = db.get_all_factions_with_entries()
    return jsonify(entries)


@app.route('/api/entries/<faction_name>', methods=['GET'])
def get_faction_entries(faction_name):
    """Get stat entries for a specific faction"""
    entries = db.get_faction_entries(faction_name)
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
        entry = db.add_stat_entry(faction_name, int(value))
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reputations', methods=['GET'])
def get_reputations():
    """Get list of all fkr_reputations"""
    reputations = db.get_all_reputations()
    return jsonify(reputations)


@app.route('/api/augment-reputations', methods=['GET'])
def get_augment_reputations():
    """Get list of all augment reputations"""
    reputations = db.get_all_augment_reputations()
    return jsonify(reputations)


@app.route('/api/rogue-reputations', methods=['GET'])
def get_rogue_reputations():
    """Get list of all rogue reputations"""
    reputations = db.get_all_rogue_reputations()
    return jsonify(reputations)


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], port=5000)
