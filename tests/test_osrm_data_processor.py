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
    osrm_data_dir = tmp_path / "osrm_data"
    osrm_data_dir.mkdir()
    return AppSettings(
        osrm_data=OsrmDataSettings(
            base_dir=osrm_data_dir,
            processed_dir=tmp_path / "osrm_processed",
            profile_script_in_container="/opt/car.lua",
        ),
        osrm_service=OsrmServiceSettings(
            image_tag="osrm/osrm-backend:latest"
        ),
        container_runtime_command="docker",
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

        base_pbf_path = tmp_path / "base.osm.pbf"
        base_pbf_path.touch()
        geojson_dir = (
            Path(mock_app_settings.osrm_data.base_dir)
            / "regions"
            / "TestRegion"
        )
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

        assert "TestRegion_MyArea" in result
        expected_output_pbf = geojson_dir / "TestRegion_MyArea.osm.pbf"
        assert result["TestRegion_MyArea"] == str(expected_output_pbf)
        mock_run_command.assert_called_once()

    def test_extraction_skipped_if_exists(
        self, monkeypatch, mock_app_settings, tmp_path
    ):
        """Test that Osmium extraction is skipped if the output file already exists."""
        mock_run_command = MagicMock()
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor.run_command",
            mock_run_command,
        )

        base_pbf_path = tmp_path / "base.osm.pbf"
        base_pbf_path.touch()
        geojson_dir = (
            Path(mock_app_settings.osrm_data.base_dir)
            / "regions"
            / "TestRegion"
        )
        geojson_dir.mkdir(parents=True)
        (geojson_dir / "MyAreaRegionMap.json").touch()
        (geojson_dir / "TestRegion_MyArea.osm.pbf").touch()

        extract_regional_pbfs_with_osmium(
            str(base_pbf_path), mock_app_settings
        )

        mock_run_command.assert_not_called()

    def test_base_pbf_not_found(self, mock_app_settings, caplog):
        """Test that the function handles a missing base PBF file gracefully."""
        result = extract_regional_pbfs_with_osmium(
            "non_existent.pbf", mock_app_settings
        )
        assert result == {}
        assert "Base PBF file non_existent.pbf not found" in caplog.text


class TestBuildOsrmGraphs:
    """Tests for the build_osrm_graphs_for_region function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Mocks external commands for all tests in this class."""

        mock_elevated = MagicMock()

        def mock_mkdir_side_effect(*args, **kwargs):
            command = args[0]
            if command[0] == "mkdir":
                Path(command[2]).mkdir(parents=True, exist_ok=True)

        mock_elevated.side_effect = mock_mkdir_side_effect
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor.run_elevated_command",
            mock_elevated,
        )

        mock_container_run = MagicMock(return_value=True)
        monkeypatch.setattr(
            "processors.data_handling.osrm_data_processor._run_osrm_container_command_internal",
            mock_container_run,
        )
        return mock_elevated, mock_container_run

    def test_successful_graph_build(
        self, setup_mocks, mock_app_settings, tmp_path
    ):
        """Test a full, successful OSRM graph build process."""
        _, mock_container_run = setup_mocks
        region_name = "test_region"
        pbf_path = tmp_path / f"{region_name}.osm.pbf"
        pbf_path.touch()
        processed_dir = (
            Path(mock_app_settings.osrm_data.processed_dir) / region_name
        )

        def side_effect(*args, **kwargs):
            step = args[6]
            if step == "osrm-extract":
                (processed_dir / f"{region_name}.osrm").touch()
            elif step == "osrm-partition":
                (processed_dir / f"{region_name}.osrm.partition").touch()
            elif step == "osrm-customize":
                (processed_dir / f"{region_name}.osrm.customize").touch()
            return True

        mock_container_run.side_effect = side_effect

        result = build_osrm_graphs_for_region(
            region_name, str(pbf_path), mock_app_settings
        )

        assert result is True
        assert (processed_dir / f"{region_name}.osrm.partition").is_file()
        assert (processed_dir / f"{region_name}.osrm.customize").is_file()

    def test_file_rename_logic(
        self, setup_mocks, mock_app_settings, tmp_path
    ):
        """Test that files are correctly renamed if the PBF stem doesn't match the region key."""
        _, mock_container_run = setup_mocks
        region_name = "test_region"
        pbf_filename = "pbf_with_different_name.osm.pbf"
        pbf_path = tmp_path / pbf_filename
        pbf_path.touch()
        processed_dir = (
            Path(mock_app_settings.osrm_data.processed_dir) / region_name
        )
        pbf_stem = Path(pbf_filename).stem.removesuffix(".osm")

        def side_effect(*args, **kwargs):
            step = args[6]
            if step == "osrm-extract":
                (processed_dir / f"{pbf_stem}.osrm").touch()
            elif step == "rename":
                (processed_dir / f"{pbf_stem}.osrm").rename(
                    processed_dir / f"{region_name}.osrm"
                )
            return True

        mock_container_run.side_effect = side_effect

        build_osrm_graphs_for_region(
            region_name, str(pbf_path), mock_app_settings
        )

        step_calls = [c.args[6] for c in mock_container_run.call_args_list]
        assert "rename" in step_calls
        assert not (processed_dir / f"{pbf_stem}.osrm").exists()

    def test_build_fails_on_missing_pbf(
        self, setup_mocks, mock_app_settings, caplog
    ):
        """Test that the build fails if the input PBF file does not exist."""
        result = build_osrm_graphs_for_region(
            "test_region", "non_existent.pbf", mock_app_settings
        )
        assert result is False
        assert "Regional PBF file not found: non_existent.pbf" in caplog.text
