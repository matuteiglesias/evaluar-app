from flask import Blueprint, render_template, session, jsonify, redirect, url_for

core_bp = Blueprint('core', __name__)


@core_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('core.index'))

@core_bp.route('/health')
def health():
    return jsonify({"status": "up"}), 200

@core_bp.route('/')
def index():
    if 'user' in session:
        return render_template('index.html', user=session['user'])
    return render_template('login.html')
