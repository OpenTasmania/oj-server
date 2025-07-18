# -*- coding: utf-8 -*-
from flask import Flask, render_template, request

from .utils.builders.amd64 import create_debian_installer_amd64
from .utils.builders.rpi64 import create_debian_installer_rpi64
from .utils.common import create_debian_package
from .utils.kubernetes_tools import deploy, destroy, get_kubectl_command
from .utils.plugin_manager import PluginManager


def create_app():
    """
    Creates and configures the Flask application.

    The application provides multiple routes to handle deployment, destruction,
    and building of various resources. Each route supports HTTP GET and POST
    methods, enabling different operations depending on the user's input.

    Returns:
        Flask application instance.

    Routes:
        - "/": Renders the index page.
        - "/deploy": Handles deployment-related operations based on user inputs.
        - "/destroy": Handles destruction-related operations based on user inputs.
        - "/build": Handles build operations for various build types, such as
          debian packages and installers.

    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
    )

    @app.route("/")
    def index():
        """
        A route handler for the root URL of the application. This function serves the main page of the application.

        Returns:
            str: The rendered HTML for the index page.
        """
        return render_template("index.html")

    @app.route("/deploy", methods=["GET", "POST"])
    def deploy_route():
        """
        Handles deployment actions based on HTTP GET or POST methods for the /deploy route.

        Summary:
        This function handles HTTP GET and POST requests to facilitate the deployment process.
        For POST requests, it retrieves form data necessary for deployment, including environment
        information, images list, overwrite flag, and production flag. It initializes a plugin
        manager and Kubernetes command utility before invoking the deployment process. On successful
        processing, it returns a response indicating the start of the deployment. For GET requests,
        it renders the HTML template for the deployment interface.

        Parameters:
            None

        Returns:
            str: For POST requests, it returns a message indicating that deployment has started.
            Response: For GET requests, it renders and returns the deployment HTML template.

        Raises:
            None
        """
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
        """
        Handle the destroy route for the web application.

        Summary:
        This function handles the "/destroy" route, supporting both GET and POST
        methods. When accessed via a POST request, it retrieves form data to
        destroy specific resources. For GET requests, it renders the "destroy.html"
        template.

        Args:
            None. This function uses request contexts to get form data or
            render templates.

        Returns:
            str: A confirmation message when resources are being destroyed (for POST
            requests).
            Response: The rendered HTML response for the "destroy.html" template
            (for GET requests).
        """
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
        """
        Handles the /build route, providing both GET and POST request support. This route
        is used for building software packages based on user-provided input. On a POST
        request, it processes the form data to determine the type of build to be executed
        and initiates the appropriate build process. For GET requests, it renders the
        build template.

        Raises:
            KeyError: Raised if an expected form field is missing during a POST request
            ValueError: Raised if an invalid value for 'rpi_model' is provided in
                the form data during a POST request

        Args:
            None

        Returns:
            str: A response message indicating the outcome of the build operation
                during a POST request
            Response: A rendered HTML template during a GET request
        """
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
