# Alchemy Smart Wallet Costs vs Current EOA Implementation

## Overview

This document compares the costs of using **Alchemy Smart Wallets (Account Abstraction)** versus the current **EOA wallet + Polymarket relayer** implementation.

---

## Current Implementation: EOA + Polymarket Relayer

### Architecture
- **Wallet Type**: EOA (Externally Owned Account)
- **Generation**: eth-account library (free, local)
- **Approvals**: Polymarket's gasless relayer
- **Trading**: Polymarket CLOB API
- **Gas Costs**: $0 (Polymarket sponsors via relayer)

### Costs Breakdown

| Operation | Cost | Notes |
|-----------|------|-------|
| Wallet Creation | **$0** | Generated locally, no on-chain deployment |
| Token Approval (USDC) | **$0** | Via Polymarket relayer (gasless) |
| Market Order | **$0** | Via Polymarket relayer (gasless) |
| Limit Order | **$0** | Via Polymarket relayer (gasless) |
| Withdraw USDC | **~$0.01** | User pays gas (or bot sponsors with GAS_SPONSOR_PRIVATE_KEY) |
| **Monthly Cost** | **$0** | No recurring fees |

### Alchemy API Costs (Current Usage)
- **Webhooks**: Free tier (up to 100k/month)
- **RPC Calls**: Free tier (300M compute units/month)
- **Total Alchemy Cost**: **$0/month** for most use cases

---

## Alchemy Smart Wallets (Account Abstraction)

### Architecture
- **Wallet Type**: ERC-4337 Smart Contract Wallet
- **Deployment**: On-chain contract deployment
- **Approvals**: Bundled with first transaction
- **Trading**: Via UserOps (Account Abstraction)
- **Gas Costs**: Sponsored by Alchemy (with fees)

### Costs Breakdown

| Tier | Free | Pay-As-You-Go (PAYG) | Enterprise |
|------|------|---------------------|-----------|
| **Account Kit SDK** | ✅ Included | ✅ Included | ✅ Included |
| **Bundler API** | ✅ Included | ✅ Included | ✅ Included |
| **Gas Manager** | ⚠️ Testnet only | 8% admin fee | Custom fee |
| **Gas Sponsorship** | ❌ Not available | $25/month minimum | Custom pricing |
| **Admin API** | ❌ | ✅ | ✅ |
| **Support** | Community | Standard | Dedicated |

### Detailed Pricing (PAYG Tier)

#### Base Fees
- **Minimum**: $25/month for gas sponsorship
- **Admin Fee**: 8% on all gas sponsored transactions
- **Contract Deployment**: ~$0.26 per wallet (on Polygon)

#### Per-Transaction Costs (Estimated)

| Operation | Base Gas Cost | With 8% Admin Fee | Total |
|-----------|---------------|-------------------|-------|
| Wallet Deployment | $0.26 | +$0.02 | **$0.28** |
| Token Approval | $0.05 | +$0.004 | **$0.054** |
| Market Order | $0.10 | +$0.008 | **$0.108** |
| Limit Order | $0.08 | +$0.006 | **$0.086** |
| Withdraw USDC | $0.05 | +$0.004 | **$0.054** |

**Monthly Cost Example** (100 users, 10 trades each):
- 100 wallet deployments: $28.00
- 100 approvals: $5.40
- 1,000 trades (avg): $97.00
- **Total**: ~$130.40/month + $25 base fee = **$155.40/month**

### Cost Savings Claims

From Alchemy's marketing:
- **53% cheaper** wallet deployment vs competitors ($0.26 vs $0.56)
- **5-10% savings** on transaction costs vs other AA providers
- **Free for 2 years** for rollup deployments (~$80k value)
- **Up to $25k credits** via Everyone Onchain Fund

---

## Side-by-Side Comparison

### Monthly Costs (1000 Users, 10 Trades Each)

| Metric | Current (EOA + Polymarket) | Alchemy Smart Wallets | Difference |
|--------|---------------------------|----------------------|-----------|
| Wallet Creation | $0 | $280 | +$280 |
| Token Approvals | $0 | $54 | +$54 |
| 10,000 Trades | $0 | $970 | +$970 |
| **Base Monthly Fee** | **$0** | **$25** | **+$25** |
| **Total Monthly** | **$0** | **$1,329** | **+$1,329** |

### Annual Costs

| | Current | Alchemy Smart Wallets | Difference |
|---|---------|---------------------|-----------|
| **Year 1** | $0 | $15,948 | +$15,948 |

### Cost Per User

| Metric | Current | Alchemy Smart Wallets |
|--------|---------|---------------------|
| **Onboarding** | $0 | $0.28 |
| **Per Trade** | $0 | $0.10 |
| **Monthly Active** | $0 | $1.33 |

---

## Benefits of Alchemy Smart Wallets

Despite the higher costs, Alchemy Smart Wallets offer:

### 1. Batched Transactions ✅
```
EOA:
1. Approve USDC → Wait
2. Place Trade → Wait

Smart Wallet:
1. Approve + Trade → Done!
```

### 2. Social Recovery ✅
- No need to backup private keys
- Recover wallet via email/phone
- Better UX for non-crypto users

### 3. Session Keys ✅
- Auto-trade without signing each time
- Time-limited permissions
- Revokable access

### 4. Gasless Everything ✅
- No POL needed (current: same with Polymarket relayer)
- No user-facing gas fees
- Alchemy handles all gas

### 5. Better Developer Experience ✅
- Native Account Abstraction support
- Built-in gas sponsorship
- Better monitoring and analytics

---

## When Alchemy Smart Wallets Make Sense

### ✅ Good For:
1. **High-value users** - Premium features justify cost
2. **Social login** - Email/phone onboarding instead of seed phrases
3. **Non-crypto users** - Abstract away blockchain complexity
4. **Subscription models** - Pass costs to users ($0.10/trade fee)
5. **Enterprise clients** - Negotiated pricing, dedicated support

### ❌ Not Ideal For:
1. **Free trading apps** - Current $0 cost is better
2. **High-frequency traders** - Costs add up quickly
3. **Bootstrap phase** - $1,329/month for 1,000 users
4. **Margin-sensitive** - Every $0.10 matters

---

## Recommendations

### Option 1: Keep Current Implementation ✅ (Recommended)

**Pros**:
- ✅ $0 cost
- ✅ Already working
- ✅ Polymarket relayer is gasless
- ✅ Simpler architecture
- ✅ No vendor lock-in

**Cons**:
- ❌ No social recovery
- ❌ No session keys
- ❌ Users need to backup keys

**Best for**:
- Current phase (growth, validation)
- Cost-sensitive operations
- Crypto-native users

### Option 2: Hybrid Approach

**Implementation**:
- Default: EOA wallets (current)
- Premium: Alchemy Smart Wallets ($5/month subscription)
- User choice during onboarding

**Pricing Model**:
```
Free Tier: EOA wallets ($0 cost)
Premium: Smart wallets ($5/month covers Alchemy costs)
  - Social recovery
  - Auto-trade session keys
  - Priority support
```

### Option 3: Full Migration to Smart Wallets

**Only if**:
1. Secured VC funding
2. $25k Alchemy credits obtained
3. Premium subscription model ($10/month)
4. Enterprise customers (B2B)

**Minimum Revenue Needed**:
- $1,329/month ÷ 1,000 users = $1.33/user/month
- Charge $5/month = $3.67 profit per user
- Need 286 paying users to break even

---

## Cost Calculator

### Monthly Costs Formula

```python
def calculate_alchemy_costs(
    num_users: int,
    trades_per_user: int,
) -> dict:
    """Calculate monthly Alchemy Smart Wallet costs."""

    # Deployment
    wallet_deployments = num_users * 0.28

    # Approvals (assume each user needs 1)
    approvals = num_users * 0.054

    # Trades
    total_trades = num_users * trades_per_user
    trading_costs = total_trades * 0.10

    # Base fee
    base_fee = 25.00

    total = wallet_deployments + approvals + trading_costs + base_fee

    return {
        "wallet_deployments": wallet_deployments,
        "approvals": approvals,
        "trading_costs": trading_costs,
        "base_fee": base_fee,
        "total": total,
        "cost_per_user": total / num_users if num_users > 0 else 0,
    }

# Example: 500 users, 20 trades each
costs = calculate_alchemy_costs(500, 20)
# Output:
# {
#   "wallet_deployments": $140.00,
#   "approvals": $27.00,
#   "trading_costs": $1,000.00,
#   "base_fee": $25.00,
#   "total": $1,192.00,
#   "cost_per_user": $2.38
# }
```

### Break-Even Analysis

To justify Alchemy Smart Wallets with a **$5/month subscription**:

| Users | Monthly Cost | Revenue ($5/user) | Profit/Loss |
|-------|-------------|-------------------|-------------|
| 100 | $155 | $500 | +$345 ✅ |
| 500 | $1,192 | $2,500 | +$1,308 ✅ |
| 1,000 | $1,329 | $5,000 | +$3,671 ✅ |

**Conclusion**: Even at $5/month, Alchemy Smart Wallets are profitable with 100+ paying users.

---

## Alchemy Credits & Discounts

### 1. Everyone Onchain Fund
- **Up to $25k in credits**
- Application: https://www.alchemy.com/blog/everyone-onchain-fund
- Eligibility: Startups, builders, developers

### 2. Rollup Integration
- **Free for 2 years** (~$80k value)
- For apps building on custom rollups
- Includes smart wallet infrastructure

### 3. Volume Discounts
- **60%+ savings** at scale
- Negotiated with Enterprise tier
- Based on usage volume

### 4. Startup Program
- Potential free tier extensions
- Technical support
- Architecture consulting

---

## Implementation Comparison

### Current (EOA + Polymarket Relayer)

```python
# Wallet creation
address, private_key = WalletGenerator.create_wallet()  # Free, local
encrypted_key, salt = encryption.encrypt(private_key)
await wallet_repo.create(address, encrypted_key, salt)

# Trading
client = PolymarketCLOB(private_key, funder_address)
await client.set_allowance()  # Free, via Polymarket relayer
result = await client.place_market_order()  # Free, via relayer
```

### With Alchemy Smart Wallets

```python
# Wallet creation (costs $0.28)
from alchemy import AccountKitClient

client = AccountKitClient(api_key=settings.alchemy_api_key)
wallet = await client.create_account()  # Deployed on-chain
await wallet_repo.create(wallet.address, wallet.owner)

# Trading (costs $0.10 per trade)
# Approval + Trade batched in single UserOp
user_op = await wallet.batch([
    wallet.approve(USDC, CLOB_CONTRACT),
    wallet.trade(token_id, amount)
])
result = await client.send_user_operation(user_op)  # Sponsored gas
```

---

## Resources

- [Alchemy Smart Wallets](https://www.alchemy.com/smart-wallets)
- [Account Kit Documentation](https://www.alchemy.com/account-kit)
- [Pricing Calculator](https://wallet-calculator.alchemy.com/)
- [Cost Savings Blog](https://www.alchemy.com/blog/the-most-affordable-smart-wallet)
- [Everyone Onchain Fund](https://www.alchemy.com/blog/everyone-onchain-fund)
- [Pricing Plans](https://www.alchemy.com/docs/reference/pricing-plans)

---

## Conclusion

### Current Recommendation: **Keep EOA Wallets** ✅

**Reasoning**:
1. **$0 cost** vs $1,329/month for 1,000 users
2. **Already working** with Polymarket's gasless relayer
3. **Simpler architecture** - less complexity
4. **No vendor lock-in** - not dependent on Alchemy pricing
5. **Same UX** - users get gasless approvals anyway

### Future Consideration: **Hybrid Approach**

Once you have:
- ✅ 500+ paying users ($5/month subscription)
- ✅ Product-market fit validated
- ✅ $25k Alchemy credits secured
- ✅ Premium tier demand proven

Then offer:
- **Free Tier**: EOA wallets (current)
- **Premium Tier**: Smart wallets with social recovery

---

## Summary

| Aspect | Current (EOA) | Alchemy Smart Wallets |
|--------|--------------|---------------------|
| **Monthly Cost** | $0 | $25-$1,329+ |
| **Per User Cost** | $0 | $1.33-$2.38 |
| **Deployment** | Free (local) | $0.28 |
| **Per Trade** | $0 (Polymarket relayer) | $0.10 |
| **Complexity** | Low | Medium |
| **Social Recovery** | ❌ | ✅ |
| **Session Keys** | ❌ | ✅ |
| **Vendor Lock-in** | None | Alchemy |
| **Best For** | Early stage, free apps | Premium features, enterprise |

**Bottom Line**: Stick with current EOA implementation. Alchemy Smart Wallets are excellent but not cost-justified until you have paying users and premium feature demand.
