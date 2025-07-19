from ..utils.builders.amd64 import create_debian_installer_amd64
from ..utils.builders.rpi64 import create_debian_installer_rpi64
from ..utils.common import create_debian_package


class BuildManager:
    def build(self, config):
        build_type = config.get("build_type")
        if build_type == "deb":
            return create_debian_package()
        elif build_type == "amd64":
            return create_debian_installer_amd64()
        elif build_type == "rpi64":
            rpi_model = int(config.get("rpi_model", 4))
            return create_debian_installer_rpi64(rpi_model)
