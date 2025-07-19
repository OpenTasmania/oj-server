from ..utils.kubernetes_tools import deploy, get_kubectl_command
from ..utils.plugin_manager import PluginManager


class DeploymentManager:
    def deploy(self, config):
        env = config.get("env", "local")
        images = config.get("images", [])
        overwrite = config.get("overwrite", False)
        production = config.get("production", False)
        plugin_manager = PluginManager()
        kubectl_cmd = get_kubectl_command()
        return deploy(
            env,
            kubectl_cmd,
            plugin_manager,
            images=images,
            overwrite=overwrite,
            production=production,
        )

    def get_status(self, deployment_id):
        # This is a placeholder for the actual status logic
        return {"status": "deploying", "progress": 50}
