# tests/test_osrm_data_processor.py
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from processors.data_handling.osrm_data_processor import (
    build_osrm_graphs_for_region,
    extract_regional_pbfs_with_osmium,
)
from setup.config_models import (
    AppSettings,
    OsrmDataSettings,
    OsrmServiceSettings,
)


@pytest.fixture
def mock_app_settings(tmp_path) -> AppSettings:
    """Provides a mock AppSettings object for tests."""
    return AppSettings(
        osrm_data=OsrmDataSettings(
            base_dir=tmp_path / "osrm_data",
            processed_dir=tmp_path / "osrm_processed",
        ),
        osrm_service=OsrmServiceSettings(
            image_tag="osrm/osrm-backend:latest"
        ),
        container_runtime_command="podman",
        symbols={
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "!",
            "step": "➡️",
            "debug": "🐛",
            "critical": "🔥",
        },
    )


class TestExtractRegionalPbfs:
    """Tests for the extract_regional_pbfs_with_osmium function."""

    def test_successful_extraction(
        self, monkeypatch, mock_app_settings, tmp_path
    ):
        """Test successful PBF extraction for a single region."""
        mock_run_command = MagicMock()
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor.run_command",
            mock_run_command,
        )

        # Setup file system
        base_pbf_path = tmp_path / "base.osm.pbf"
        base_pbf_path.touch()
        geojson_dir = mock_app_settings.osrm_data.base_dir / "regions"
        geojson_dir.mkdir(parents=True)
        (geojson_dir / "MyAreaRegionMap.json").touch()

        def side_effect(*args, **kwargs):
            cmd = args[0]
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.touch()

        mock_run_command.side_effect = side_effect

        result = extract_regional_pbfs_with_osmium(
            str(base_pbf_path), mock_app_settings
        )

        assert "MyArea" in result
        expected_output_pbf = geojson_dir / "MyArea.osm.pbf"
        assert result["MyArea"] == str(expected_output_pbf)
        mock_run_command.assert_called_once()


class TestBuildOsrmGraphsTransactional:
    """Tests for the transactional build_osrm_graphs_for_region function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Mocks external commands for all tests in this class."""
        mock_elevated = MagicMock()
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor.run_elevated_command",
            mock_elevated,
        )

        mock_container_run = MagicMock(return_value=True)
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor._run_osrm_container_command_internal",
            mock_container_run,
        )

        mock_shutil_move = MagicMock()
        monkeypatch.setattr("shutil.move", mock_shutil_move)

        mock_shutil_rmtree = MagicMock()
        monkeypatch.setattr("shutil.rmtree", mock_shutil_rmtree)

        return {
            "elevated": mock_elevated,
            "container": mock_container_run,
            "move": mock_shutil_move,
            "rmtree": mock_shutil_rmtree,
        }

    def test_successful_transactional_build(
        self, setup_mocks, mock_app_settings, tmp_path
    ):
        """Test a full, successful transactional build process."""
        region_name = "test_region"
        pbf_path = tmp_path / f"{region_name}.osm.pbf"
        pbf_path.touch()

        result = build_osrm_graphs_for_region(
            region_name, str(pbf_path), mock_app_settings
        )

        assert result is True

        mock_move = setup_mocks["move"]
        mock_move.assert_called_once()

        destination_path = mock_move.call_args[0][1]
        assert (
            Path(destination_path)
            == mock_app_settings.osrm_data.processed_dir / region_name
        )

        source_path = Path(mock_move.call_args[0][0])
        assert source_path.parent == mock_app_settings.osrm_data.processed_dir
        assert source_path.name.startswith(f"{region_name}_")

        setup_mocks["rmtree"].assert_not_called()

    def test_failed_transaction(
        self, setup_mocks, mock_app_settings, tmp_path
    ):
        """Test that a failed step does not commit the results."""

        def container_side_effect(*args, **kwargs):
            if args[6] == "osrm-partition":
                return False
            return True

        setup_mocks["container"].side_effect = container_side_effect

        region_name = "test_region"
        pbf_path = tmp_path / f"{region_name}.osm.pbf"
        pbf_path.touch()

        result = build_osrm_graphs_for_region(
            region_name, str(pbf_path), mock_app_settings
        )

        assert result is False

    def test_replace_existing_directory(
        self, setup_mocks, mock_app_settings, tmp_path
    ):
        """Test that a successful build replaces an existing directory."""
        region_name = "test_region"
        pbf_path = tmp_path / f"{region_name}.osm.pbf"
        pbf_path.touch()

        final_dir = mock_app_settings.osrm_data.processed_dir / region_name
        # FIX: Add parents=True to ensure the parent directory is also created.
        final_dir.mkdir(parents=True)

        result = build_osrm_graphs_for_region(
            region_name, str(pbf_path), mock_app_settings
        )

        assert result is True
        setup_mocks["rmtree"].assert_called_once_with(final_dir)
        setup_mocks["move"].assert_called_once()
