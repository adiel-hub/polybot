"""Real-time blockchain balance queries for USDC.e."""

import logging
from typing import Optional

from web3 import Web3

from config import settings
from config.constants import USDC_E_ADDRESS, USDC_DECIMALS

logger = logging.getLogger(__name__)

# Minimal ERC20 ABI for balanceOf
ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]


class BalanceService:
    """Service for querying real-time USDC.e balances from blockchain."""

    def __init__(self, rpc_url: str = None):
        """
        Initialize balance service.

        Args:
            rpc_url: Polygon RPC URL (defaults to settings)
        """
        self.rpc_url = rpc_url or settings.polygon_rpc_url
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # USDC.e contract (Polymarket uses this)
        self.usdc_e_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E_ADDRESS),
            abi=ERC20_BALANCE_ABI,
        )

    def get_balance(self, address: str) -> float:
        """
        Get USDC.e balance for an address.

        Args:
            address: Wallet address

        Returns:
            Balance in USDC.e (as float, e.g., 21.50)
        """
        try:
            balance_raw = self.usdc_e_contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()

            # Convert from smallest unit to USDC
            balance = balance_raw / (10 ** USDC_DECIMALS)

            logger.debug(f"Balance for {address[:10]}...: ${balance:.2f} USDC.e")
            return balance

        except Exception as e:
            logger.error(f"Failed to get balance for {address[:10]}...: {e}")
            return 0.0

    async def get_balance_async(self, address: str) -> float:
        """
        Async wrapper for get_balance.

        Args:
            address: Wallet address

        Returns:
            Balance in USDC.e
        """
        # web3.py calls are synchronous, but we wrap for consistency
        return self.get_balance(address)

    def has_sufficient_balance(self, address: str, required_amount: float) -> bool:
        """
        Check if address has sufficient USDC.e balance.

        Args:
            address: Wallet address
            required_amount: Required amount in USDC

        Returns:
            True if balance >= required_amount
        """
        current_balance = self.get_balance(address)
        return current_balance >= required_amount


# Global instance (lazy-initialized)
_balance_service: Optional[BalanceService] = None


def get_balance_service() -> BalanceService:
    """Get or create global BalanceService instance."""
    global _balance_service
    if _balance_service is None:
        _balance_service = BalanceService()
    return _balance_service
