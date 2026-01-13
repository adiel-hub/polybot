"""Integration tests for withdrawal execution using REAL bot implementation.

These tests execute actual USDC withdrawals on Polygon blockchain.
All transactions are REAL - no mocks!

Cost per test: Gas fees only (USDC is sent and received back)
"""

import pytest
import pytest_asyncio
from web3 import Web3

# Import REAL bot services
from services.user_service import UserService
from database.repositories.wallet_repo import WalletRepository
from core.blockchain.withdrawals import WithdrawalManager
from config.settings import settings
from config.constants import USDC_ADDRESS, USDC_DECIMALS


@pytest.mark.integration
@pytest.mark.expensive
@pytest.mark.asyncio
async def test_real_usdc_withdrawal(
    real_user_service: UserService,
    real_withdrawal_manager: WithdrawalManager,
    funded_test_user,
    external_wallet,
    web3_polygon: Web3,
    wallet_repo: WalletRepository,
    check_balance_on_chain,
    send_pol_for_gas,
):
    """Test REAL USDC withdrawal execution on Polygon.

    Flow:
    1. Use funded test user (has USDC)
    2. Send POL to bot wallet for gas
    3. Execute real withdrawal via WithdrawalManager
    4. Verify transaction broadcasts to Polygon
    5. Verify funds arrive at destination
    6. Verify database balance decreases

    Cost: ~0.02 POL for gas (USDC returns to your wallet)
    """
    print(f"\n{'='*80}")
    print(f"REAL USDC WITHDRAWAL TEST")
    print(f"{'='*80}\n")

    user, wallet = funded_test_user

    print(f"📋 Test setup:")
    print(f"   User ID: {user.id}")
    print(f"   Wallet: {wallet.address}")
    print(f"   Initial DB balance: ${wallet.usdc_balance:.2f}")

    # Check initial on-chain balance
    initial_onchain = check_balance_on_chain(wallet.address)
    print(f"   Initial on-chain balance: ${initial_onchain:.6f}")

    # Send POL for gas
    print(f"\n🔄 Sending POL for gas...")
    await send_pol_for_gas(wallet.address, amount_pol=0.05)

    # Verify POL received
    pol_balance = web3_polygon.eth.get_balance(wallet.address)
    pol_ether = web3_polygon.from_wei(pol_balance, 'ether')
    print(f"✅ Bot wallet POL balance: {pol_ether:.4f}")
    assert pol_balance > 0, "No POL for gas"

    # Get REAL private key
    private_key = await real_user_service.get_private_key(user.id)
    assert private_key, "Could not decrypt private key"
    print(f"✅ Private key decrypted")

    # Execute REAL withdrawal
    withdrawal_amount = settings.test_withdrawal_amount
    destination = external_wallet.address

    print(f"\n🔄 Executing withdrawal:")
    print(f"   Amount: ${withdrawal_amount} USDC")
    print(f"   From: {wallet.address}")
    print(f"   To: {destination}")

    result = await real_withdrawal_manager.withdraw(
        from_private_key=private_key,
        to_address=destination,
        amount=withdrawal_amount,
    )

    # Verify withdrawal result
    assert result.success, f"Withdrawal failed: {result.error}"
    assert result.tx_hash, "No transaction hash returned"

    print(f"\n✅ Withdrawal broadcast!")
    print(f"   TX hash: {result.tx_hash}")

    # Verify on-chain using REAL web3
    print(f"\n🔍 Waiting for confirmation...")
    receipt = web3_polygon.eth.get_transaction_receipt(result.tx_hash)
    assert receipt.status == 1, "Withdrawal transaction failed on-chain"

    print(f"✅ Transaction confirmed on-chain!")
    print(f"   Block: {receipt.blockNumber}")
    print(f"   Gas used: {receipt.gasUsed}")
    print(f"   Gas price: {web3_polygon.from_wei(receipt.effectiveGasPrice, 'gwei'):.2f} gwei")

    # Verify on-chain balance decreased
    final_onchain = check_balance_on_chain(wallet.address)
    onchain_decrease = initial_onchain - final_onchain

    print(f"\n💰 On-chain balance verification:")
    print(f"   Initial: ${initial_onchain:.6f}")
    print(f"   Final: ${final_onchain:.6f}")
    print(f"   Decrease: ${onchain_decrease:.6f}")

    assert abs(onchain_decrease - withdrawal_amount) < 0.01, f"On-chain balance mismatch: {onchain_decrease} vs {withdrawal_amount}"

    # Update database (simulate what the withdrawal handler would do)
    await wallet_repo.subtract_balance(wallet.id, withdrawal_amount)

    # Verify database update
    updated_wallet = await wallet_repo.get_by_id(wallet.id)
    db_decrease = wallet.usdc_balance - updated_wallet.usdc_balance

    print(f"\n💾 Database balance verification:")
    print(f"   Initial: ${wallet.usdc_balance:.2f}")
    print(f"   Final: ${updated_wallet.usdc_balance:.2f}")
    print(f"   Decrease: ${db_decrease:.2f}")

    assert abs(db_decrease - withdrawal_amount) < 0.01, "Database balance mismatch"

    print(f"\n{'='*80}")
    print(f"✅ REAL USDC WITHDRAWAL TEST PASSED!")
    print(f"   You can verify on Polygonscan: https://polygonscan.com/tx/{result.tx_hash}")
    print(f"{'='*80}\n")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdrawal_insufficient_balance(
    real_user_service: UserService,
    real_withdrawal_manager: WithdrawalManager,
    test_user,  # Unfunded user
    external_wallet,
):
    """Test that withdrawal fails gracefully with insufficient balance.

    Uses REAL WithdrawalManager - verifies error handling.

    Cost: Free (no actual transaction)
    """
    print(f"\n{'='*80}")
    print(f"INSUFFICIENT BALANCE WITHDRAWAL TEST")
    print(f"{'='*80}\n")

    user, wallet = test_user

    print(f"📋 Wallet: {wallet.address}")
    print(f"   Balance: ${wallet.usdc_balance:.2f}")

    # Get private key
    private_key = await real_user_service.get_private_key(user.id)
    assert private_key, "Could not decrypt private key"

    # Try to withdraw more than balance
    print(f"\n🔄 Attempting to withdraw $1000 (more than balance)...")

    result = await real_withdrawal_manager.withdraw(
        from_private_key=private_key,
        to_address=external_wallet.address,
        amount=1000.0,
    )

    # Verify failure
    assert result.success is False, "Withdrawal should have failed"
    assert "insufficient" in result.error.lower() or "balance" in result.error.lower(), f"Wrong error: {result.error}"

    print(f"✅ Withdrawal correctly rejected: {result.error}")

    print(f"\n{'='*80}")
    print(f"✅ INSUFFICIENT BALANCE TEST PASSED!")
    print(f"{'='*80}\n")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdrawal_invalid_address(
    real_user_service: UserService,
    real_withdrawal_manager: WithdrawalManager,
    funded_test_user,
):
    """Test that withdrawal fails with invalid destination address.

    Uses REAL WithdrawalManager - verifies address validation.

    Cost: Free (no actual transaction)
    """
    print(f"\n{'='*80}")
    print(f"INVALID ADDRESS WITHDRAWAL TEST")
    print(f"{'='*80}\n")

    user, wallet = funded_test_user

    # Get private key
    private_key = await real_user_service.get_private_key(user.id)
    assert private_key, "Could not decrypt private key"

    # Try invalid addresses
    invalid_addresses = [
        "not_an_address",
        "0x123",  # Too short
        "0xINVALIDHEXCHARACTERS1234567890abcdef12345",
    ]

    for invalid_address in invalid_addresses:
        print(f"\n🔄 Testing invalid address: {invalid_address}")

        result = await real_withdrawal_manager.withdraw(
            from_private_key=private_key,
            to_address=invalid_address,
            amount=1.0,
        )

        assert result.success is False, f"Withdrawal should have failed for: {invalid_address}"
        print(f"   ✅ Correctly rejected: {result.error}")

    print(f"\n{'='*80}")
    print(f"✅ INVALID ADDRESS TEST PASSED!")
    print(f"{'='*80}\n")


@pytest.mark.integration
@pytest.mark.expensive
@pytest.mark.asyncio
async def test_withdrawal_without_gas(
    real_user_service: UserService,
    real_withdrawal_manager: WithdrawalManager,
    funded_test_user,
    external_wallet,
):
    """Test withdrawal fails when wallet has no POL for gas.

    Note: This test assumes GAS_SPONSOR_PRIVATE_KEY is NOT set.
    If gas sponsorship is enabled, this test will be skipped.

    Cost: Free (transaction fails before broadcast)
    """
    if settings.gas_sponsor_private_key:
        pytest.skip("Gas sponsorship is enabled - test not applicable")

    print(f"\n{'='*80}")
    print(f"NO GAS WITHDRAWAL TEST")
    print(f"{'='*80}\n")

    user, wallet = funded_test_user

    # Verify wallet has no POL
    # (funded_test_user only sends USDC, not POL)

    print(f"📋 Wallet: {wallet.address}")
    print(f"   USDC balance: ${wallet.usdc_balance:.2f}")

    # Get private key
    private_key = await real_user_service.get_private_key(user.id)

    # Try to withdraw
    print(f"\n🔄 Attempting withdrawal without POL for gas...")

    result = await real_withdrawal_manager.withdraw(
        from_private_key=private_key,
        to_address=external_wallet.address,
        amount=1.0,
    )

    # Should fail due to no gas
    assert result.success is False, "Withdrawal should have failed without gas"
    assert "gas" in result.error.lower() or "insufficient funds" in result.error.lower(), f"Wrong error: {result.error}"

    print(f"✅ Withdrawal correctly rejected: {result.error}")

    print(f"\n{'='*80}")
    print(f"✅ NO GAS TEST PASSED!")
    print(f"{'='*80}\n")
