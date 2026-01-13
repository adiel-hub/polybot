"""Tests for referral service."""

import pytest
import asyncio
from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.referral_repo import ReferralRepository


@pytest.fixture
async def db():
    """Create test database."""
    database = Database(':memory:')
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user_repo(db):
    """Create user repository."""
    return UserRepository(db)


@pytest.fixture
async def referral_repo(db):
    """Create referral repository."""
    return ReferralRepository(db)


@pytest.mark.asyncio
async def test_referral_chain_creation(user_repo, referral_repo):
    """Test creating a 3-tier referral chain."""
    # Create 4 users in a chain
    user1 = await user_repo.create(telegram_id=1001, telegram_username='user1')
    user2 = await user_repo.create(telegram_id=1002, telegram_username='user2')
    user3 = await user_repo.create(telegram_id=1003, telegram_username='user3')
    user4 = await user_repo.create(telegram_id=1004, telegram_username='user4')

    # Set referral codes
    await user_repo.set_referral_code(user1.id, 'code001')
    await user_repo.set_referral_code(user2.id, 'code002')
    await user_repo.set_referral_code(user3.id, 'code003')

    # Link referrals: 1 <- 2 <- 3 <- 4
    await user_repo.set_referrer(user2.id, user1.id)
    await user_repo.set_referrer(user3.id, user2.id)
    await user_repo.set_referrer(user4.id, user3.id)

    # Test referral chain retrieval
    chain = await referral_repo.get_referral_chain(user4.id)

    assert len(chain) == 3, 'Expected 3-tier chain'
    assert chain[0] == (user3.id, 1), 'Tier 1 should be user3'
    assert chain[1] == (user2.id, 2), 'Tier 2 should be user2'
    assert chain[2] == (user1.id, 3), 'Tier 3 should be user1'


@pytest.mark.asyncio
async def test_commission_calculation(user_repo, referral_repo):
    """Test commission calculation for 3 tiers."""
    # Create users
    user1 = await user_repo.create(telegram_id=2001, telegram_username='user1')
    user2 = await user_repo.create(telegram_id=2002, telegram_username='user2')
    user3 = await user_repo.create(telegram_id=2003, telegram_username='user3')
    user4 = await user_repo.create(telegram_id=2004, telegram_username='user4')

    # Set referral codes
    await user_repo.set_referral_code(user1.id, 'abc123')
    await user_repo.set_referral_code(user2.id, 'def456')
    await user_repo.set_referral_code(user3.id, 'ghi789')

    # Link referrals
    await user_repo.set_referrer(user2.id, user1.id)
    await user_repo.set_referrer(user3.id, user2.id)
    await user_repo.set_referrer(user4.id, user3.id)

    # Simulate $100 trade by user4
    trade_amount = 100.0
    trade_fee = trade_amount * 0.005  # $0.50

    # Create commission records
    await referral_repo.create_commission(
        referrer_id=user3.id, referee_id=user4.id, order_id=1,
        tier=1, trade_amount=trade_amount, trade_fee=trade_fee,
        commission_rate=0.25, commission_amount=trade_fee * 0.25  # $0.125
    )
    await referral_repo.create_commission(
        referrer_id=user2.id, referee_id=user4.id, order_id=1,
        tier=2, trade_amount=trade_amount, trade_fee=trade_fee,
        commission_rate=0.05, commission_amount=trade_fee * 0.05  # $0.025
    )
    await referral_repo.create_commission(
        referrer_id=user1.id, referee_id=user4.id, order_id=1,
        tier=3, trade_amount=trade_amount, trade_fee=trade_fee,
        commission_rate=0.03, commission_amount=trade_fee * 0.03  # $0.015
    )

    # Add to commission balances
    await user_repo.add_commission_balance(user3.id, 0.125)
    await user_repo.add_commission_balance(user2.id, 0.025)
    await user_repo.add_commission_balance(user1.id, 0.015)

    # Verify balances
    user1 = await user_repo.get_by_id(user1.id)
    user2 = await user_repo.get_by_id(user2.id)
    user3 = await user_repo.get_by_id(user3.id)

    assert abs(user3.commission_balance - 0.125) < 0.001, 'Tier 1 commission incorrect'
    assert abs(user2.commission_balance - 0.025) < 0.001, 'Tier 2 commission incorrect'
    assert abs(user1.commission_balance - 0.015) < 0.001, 'Tier 3 commission incorrect'

    # Verify total earned
    assert abs(user3.total_earned - 0.125) < 0.001
    assert abs(user2.total_earned - 0.025) < 0.001
    assert abs(user1.total_earned - 0.015) < 0.001


@pytest.mark.asyncio
async def test_claim_commission(user_repo):
    """Test commission claiming."""
    user = await user_repo.create(telegram_id=3001, telegram_username='testuser')

    # Add commission balance
    await user_repo.add_commission_balance(user.id, 10.50)

    # Verify balance added
    user = await user_repo.get_by_id(user.id)
    assert abs(user.commission_balance - 10.50) < 0.001
    assert abs(user.total_earned - 10.50) < 0.001
    assert user.total_claimed == 0.0

    # Claim $5.00
    success = await user_repo.claim_commission(user.id, 5.00)
    assert success is True

    # Verify balances updated
    user = await user_repo.get_by_id(user.id)
    assert abs(user.commission_balance - 5.50) < 0.001  # 10.50 - 5.00
    assert abs(user.total_earned - 10.50) < 0.001  # Unchanged
    assert abs(user.total_claimed - 5.00) < 0.001  # 5.00 claimed

    # Try to claim more than balance
    success = await user_repo.claim_commission(user.id, 10.00)
    assert success is False  # Should fail

    # Balance unchanged
    user = await user_repo.get_by_id(user.id)
    assert abs(user.commission_balance - 5.50) < 0.001


@pytest.mark.asyncio
async def test_referral_stats(user_repo, referral_repo):
    """Test referral statistics calculation."""
    # Create referral network
    root = await user_repo.create(telegram_id=4001, telegram_username='root')

    # Tier 1 referrals (2 users)
    t1_user1 = await user_repo.create(telegram_id=4002, telegram_username='t1_1')
    t1_user2 = await user_repo.create(telegram_id=4003, telegram_username='t1_2')
    await user_repo.set_referrer(t1_user1.id, root.id)
    await user_repo.set_referrer(t1_user2.id, root.id)

    # Tier 2 referrals (3 users)
    t2_user1 = await user_repo.create(telegram_id=4004, telegram_username='t2_1')
    t2_user2 = await user_repo.create(telegram_id=4005, telegram_username='t2_2')
    t2_user3 = await user_repo.create(telegram_id=4006, telegram_username='t2_3')
    await user_repo.set_referrer(t2_user1.id, t1_user1.id)
    await user_repo.set_referrer(t2_user2.id, t1_user1.id)
    await user_repo.set_referrer(t2_user3.id, t1_user2.id)

    # Tier 3 referrals (1 user)
    t3_user1 = await user_repo.create(telegram_id=4007, telegram_username='t3_1')
    await user_repo.set_referrer(t3_user1.id, t2_user1.id)

    # Get stats
    stats = await referral_repo.get_referral_stats(root.id)

    assert stats['referral_counts']['t1'] == 2, 'Should have 2 Tier 1 referrals'
    assert stats['referral_counts']['t2'] == 3, 'Should have 3 Tier 2 referrals'
    assert stats['referral_counts']['t3'] == 1, 'Should have 1 Tier 3 referral'
    assert stats['total_referrals'] == 6, 'Should have 6 total referrals'
