from flask import Blueprint, send_from_directory

static_bp = Blueprint('static_routes', __name__)

@static_bp.route('/tikzpics/<filename>')
def tikzpics(filename):
    """
    Serve a file from the 'tikzpics' directory.

    This route handles requests to the '/tikzpics/<filename>' endpoint and serves
    the specified file from the 'tikzpics' directory.

    Args:
        filename (str): The name of the file to be served.

    Returns:
        Response: A Flask response object that contains the requested file.

    Raises:
        werkzeug.exceptions.NotFound: If the file does not exist in the 'tikzpics' directory.
    """
    return send_from_directory('tikzpics', filename)


