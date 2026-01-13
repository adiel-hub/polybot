#!/usr/bin/env python3
"""Test script to verify Polymarket API credentials work."""

from py_clob_client.client import ClobClient
from core.wallet.generator import WalletGenerator


def test_credentials():
    """Test that we can create API credentials and connect to Polymarket."""
    # Generate a test wallet
    address, private_key = WalletGenerator.create_wallet()
    print(f"Test wallet: {address}")
    print(f"Private key: {private_key[:10]}...")

    # Create CLOB client
    print("\nConnecting to Polymarket CLOB API...")
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=private_key,
        signature_type=2,  # POLY_GNOSIS_SAFE
    )

    # Test basic API connectivity first
    try:
        ok = client.get_ok()
        print(f"✅ API health check: {ok}")
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return

    # Derive API credentials (this tests wallet signing)
    try:
        print("\nDeriving API credentials from wallet...")
        creds = client.create_or_derive_api_creds()
        print(f"✅ API credentials created successfully!")
        print(f"   API Key: {creds.api_key[:20]}...")
        print(f"   API Secret: {creds.api_secret[:20]}...")
        print(f"   Passphrase: {creds.api_passphrase[:10]}...")
    except Exception as e:
        print(f"❌ Failed to create credentials: {e}")
        return

    # Test authenticated endpoint
    try:
        print("\nTesting authenticated API call...")
        # Set the credentials on the client
        client.set_api_creds(creds)

        # Try to get open orders (will be empty for new wallet, but tests auth)
        orders = client.get_orders()
        print(f"✅ Authenticated API works! Open orders: {len(orders)}")
    except Exception as e:
        print(f"❌ Authenticated API call failed: {e}")
        return

    print("\n" + "=" * 50)
    print("✅ All Polymarket credential tests PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    test_credentials()
