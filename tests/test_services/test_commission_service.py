"""Tests for the commission service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.commission_service import CommissionService, CommissionCalculation


class TestCommissionCalculation:
    """Tests for commission calculation logic."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create commission service with default settings."""
        with patch("services.commission_service.settings") as mock_settings:
            mock_settings.operator_commission_rate = 0.01  # 1%
            mock_settings.min_commission_amount = 0.01
            mock_settings.operator_wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
            mock_settings.polygon_rpc_url = "https://polygon-rpc.com"
            mock_settings.gas_sponsor_private_key = ""
            mock_settings.chain_id = 137

            service = CommissionService(mock_db)
            # Override the rate from settings
            service.commission_rate = 0.01
            service.min_commission = 0.01
            service.operator_wallet = "0x1234567890abcdef1234567890abcdef12345678"
            return service

    def test_calculate_commission_standard(self, service):
        """Test standard commission calculation."""
        result = service.calculate_commission(100.0)

        assert result.original_amount == 100.0
        assert result.commission_rate == 0.01
        assert result.commission_amount == 1.0
        assert result.net_trade_amount == 99.0

    def test_calculate_commission_small_amount(self, service):
        """Test commission on small trade."""
        result = service.calculate_commission(10.0)

        assert result.original_amount == 10.0
        assert result.commission_amount == 0.10
        assert result.net_trade_amount == 9.90

    def test_calculate_commission_below_minimum(self, service):
        """Test commission below minimum threshold is skipped."""
        # $0.50 trade * 1% = $0.005, which is below $0.01 minimum
        result = service.calculate_commission(0.50)

        assert result.original_amount == 0.50
        assert result.commission_amount == 0.0  # Skipped
        assert result.net_trade_amount == 0.50  # Full amount

    def test_calculate_commission_at_minimum_threshold(self, service):
        """Test commission exactly at minimum threshold."""
        # $1.00 trade * 1% = $0.01, exactly at minimum
        result = service.calculate_commission(1.00)

        assert result.commission_amount == 0.01
        assert result.net_trade_amount == 0.99

    def test_calculate_commission_large_trade(self, service):
        """Test commission on large trade."""
        result = service.calculate_commission(10000.0)

        assert result.commission_amount == 100.0
        assert result.net_trade_amount == 9900.0

    def test_is_enabled_with_wallet(self, service):
        """Test is_enabled returns True when wallet is configured."""
        assert service.is_enabled() is True

    def test_is_enabled_without_wallet(self, service):
        """Test is_enabled returns False when wallet is not configured."""
        service.operator_wallet = ""
        assert service.is_enabled() is False

    def test_is_enabled_zero_rate(self, service):
        """Test is_enabled returns False when rate is zero."""
        service.commission_rate = 0.0
        assert service.is_enabled() is False


class TestCommissionServiceWithDifferentRates:
    """Test commission calculations with different rates."""

    def test_half_percent_rate(self):
        """Test 0.5% commission rate."""
        with patch("services.commission_service.settings") as mock_settings:
            mock_settings.operator_commission_rate = 0.005  # 0.5%
            mock_settings.min_commission_amount = 0.01
            mock_settings.operator_wallet_address = "0x1234"
            mock_settings.polygon_rpc_url = "https://polygon-rpc.com"
            mock_settings.gas_sponsor_private_key = ""
            mock_settings.chain_id = 137

            service = CommissionService(MagicMock())
            service.commission_rate = 0.005
            service.min_commission = 0.01
            service.operator_wallet = "0x1234"

            result = service.calculate_commission(100.0)

            assert result.commission_rate == 0.005
            assert result.commission_amount == 0.50
            assert result.net_trade_amount == 99.50

    def test_two_percent_rate(self):
        """Test 2% commission rate."""
        with patch("services.commission_service.settings") as mock_settings:
            mock_settings.operator_commission_rate = 0.02  # 2%
            mock_settings.min_commission_amount = 0.01
            mock_settings.operator_wallet_address = "0x1234"
            mock_settings.polygon_rpc_url = "https://polygon-rpc.com"
            mock_settings.gas_sponsor_private_key = ""
            mock_settings.chain_id = 137

            service = CommissionService(MagicMock())
            service.commission_rate = 0.02
            service.min_commission = 0.01
            service.operator_wallet = "0x1234"

            result = service.calculate_commission(100.0)

            assert result.commission_rate == 0.02
            assert result.commission_amount == 2.0
            assert result.net_trade_amount == 98.0


class TestCommissionDataclass:
    """Test the CommissionCalculation dataclass."""

    def test_dataclass_creation(self):
        """Test creating CommissionCalculation directly."""
        calc = CommissionCalculation(
            original_amount=100.0,
            commission_rate=0.01,
            commission_amount=1.0,
            net_trade_amount=99.0,
        )

        assert calc.original_amount == 100.0
        assert calc.commission_rate == 0.01
        assert calc.commission_amount == 1.0
        assert calc.net_trade_amount == 99.0

    def test_dataclass_equality(self):
        """Test CommissionCalculation equality."""
        calc1 = CommissionCalculation(100.0, 0.01, 1.0, 99.0)
        calc2 = CommissionCalculation(100.0, 0.01, 1.0, 99.0)

        assert calc1 == calc2
