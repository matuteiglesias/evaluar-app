from flask import Blueprint, send_from_directory

static_bp = Blueprint('static_routes', __name__)

@static_bp.route('/tikzpics/<filename>')
def tikzpics(filename):
    return send_from_directory('tikzpics', filename)


