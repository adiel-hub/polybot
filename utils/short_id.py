"""Short ID generation for deep links."""

import hashlib


def generate_short_id(condition_id: str, length: int = 8) -> str:
    """
    Generate a short, URL-friendly ID from a condition_id.

    Uses SHA256 hash and takes first N characters for a short identifier.
    This creates deterministic short IDs - same condition_id always produces
    the same short ID.

    Args:
        condition_id: The full condition ID (e.g., "0x61b66d02...")
        length: Length of the short ID (default 8 characters)

    Returns:
        Short ID string (e.g., "a3f9k2p1")
    """
    # Remove 0x prefix if present
    clean_id = condition_id.lower()
    if clean_id.startswith("0x"):
        clean_id = clean_id[2:]

    # Create hash
    hash_obj = hashlib.sha256(clean_id.encode())
    hash_hex = hash_obj.hexdigest()

    # Take first N characters
    return hash_hex[:length]


def extract_condition_id_prefix(short_id: str) -> str:
    """
    Not used for lookup - just for documentation.
    Short IDs are hashes, not prefixes, so we can't reverse them.
    We'll need to search markets by trying to match the short_id.
    """
    return short_id
