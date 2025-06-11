from unittest.mock import ANY, MagicMock, call

import pytest

from setup.config_models import (
    AppSettings,
    OsrmDataSettings,
    OsrmServiceSettings,
)
from setup.configure.osrm_configurator import (
    activate_osrm_routed_service,
    configure_osrm_services,
    create_osrm_routed_service_file,
)

TEST_SYSTEMD_TEMPLATE = """
[Unit]
Description=OSRM-routed for {region_name}

[Service]
ExecStart={container_runtime_command} run --rm -p {host_port_for_region}:{container_osrm_port} {osrm_image_tag} osrm-routed --algorithm mld {extra_osrm_routed_args} /data_processing/{osrm_filename_in_container}
"""


@pytest.fixture
def mock_app_settings(tmp_path) -> AppSettings:
    """Provides a mock AppSettings object for tests."""
    processed_dir = tmp_path / "osrm_processed"
    processed_dir.mkdir()
    return AppSettings(
        osrm_data=OsrmDataSettings(
            base_dir=tmp_path / "osrm_data",
            processed_dir=processed_dir,
            max_table_size_routed=1000,
        ),
        osrm_service=OsrmServiceSettings(
            image_tag="osrm/osrm-backend:latest",
            car_profile_default_host_port=5000,
            container_osrm_port=5000,
            region_port_map={},
            systemd_template=TEST_SYSTEMD_TEMPLATE,
            extra_routed_args="--max-viaroute-size 500",
        ),
        container_runtime_command="podman",
        symbols={
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "!",
            "step": "➡️",
        },
    )


class TestConfigureOsrmServices:
    def test_configure_success(self, monkeypatch, mock_app_settings):
        """Test successful configuration of multiple regions."""
        mock_create = MagicMock()
        mock_activate = MagicMock()
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.create_osrm_routed_service_file",
            mock_create,
        )
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.activate_osrm_routed_service",
            mock_activate,
        )

        (mock_app_settings.osrm_data.processed_dir / "region_A").mkdir()
        (mock_app_settings.osrm_data.processed_dir / "region_B").mkdir()

        result = configure_osrm_services(mock_app_settings)

        assert result is True
        assert mock_create.call_count == 2
        assert mock_activate.call_count == 2

    def test_configure_one_fails(self, monkeypatch, mock_app_settings):
        """Test that configuration continues if one region fails."""
        mock_create = MagicMock(
            side_effect=[None, FileNotFoundError("mock error")]
        )
        mock_activate = MagicMock()
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.create_osrm_routed_service_file",
            mock_create,
        )
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.activate_osrm_routed_service",
            mock_activate,
        )

        (mock_app_settings.osrm_data.processed_dir / "region_A").mkdir()
        (mock_app_settings.osrm_data.processed_dir / "region_B").mkdir()

        result = configure_osrm_services(mock_app_settings)

        assert result is False
        assert mock_create.call_count == 2
        mock_activate.assert_called_once()


class TestCreateOsrmServiceFile:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        mock_elevated = MagicMock()
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.run_elevated_command",
            mock_elevated,
        )
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.get_current_script_hash",
            MagicMock(return_value="testhash"),
        )
        return mock_elevated

    def test_create_service_auto_port(self, setup_mocks, mock_app_settings):
        """Test creating a service file with an auto-assigned port."""
        mock_elevated = setup_mocks
        region_name = "Tasmania"

        region_dir = mock_app_settings.osrm_data.processed_dir / region_name
        region_dir.mkdir()
        (region_dir / f"{region_name}.osrm").touch()

        create_osrm_routed_service_file(region_name, mock_app_settings)

        assert (
            mock_app_settings.osrm_service.region_port_map[region_name]
            == 5000
        )
        written_content = mock_elevated.call_args.kwargs["cmd_input"]
        assert "Description=OSRM-routed for Tasmania" in written_content
        assert "ExecStart=podman run --rm -p 5000:5000" in written_content

    def test_fail_on_missing_osrm_data(self, mock_app_settings):
        """Test that service file creation fails if the .osrm file is missing."""
        region_name = "Tasmania"
        (mock_app_settings.osrm_data.processed_dir / region_name).mkdir()

        with pytest.raises(FileNotFoundError):
            create_osrm_routed_service_file(region_name, mock_app_settings)


class TestActivateOsrmService:
    def test_activation_commands(self, monkeypatch, mock_app_settings):
        """Test that the correct systemctl commands are called."""
        mock_reload = MagicMock()
        mock_elevated = MagicMock()
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.systemd_reload", mock_reload
        )
        monkeypatch.setattr(
            "setup.configure.osrm_configurator.run_elevated_command",
            mock_elevated,
        )

        region_name = "Tasmania"
        service_name = f"osrm-routed-{region_name}.service"
        activate_osrm_routed_service(region_name, mock_app_settings)

        mock_reload.assert_called_once()

        expected_calls = [
            call(
                ["systemctl", "enable", service_name],
                mock_app_settings,
                current_logger=ANY,
            ),
            call(
                ["systemctl", "restart", service_name],
                mock_app_settings,
                current_logger=ANY,
            ),
            call(
                ["systemctl", "status", service_name, "--no-pager", "-l"],
                mock_app_settings,
                current_logger=ANY,
                check=True,
            ),
        ]
        mock_elevated.assert_has_calls(expected_calls)
