# opentasmania-osm-osrm-server/tests/common/test_network_utils.py
# -*- coding: utf-8 -*-
import logging

import pytest

from common.network_utils import validate_cidr
from setup.config_models import AppSettings


@pytest.fixture
def mock_app_settings():
    """Fixture to provide a mock AppSettings instance."""
    return AppSettings(symbols={"error": "❌", "warning": "!"})


@pytest.fixture
def mock_logger(mocker):
    """Fixture to provide a mock logger instance."""
    return mocker.Mock(spec=logging.Logger)


def test_validate_cidr_valid(mock_app_settings, mock_logger):
    """Test validate_cidr with a valid CIDR string."""
    cidr = "192.168.1.0/24"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is True


def test_validate_cidr_invalid_format(mock_app_settings, mock_logger):
    """Test validate_cidr with an invalid CIDR format."""
    cidr = "192.168.1.0-24"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_prefix_out_of_range(mock_app_settings, mock_logger):
    """Test validate_cidr with a CIDR prefix that is out of range."""
    cidr = "192.168.1.0/33"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_invalid_ip_octet(mock_app_settings, mock_logger):
    """Test validate_cidr with an IP that has an octet out of range."""
    cidr = "256.168.1.0/24"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_non_integer_octet(mock_app_settings, mock_logger):
    """Test validate_cidr with a CIDR containing non-integer octets."""
    cidr = "192.abc.1.0/24"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_non_string_input(mock_app_settings, mock_logger):
    """Test validate_cidr with a non-string input."""
    cidr = 12345
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_missing_octets(mock_app_settings, mock_logger):
    """Test validate_cidr with a CIDR missing some octets."""
    cidr = "192.168/24"
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False


def test_validate_cidr_empty_string(mock_app_settings, mock_logger):
    """Test validate_cidr with an empty string."""
    cidr = ""
    assert validate_cidr(cidr, mock_app_settings, mock_logger) is False
