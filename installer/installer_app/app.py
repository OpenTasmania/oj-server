# app.py
from flask import Flask, render_template
from flask_cors import CORS

from .api.routes import api_bp


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # Enable CORS for Vue.js development
    CORS(app, origins=["http://localhost:5173"])  # Vite dev server

    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    @app.route("/")
    @app.route("/<path:path>")
    def index(path=""):
        """Serve the Vue.js SPA"""
        return render_template("index.html")

    return app
