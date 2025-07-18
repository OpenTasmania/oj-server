from flask import Flask, render_template, request

from .utils.builders.amd64 import create_debian_installer_amd64
from .utils.builders.rpi64 import create_debian_installer_rpi64
from .utils.common import create_debian_package
from .utils.kubernetes_tools import deploy, destroy, get_kubectl_command
from .utils.plugin_manager import PluginManager


def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
    )

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/deploy", methods=["GET", "POST"])
    def deploy_route():
        if request.method == "POST":
            env = request.form.get("env", "local")
            images = request.form.getlist("images")
            overwrite = request.form.get("overwrite") == "on"
            production = request.form.get("production") == "on"
            plugin_manager = PluginManager()
            kubectl_cmd = get_kubectl_command()
            deploy(
                env,
                kubectl_cmd,
                plugin_manager,
                images=images,
                overwrite=overwrite,
                production=production,
            )
            return "Deploying..."
        return render_template("deploy.html")

    @app.route("/destroy", methods=["GET", "POST"])
    def destroy_route():
        if request.method == "POST":
            env = request.form.get("env", "local")
            images = request.form.getlist("images")
            plugin_manager = PluginManager()
            kubectl_cmd = get_kubectl_command()
            destroy(
                env,
                kubectl_cmd,
                plugin_manager,
                images=images,
            )
            return "Destroying..."
        return render_template("destroy.html")

    @app.route("/build", methods=["GET", "POST"])
    def build_route():
        if request.method == "POST":
            build_type = request.form.get("build_type")
            if build_type == "deb":
                create_debian_package()
                return "Building debian package..."
            elif build_type == "amd64":
                create_debian_installer_amd64()
                return "Building amd64 debian installer..."
            elif build_type == "rpi64":
                rpi_model = int(request.form.get("rpi_model", 4))
                create_debian_installer_rpi64(rpi_model)
                return (
                    f"Building rpi64 debian installer for RPi {rpi_model}..."
                )
        return render_template("build.html")

    return app
