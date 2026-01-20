#!/usr/bin/env python3
"""
Diagnostic script to check on-chain approval status for a Safe wallet.

Usage:
    python scripts/check_wallet_approvals.py <wallet_address>
    python scripts/check_wallet_approvals.py  # Uses default test wallet
"""

import asyncio
import sys
from web3 import Web3

# Contract addresses
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

USDC_SPENDERS = [
    ("CTF Exchange", CTF_EXCHANGE_ADDRESS),
    ("Neg Risk CTF", NEG_RISK_CTF_ADDRESS),
    ("Neg Risk Adapter", NEG_RISK_ADAPTER_ADDRESS),
]

CTF_OPERATORS = [
    ("CTF Exchange", CTF_EXCHANGE_ADDRESS),
    ("Neg Risk CTF", NEG_RISK_CTF_ADDRESS),
    ("Neg Risk Adapter", NEG_RISK_ADAPTER_ADDRESS),
]

# ABIs
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
]

ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
]


import time

def rate_limited_call(fn, max_retries=3, delay=2):
    """Execute RPC call with rate limit handling."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                print(f"    (Rate limited, waiting {delay}s...)")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise


def check_safe_deployed(w3: Web3, address: str) -> bool:
    """Check if Safe wallet is deployed (has contract code)."""
    code = rate_limited_call(
        lambda: w3.eth.get_code(Web3.to_checksum_address(address))
    )
    return len(code) > 0


def check_usdc_balance(w3: Web3, usdc_contract, address: str) -> float:
    """Check USDC balance."""
    balance = rate_limited_call(
        lambda: usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
    )
    return balance / 10**6


def check_usdc_allowance(w3: Web3, usdc_contract, owner: str, spender: str) -> int:
    """Check USDC allowance."""
    return rate_limited_call(
        lambda: usdc_contract.functions.allowance(
            Web3.to_checksum_address(owner),
            Web3.to_checksum_address(spender),
        ).call()
    )


def check_ctf_approval(w3: Web3, ctf_contract, owner: str, operator: str) -> bool:
    """Check CTF operator approval."""
    return rate_limited_call(
        lambda: ctf_contract.functions.isApprovedForAll(
            Web3.to_checksum_address(owner),
            Web3.to_checksum_address(operator),
        ).call()
    )


def main():
    # Get wallet address from args or use default
    if len(sys.argv) > 1:
        wallet_address = sys.argv[1]
    else:
        wallet_address = "0x5b56B3871cbcDad6282A5E6f181b3AD5F9758185"  # Default test wallet

    print(f"\n{'='*60}")
    print(f"Checking on-chain status for wallet: {wallet_address}")
    print(f"{'='*60}\n")

    # Load RPC URL from environment or use default
    import os
    from dotenv import load_dotenv
    load_dotenv()

    rpc_url = os.getenv("POLYGON_RPC_URL")
    if not rpc_url:
        print("Error: POLYGON_RPC_URL not set in environment")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print("Error: Could not connect to Polygon RPC")
        sys.exit(1)

    # Create contract instances
    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    ctf_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=ERC1155_ABI,
    )

    # Check Safe deployment
    is_deployed = check_safe_deployed(w3, wallet_address)
    print(f"Safe Deployed: {'✅ YES' if is_deployed else '❌ NO'}")

    # Check USDC balance
    balance = check_usdc_balance(w3, usdc_contract, wallet_address)
    print(f"USDC Balance: ${balance:.2f}")
    print()

    # Check USDC allowances
    print("USDC Allowances:")
    print("-" * 40)
    all_usdc_approved = True
    for name, spender in USDC_SPENDERS:
        allowance = check_usdc_allowance(w3, usdc_contract, wallet_address, spender)
        if allowance > 0:
            if allowance >= 2**200:  # Near unlimited
                status = "✅ UNLIMITED"
            else:
                status = f"✅ {allowance / 10**6:.2f} USDC"
        else:
            status = "❌ ZERO"
            all_usdc_approved = False
        print(f"  {name}: {status}")
    print()

    # Check CTF operator approvals
    print("CTF Operator Approvals:")
    print("-" * 40)
    all_ctf_approved = True
    for name, operator in CTF_OPERATORS:
        is_approved = check_ctf_approval(w3, ctf_contract, wallet_address, operator)
        if is_approved:
            status = "✅ APPROVED"
        else:
            status = "❌ NOT APPROVED"
            all_ctf_approved = False
        print(f"  {name}: {status}")
    print()

    # Summary
    print("=" * 60)
    total_approvals = len(USDC_SPENDERS) + len(CTF_OPERATORS)
    passed = sum(1 for _, s in USDC_SPENDERS if check_usdc_allowance(w3, usdc_contract, wallet_address, s) > 0)
    passed += sum(1 for _, o in CTF_OPERATORS if check_ctf_approval(w3, ctf_contract, wallet_address, o))

    if all_usdc_approved and all_ctf_approved:
        print("✅ ALL 6 APPROVALS SET - Ready for trading")
    else:
        print(f"❌ MISSING APPROVALS: {passed}/{total_approvals} approved")
        print("\nTo fix, the bot needs to run setup_all_allowances() for this wallet.")
    print("=" * 60)


if __name__ == "__main__":
    main()
