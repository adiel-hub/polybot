"""Tests for Polymarket relayer client."""

import pytest
import base64
import hmac
import hashlib

from core.polymarket.relayer_client import PolymarketRelayer, RelayerResult


class TestRelayerClient:
    """Tests for PolymarketRelayer class."""

    def test_init_with_no_credentials(self, monkeypatch):
        """Test initialization without credentials."""
        monkeypatch.setattr("config.settings.poly_builder_api_key", "")
        monkeypatch.setattr("config.settings.poly_builder_secret", "")
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "")

        relayer = PolymarketRelayer()
        assert relayer.is_configured() is False

    def test_init_with_credentials(self, monkeypatch):
        """Test initialization with credentials."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert relayer.is_configured() is True

    def test_hmac_signature_format(self, monkeypatch):
        """Test HMAC signature generation."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        # Test signature generation
        method = "POST"
        path = "/submit"
        timestamp = "1234567890"
        body = '{"test": "data"}'

        signature = relayer._sign_request(method, path, timestamp, body)

        # Verify signature is URL-safe base64 encoded
        assert signature is not None
        decoded = base64.urlsafe_b64decode(signature)
        assert len(decoded) == 32  # SHA256 produces 32 bytes

    def test_headers_contain_required_fields(self, monkeypatch):
        """Test that headers contain all required builder authentication fields."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        headers = relayer._get_headers("POST", "/test", "")

        # Builder-specific headers (POLY_BUILDER_*)
        assert "POLY_BUILDER_API_KEY" in headers
        assert "POLY_BUILDER_SIGNATURE" in headers
        assert "POLY_BUILDER_TIMESTAMP" in headers
        assert "POLY_BUILDER_PASSPHRASE" in headers
        assert headers["Content-Type"] == "application/json"

    def test_headers_values_are_correct(self, monkeypatch):
        """Test that header values are set correctly."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        headers = relayer._get_headers("POST", "/test", "")

        assert headers["POLY_BUILDER_API_KEY"] == "test_api_key"
        assert headers["POLY_BUILDER_PASSPHRASE"] == "test_passphrase"
        # Signature and timestamp should be present
        assert len(headers["POLY_BUILDER_SIGNATURE"]) > 0
        assert headers["POLY_BUILDER_TIMESTAMP"].isdigit()

    def test_encode_erc20_approve(self, monkeypatch):
        """Test ERC20 approve calldata encoding."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        spender = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        amount = 1000000  # 1 USDC

        calldata = relayer._encode_erc20_approve(spender, amount)

        # Check function selector for approve(address,uint256)
        assert calldata.startswith("0x095ea7b3")
        # Check length (4 bytes selector + 32 bytes address + 32 bytes amount = 68 bytes = 136 hex chars + 2 for 0x)
        assert len(calldata) == 138

    def test_encode_erc20_transfer(self, monkeypatch):
        """Test ERC20 transfer calldata encoding."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        to_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"
        amount = 5000000  # 5 USDC

        calldata = relayer._encode_erc20_transfer(to_address, amount)

        # Check function selector for transfer(address,uint256)
        assert calldata.startswith("0xa9059cbb")
        assert len(calldata) == 138


class TestSignaturePacking:
    """Tests for Safe signature packing."""

    def test_split_and_pack_signature_v27(self, monkeypatch):
        """Test signature packing with v=27 (should become 31)."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        # Sample signature with v=27 (0x1b)
        # r = 0x1234...., s = 0x5678...., v = 0x1b (27)
        r_hex = "1234567890123456789012345678901234567890123456789012345678901234"
        s_hex = "5678901234567890123456789012345678901234567890123456789012345678"
        v_hex = "1b"  # 27
        signature = "0x" + r_hex + s_hex + v_hex

        packed = relayer._split_and_pack_signature(signature)

        # Should start with 0x
        assert packed.startswith("0x")
        # 32 bytes for r + 32 bytes for s + 1 byte for v = 65 bytes = 130 hex chars + 2 for 0x
        assert len(packed) == 132

    def test_split_and_pack_signature_v28(self, monkeypatch):
        """Test signature packing with v=28 (should become 32)."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        # Sample signature with v=28 (0x1c)
        r_hex = "1234567890123456789012345678901234567890123456789012345678901234"
        s_hex = "5678901234567890123456789012345678901234567890123456789012345678"
        v_hex = "1c"  # 28
        signature = "0x" + r_hex + s_hex + v_hex

        packed = relayer._split_and_pack_signature(signature)

        # Verify the v value is normalized (28 + 4 = 32 = 0x20)
        # v is the last byte
        packed_bytes = bytes.fromhex(packed[2:])
        v_normalized = packed_bytes[-1]
        assert v_normalized == 32

    def test_split_and_pack_signature_v0(self, monkeypatch):
        """Test signature packing with v=0 (should become 31)."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        r_hex = "1234567890123456789012345678901234567890123456789012345678901234"
        s_hex = "5678901234567890123456789012345678901234567890123456789012345678"
        v_hex = "00"  # 0
        signature = "0x" + r_hex + s_hex + v_hex

        packed = relayer._split_and_pack_signature(signature)

        # Verify the v value is normalized (0 + 31 = 31 = 0x1f)
        packed_bytes = bytes.fromhex(packed[2:])
        v_normalized = packed_bytes[-1]
        assert v_normalized == 31

    def test_split_and_pack_signature_invalid_v(self, monkeypatch):
        """Test signature packing with invalid v raises error."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        r_hex = "1234567890123456789012345678901234567890123456789012345678901234"
        s_hex = "5678901234567890123456789012345678901234567890123456789012345678"
        v_hex = "ff"  # Invalid v value
        signature = "0x" + r_hex + s_hex + v_hex

        with pytest.raises(ValueError, match="Invalid v value"):
            relayer._split_and_pack_signature(signature)


class TestSetApprovalForAllEncoding:
    """Tests for setApprovalForAll calldata encoding."""

    def test_encode_set_approval_for_all_approve(self, monkeypatch):
        """Test setApprovalForAll encoding with approved=True."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        operator = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

        calldata = relayer._encode_set_approval_for_all(operator, True)

        # Check function selector for setApprovalForAll(address,bool)
        assert calldata.startswith("0xa22cb465")
        # Check length (4 bytes selector + 32 bytes address + 32 bytes bool = 68 bytes = 136 hex chars + 2 for 0x)
        assert len(calldata) == 138

    def test_encode_set_approval_for_all_revoke(self, monkeypatch):
        """Test setApprovalForAll encoding with approved=False."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()

        operator = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

        calldata = relayer._encode_set_approval_for_all(operator, False)

        # Check function selector
        assert calldata.startswith("0xa22cb465")
        # Should have different last 32 bytes (0 instead of 1)
        assert calldata.endswith("0" * 63 + "0")  # bool false is 0


class TestContractAddresses:
    """Tests for contract address constants."""

    def test_usdc_spenders_count(self):
        """Test that USDC_SPENDERS has the correct number of addresses."""
        from core.polymarket.relayer_client import USDC_SPENDERS
        assert len(USDC_SPENDERS) == 3

    def test_ctf_operators_count(self):
        """Test that CTF_OPERATORS has the correct number of addresses."""
        from core.polymarket.relayer_client import CTF_OPERATORS
        assert len(CTF_OPERATORS) == 3

    def test_address_validity(self):
        """Test that all addresses are valid Ethereum addresses."""
        from core.polymarket.relayer_client import (
            USDC_ADDRESS,
            CTF_ADDRESS,
            CTF_EXCHANGE_ADDRESS,
            NEG_RISK_CTF_ADDRESS,
            NEG_RISK_ADAPTER_ADDRESS,
        )

        addresses = [
            USDC_ADDRESS,
            CTF_ADDRESS,
            CTF_EXCHANGE_ADDRESS,
            NEG_RISK_CTF_ADDRESS,
            NEG_RISK_ADAPTER_ADDRESS,
        ]

        for addr in addresses:
            assert addr.startswith("0x")
            assert len(addr) == 42


class TestRelayerResult:
    """Tests for RelayerResult dataclass."""

    def test_successful_result(self):
        """Test successful result creation."""
        result = RelayerResult(
            success=True,
            tx_hash="0x1234567890abcdef",
            data={"status": "ok"},
        )

        assert result.success is True
        assert result.tx_hash == "0x1234567890abcdef"
        assert result.error is None

    def test_failed_result(self):
        """Test failed result creation."""
        result = RelayerResult(
            success=False,
            error="Transaction failed",
        )

        assert result.success is False
        assert result.tx_hash is None
        assert result.error == "Transaction failed"


class TestOnChainVerification:
    """Tests for on-chain verification methods."""

    def test_verify_on_chain_allowance_method_exists(self, monkeypatch):
        """Test that verify_on_chain_allowance method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_on_chain_allowance")
        assert callable(relayer.verify_on_chain_allowance)

    def test_wait_for_transaction_method_exists(self, monkeypatch):
        """Test that wait_for_transaction method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "wait_for_transaction")
        assert callable(relayer.wait_for_transaction)

    def test_verify_all_allowances_method_exists(self, monkeypatch):
        """Test that verify_all_allowances method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_all_allowances")
        assert callable(relayer.verify_all_allowances)

    @pytest.mark.asyncio
    async def test_wait_for_transaction_returns_false_for_none_hash(self, monkeypatch):
        """Test that wait_for_transaction returns False for None hash."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        result = await relayer.wait_for_transaction(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_transaction_returns_false_for_empty_hash(self, monkeypatch):
        """Test that wait_for_transaction returns False for empty hash."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        result = await relayer.wait_for_transaction("")
        assert result is False

    def test_verify_safe_deployed_method_exists(self, monkeypatch):
        """Test that verify_safe_deployed method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_safe_deployed")
        assert callable(relayer.verify_safe_deployed)

    def test_verify_ctf_operator_approval_method_exists(self, monkeypatch):
        """Test that verify_ctf_operator_approval method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_ctf_operator_approval")
        assert callable(relayer.verify_ctf_operator_approval)

    def test_verify_all_ctf_approvals_method_exists(self, monkeypatch):
        """Test that verify_all_ctf_approvals method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_all_ctf_approvals")
        assert callable(relayer.verify_all_ctf_approvals)

    def test_verify_all_approvals_complete_method_exists(self, monkeypatch):
        """Test that verify_all_approvals_complete method exists."""
        test_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()
        monkeypatch.setattr("config.settings.poly_builder_api_key", "test_api_key")
        monkeypatch.setattr("config.settings.poly_builder_secret", test_secret)
        monkeypatch.setattr("config.settings.poly_builder_passphrase", "test_passphrase")

        relayer = PolymarketRelayer()
        assert hasattr(relayer, "verify_all_approvals_complete")
        assert callable(relayer.verify_all_approvals_complete)
