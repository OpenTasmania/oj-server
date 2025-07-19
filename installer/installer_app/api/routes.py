from flask import Blueprint, jsonify, request

from .build import BuildManager
from .deployment import DeploymentManager
from .status import StatusManager

api_bp = Blueprint("api", __name__)
deployment_manager = DeploymentManager()
build_manager = BuildManager()
status_manager = StatusManager()


@api_bp.route("/deploy", methods=["POST"])
def deploy():
    config = request.get_json()
    try:
        result = deployment_manager.deploy(config)
        return jsonify({"success": True, "deployment_id": result.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/deploy/<deployment_id>/status")
def deployment_status(deployment_id):
    status = deployment_manager.get_status(deployment_id)
    return jsonify(status)


@api_bp.route("/build", methods=["POST"])
def build():
    config = request.get_json()
    try:
        result = build_manager.build(config)
        return jsonify({"success": True, "build_id": result.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/system/status")
def system_status():
    status = status_manager.get_system_status()
    return jsonify(status)
