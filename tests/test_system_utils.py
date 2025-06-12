# tests/test_system_utils.py
import hashlib
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Adjust the import path based on your project structure if necessary
from common.system_utils import (
    calculate_project_hash,
    calculate_threads,
    get_current_script_hash,
    get_debian_codename,
    systemd_reload,
)
from setup.config_models import SYMBOLS_DEFAULT, AppSettings, RenderdSettings

# --- Fixtures and Mocks ---


@pytest.fixture(autouse=True)
def reset_cached_script_hash():
    """Fixture to reset CACHED_SCRIPT_HASH before each test."""
    global CACHED_SCRIPT_HASH
    CACHED_SCRIPT_HASH = None
    yield
    CACHED_SCRIPT_HASH = None  # Ensure it's reset after test too


@pytest.fixture
def mock_app_settings():
    """Mock AppSettings object with common symbols and renderd config."""
    mock_symbols = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "debug": "🐛",
        "gear": "⚙️",
    }
    mock_renderd_settings = RenderdSettings(num_threads_multiplier=1.0)
    mock_settings = AppSettings(
        symbols=mock_symbols,
        renderd=mock_renderd_settings,
        # Add other necessary attributes if they are accessed by system_utils
        # For example, if system_utils accesses app_settings.logging_level
        # logging_level="INFO"
    )
    return mock_settings


# This mock_logger fixture is for explicitly passing a logger to functions if needed.
# It's different from the internal module_logger in system_utils.py.
@pytest.fixture
def mock_logger():
    """Mock logger instance."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_log_map_server():
    """Mock the log_map_server function."""
    with patch("common.system_utils.log_map_server") as mock:
        yield mock


@pytest.fixture
def mock_run_command():
    """Mock the run_command function."""
    with patch("common.system_utils.run_command") as mock:
        yield mock


@pytest.fixture
def mock_run_elevated_command():
    """Mock the run_elevated_command function."""
    with patch("common.system_utils.run_elevated_command") as mock:
        yield mock


# --- Tests for calculate_project_hash ---


def test_calculate_project_hash_success(
    tmp_path, mock_app_settings, mock_log_map_server
):
    """Test successful hashing of project files."""
    # Create dummy Python files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.py").write_text("def func(): pass")
    (tmp_path / "config.py").write_text("VERSION = '1.0'")

    # Create a non-Python file to ensure it's ignored
    (tmp_path / "README.md").write_text("# Project")

    # Expected hash (calculated manually or based on known content/paths)
    # The order of files is important for hashing (sorted by relative path)
    # config.py, src/main.py, src/utils.py
    # content: b'VERSION = \'1.0\''
    # content: b'print(\'hello\')'
    # content: b'def func(): pass'
    # paths: b'config.py', b'src/main.py', b'src/utils.py'
    import hashlib

    hasher = hashlib.sha256()
    hasher.update(b"config.py")
    hasher.update(b"VERSION = '1.0'")
    hasher.update(b"src/main.py")
    hasher.update(b"print('hello')")
    hasher.update(b"src/utils.py")
    hasher.update(b"def func(): pass")
    expected_hash = hasher.hexdigest()

    # When current_logger is None, calculate_project_hash uses module_logger.
    # We need to patch module_logger for accurate assertion of log_map_server calls.
    with patch("common.system_utils.module_logger") as patched_module_logger:
        result = calculate_project_hash(tmp_path, mock_app_settings)

        assert result == expected_hash
        mock_log_map_server.assert_called_with(
            f"{mock_app_settings.symbols.get('debug', '🐛')} Calculated SCRIPT_HASH: {expected_hash} from 3 .py files in {tmp_path}.",
            "debug",
            patched_module_logger,  # Use the patched module logger here
            mock_app_settings,
        )


def test_calculate_project_hash_no_py_files(
    tmp_path, mock_app_settings, mock_log_map_server
):
    """Test hashing when no Python files are found."""
    (tmp_path / "data.txt").write_text("some data")

    with patch("common.system_utils.module_logger") as patched_module_logger:
        result = calculate_project_hash(tmp_path, mock_app_settings)

        # Hash of an empty set of files
        assert result == hashlib.sha256().hexdigest()
        mock_log_map_server.assert_called_with(
            f"{mock_app_settings.symbols.get('warning', '!')} No .py files found under '{tmp_path}' for hashing. Hash will be of an empty set.",
            "warning",
            patched_module_logger,
            mock_app_settings,
        )


def test_calculate_project_hash_empty_directory(
    tmp_path, mock_app_settings, mock_log_map_server
):
    """Test hashing an empty directory."""
    with patch("common.system_utils.module_logger") as patched_module_logger:
        result = calculate_project_hash(tmp_path, mock_app_settings)

        assert result == hashlib.sha256().hexdigest()
        mock_log_map_server.assert_called_with(
            f"{mock_app_settings.symbols.get('warning', '!')} No .py files found under '{tmp_path}' for hashing. Hash will be of an empty set.",
            "warning",
            patched_module_logger,
            mock_app_settings,
        )


def test_calculate_project_hash_non_existent_directory(
    mock_app_settings, mock_log_map_server
):
    """Test hashing with a non-existent project root directory."""
    non_existent_path = Path("/non_existent_dir_for_test")
    with patch("common.system_utils.module_logger") as patched_module_logger:
        result = calculate_project_hash(non_existent_path, mock_app_settings)

        assert result is None
        mock_log_map_server.assert_called_with(
            f"{mock_app_settings.symbols.get('error', '❌')} Project root directory '{non_existent_path}' not found for hashing.",
            "error",
            patched_module_logger,
            mock_app_settings,
        )


def test_calculate_project_hash_file_read_error(
    tmp_path, mock_app_settings, mock_log_map_server
):
    """Test error handling when a file cannot be read."""
    (tmp_path / "broken.py").write_text("content")
    # Simulate an error when reading the file
    with patch.object(
        Path, "read_bytes", side_effect=IOError("Permission denied")
    ):
        with patch(
            "common.system_utils.module_logger"
        ) as patched_module_logger:
            result = calculate_project_hash(tmp_path, mock_app_settings)

            assert result is None
            mock_log_map_server.assert_called_with(
                f"{mock_app_settings.symbols.get('error', '❌')} Error reading file {tmp_path / 'broken.py'} for hashing: Permission denied",
                "error",
                patched_module_logger,
                mock_app_settings,
            )


def test_calculate_project_hash_general_error(
    mock_app_settings, mock_log_map_server
):
    """Test general exception during hashing process."""
    # Simulate a general error (e.g., if rglob fails unexpectedly)
    with patch.object(
        Path, "rglob", side_effect=Exception("Unexpected rglob error")
    ):
        with patch(
            "common.system_utils.module_logger"
        ) as patched_module_logger:
            result = calculate_project_hash(Path("/tmp"), mock_app_settings)

            assert result is None
            mock_log_map_server.assert_called_with(
                f"{mock_app_settings.symbols.get('error', '❌')} Critical error during project hashing: Unexpected rglob error",
                "error",
                patched_module_logger,
                mock_app_settings,
                exc_info=True,
            )


# --- Tests for get_current_script_hash ---


def test_get_current_script_hash_caches_value(
    tmp_path, mock_app_settings, mock_log_map_server, mock_logger
):
    """Test that get_current_script_hash caches the result."""
    (tmp_path / "test.py").write_text("x=1")

    with patch(
        "common.system_utils.calculate_project_hash", return_value="hash1"
    ) as mock_calc:
        with patch(
            "common.system_utils.module_logger"
        ) as patched_module_logger_in_system_utils:
            # First call should calculate and cache
            hash1 = get_current_script_hash(
                tmp_path,
                mock_app_settings,
                logger_instance=patched_module_logger_in_system_utils,
            )
            assert hash1 == "hash1"
            # calculate_project_hash is called with logger_instance from get_current_script_hash
            mock_calc.assert_called_once_with(
                tmp_path,
                mock_app_settings,
                current_logger=patched_module_logger_in_system_utils,
            )

            # Second call should return cached value without recalculating
            hash2 = get_current_script_hash(
                tmp_path,
                mock_app_settings,
                logger_instance=patched_module_logger_in_system_utils,
            )
            assert hash2 == "hash1"
            mock_calc.assert_called_once()  # Still only called once


# --- Tests for systemd_reload ---


def test_systemd_reload_success(
    mock_app_settings, mock_run_elevated_command, mock_log_map_server
):
    """Test successful systemd daemon reload."""
    with patch("common.system_utils.module_logger") as patched_module_logger:
        systemd_reload(mock_app_settings)

        mock_log_map_server.assert_any_call(
            f"{mock_app_settings.symbols.get('gear', '⚙️')} Reloading systemd daemon...",
            "info",
            patched_module_logger,
            mock_app_settings,
        )
        mock_run_elevated_command.assert_called_once_with(
            ["systemctl", "daemon-reload"],
            mock_app_settings,
            current_logger=patched_module_logger,
        )
        mock_log_map_server.assert_any_call(
            f"{mock_app_settings.symbols.get('success', '✅')} Systemd daemon reloaded.",
            "success",
            patched_module_logger,
            mock_app_settings,
        )


def test_systemd_reload_failure(
    mock_app_settings, mock_run_elevated_command, mock_log_map_server
):
    """Test systemd daemon reload failure."""
    mock_run_elevated_command.side_effect = Exception("Systemd reload failed")

    with patch("common.system_utils.module_logger") as patched_module_logger:
        systemd_reload(mock_app_settings)

        mock_log_map_server.assert_any_call(
            f"{mock_app_settings.symbols.get('error', '❌')} Failed to reload systemd: Systemd reload failed",
            "error",
            patched_module_logger,
            mock_app_settings,
        )


# --- Tests for get_debian_codename ---


def test_get_debian_codename_success(
    mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test successful retrieval of Debian codename."""
    mock_run_command.return_value = MagicMock(
        stdout="bookworm\n", returncode=0
    )

    with patch("common.system_utils.module_logger") as patched_module_logger:
        codename = get_debian_codename(mock_app_settings)

        assert codename == "bookworm"
        mock_run_command.assert_called_once_with(
            ["lsb_release", "-cs"],
            mock_app_settings,
            capture_output=True,
            check=True,
            current_logger=patched_module_logger,  # Corrected: use the patched module_logger
        )
        mock_log_map_server.assert_not_called()  # No errors/warnings expected


def test_get_debian_codename_lsb_release_not_found(
    mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test when lsb_release command is not found."""
    mock_run_command.side_effect = FileNotFoundError

    with patch("common.system_utils.module_logger") as patched_module_logger:
        codename = get_debian_codename(mock_app_settings)

        assert codename is None
        mock_log_map_server.assert_called_once_with(
            f"{mock_app_settings.symbols.get('warning', '!')} lsb_release command not found. Cannot determine Debian codename.",
            "warning",
            patched_module_logger,  # Corrected
            mock_app_settings,
        )


def test_get_debian_codename_command_fails(
    mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test when lsb_release command fails."""
    from subprocess import CalledProcessError

    mock_run_command.side_effect = CalledProcessError(
        1, ["lsb_release", "-cs"], stderr="Error output"
    )

    # In this error path, log_map_server is not called directly by get_debian_codename,
    # and run_command's logger is handled by run_command itself.
    # Therefore, patched_module_logger is unused here.
    codename = get_debian_codename(mock_app_settings)

    assert codename is None
    mock_log_map_server.assert_not_called()  # Assuming run_command logs it


def test_get_debian_codename_no_app_settings(
    mock_run_command, mock_log_map_server
):
    """Test when app_settings is None."""
    mock_run_command.return_value = MagicMock(
        stdout="bookworm\n", returncode=0
    )
    # In this success path, log_map_server is not called.
    # Therefore, patched_module_logger is unused here.
    codename = get_debian_codename(None)
    assert codename == "bookworm"
    # Ensure default symbols are used for log_map_server if it were called
    # (which it isn't in success case)


def test_get_debian_codename_general_exception(
    mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test general unexpected error getting Debian codename."""
    mock_run_command.side_effect = Exception("Unknown error")

    with patch("common.system_utils.module_logger") as patched_module_logger:
        codename = get_debian_codename(mock_app_settings)

        assert codename is None
        mock_log_map_server.assert_called_once_with(
            f"{mock_app_settings.symbols.get('warning', '!')} Unexpected error getting Debian codename: Unknown error",
            "warning",
            patched_module_logger,
            mock_app_settings,
        )


# --- Tests for calculate_threads ---


@patch("common.system_utils.cpu_count")
def test_calculate_threads_success_with_lscpu(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test successful thread calculation using lscpu output."""
    mock_app_settings.renderd.num_threads_multiplier = 2.0
    mock_run_command.return_value = MagicMock(
        stdout="0,0\n1,0\n2,0\n3,0\n", returncode=0
    )  # 4 physical cores
    mock_cpu_count.return_value = 8  # Total logical CPUs

    with patch("common.system_utils.module_logger") as patched_module_logger:
        threads = calculate_threads(mock_app_settings)

        assert threads == "8"  # 4 physical cores * 2.0 multiplier
        mock_run_command.assert_called_once_with(
            ["lscpu", "-p=Core,Socket"],
            mock_app_settings,
            capture_output=True,
            check=True,
            current_logger=patched_module_logger,
        )
        mock_log_map_server.assert_not_called()  # No errors/warnings expected


@patch("common.system_utils.cpu_count")
def test_calculate_threads_success_fallback_to_cpu_count(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test successful thread calculation falling back to cpu_count if lscpu output is empty/unparseable."""
    mock_app_settings.renderd.num_threads_multiplier = 0.5
    mock_run_command.return_value = MagicMock(
        stdout="# No output\n", returncode=0
    )  # lscpu returns header but no data, simulating unparseable for physical cores
    mock_cpu_count.return_value = 4  # Total logical CPUs

    # This scenario results in an empty set of physical cores, not an exception.
    # Therefore, log_map_server is not called here.
    threads = calculate_threads(mock_app_settings)

    assert threads == "2"  # 4 logical CPUs * 0.5 multiplier
    mock_log_map_server.assert_not_called()


@patch("common.system_utils.cpu_count")
def test_calculate_threads_lscpu_not_found(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test when lscpu command is not found."""
    mock_run_command.side_effect = FileNotFoundError
    mock_cpu_count.return_value = 4

    with patch("common.system_utils.module_logger") as patched_module_logger:
        threads = calculate_threads(mock_app_settings)

        assert threads is None
        mock_log_map_server.assert_called_once_with(
            f"{mock_app_settings.symbols.get('warning', '!')} lscpu command not found. Cannot determine cpu count.",
            "warning",
            patched_module_logger,
            mock_app_settings,
        )


def test_calculate_threads_no_app_settings(mock_log_map_server):
    """Test when app_settings is None."""
    with patch("common.system_utils.module_logger") as patched_module_logger:
        threads = calculate_threads(None)

        assert threads is None
        mock_log_map_server.assert_called_once_with(
            f"{SYMBOLS_DEFAULT.get('error', '❌')} App settings or renderd configuration not found. Cannot calculate threads.",
            "error",
            patched_module_logger,
            None,  # app_settings is None in this test
        )


def test_calculate_threads_no_renderd_in_app_settings(
    mock_app_settings, mock_log_map_server
):
    """Test when app_settings does not have renderd attribute."""
    mock_app_settings.renderd = None  # Simulate missing renderd config
    with patch("common.system_utils.module_logger") as patched_module_logger:
        threads = calculate_threads(mock_app_settings)

        assert threads is None
        mock_log_map_server.assert_called_once_with(
            f"{mock_app_settings.symbols.get('error', '❌')} App settings or renderd configuration not found. Cannot calculate threads.",
            "error",
            patched_module_logger,
            mock_app_settings,
        )


@patch("common.system_utils.cpu_count")
def test_calculate_threads_multiplier_zero_or_less(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test when num_threads_multiplier is zero or negative."""
    mock_app_settings.renderd.num_threads_multiplier = 0.0  # Or -1.0
    mock_run_command.return_value = MagicMock(stdout="0,0\n", returncode=0)
    mock_cpu_count.return_value = 2

    # In this case, log_map_server is not called.
    threads = calculate_threads(mock_app_settings)

    assert threads == "0"  # Should return "0" if multiplier is 0 or less
    mock_log_map_server.assert_not_called()


@patch("common.system_utils.cpu_count")
def test_calculate_threads_min_one_thread(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test that calculated threads is at least 1."""
    mock_app_settings.renderd.num_threads_multiplier = 0.1
    mock_run_command.return_value = MagicMock(
        stdout="0,0\n", returncode=0
    )  # 1 physical core
    mock_cpu_count.return_value = 1

    # In this case, log_map_server is not called.
    threads = calculate_threads(mock_app_settings)
    # 1 physical core * 0.1 = 0.1, max(1, 0.1) = 1
    assert threads == "1"
    mock_log_map_server.assert_not_called()


@patch("common.system_utils.cpu_count")
def test_calculate_threads_lscpu_called_process_error(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test when lscpu command returns a CalledProcessError."""
    from subprocess import CalledProcessError

    mock_run_command.side_effect = CalledProcessError(
        1, ["lscpu"], stderr="lscpu error"
    )
    mock_cpu_count.return_value = 4  # Fallback value won't be used here

    # In this error case, log_map_server is not called directly by calculate_threads;
    # run_command is expected to handle its own logging.
    threads = calculate_threads(mock_app_settings)

    assert threads is None
    mock_log_map_server.assert_not_called()


@patch("common.system_utils.cpu_count")
def test_calculate_threads_general_exception(
    mock_cpu_count, mock_app_settings, mock_run_command, mock_log_map_server
):
    """Test for general unexpected exception during thread calculation."""
    mock_run_command.side_effect = Exception("Some unexpected issue")
    mock_cpu_count.return_value = 4

    with patch("common.system_utils.module_logger") as patched_module_logger:
        threads = calculate_threads(mock_app_settings)

        assert threads is None
        mock_log_map_server.assert_called_once_with(
            f"{mock_app_settings.symbols.get('warning', '!')} Unexpected error calculating threads: Some unexpected issue",
            "warning",
            patched_module_logger,
            mock_app_settings,
        )
