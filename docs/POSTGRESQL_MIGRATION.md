# PostgreSQL Migration Guide

This document explains the migration from SQLite to PostgreSQL and how to deploy with the new database.

## Overview

PolyBot has been migrated from SQLite (aiosqlite) to PostgreSQL (asyncpg) for improved scalability and cloud deployment on Render.

### Why PostgreSQL?

- **Cloud-Ready**: Seamless integration with Render and other platforms
- **Scalability**: Connection pooling handles 10,000+ concurrent users
- **Reliability**: Managed database with automatic backups
- **Performance**: Better suited for high-traffic applications
- **Cost-Effective**: $7/month for 256MB on Render

## What Changed

### Database Driver
- **Before**: `aiosqlite` (SQLite async driver)
- **After**: `asyncpg` (PostgreSQL async driver)

### Connection
- **Before**: File-based SQLite database (`./data/polybot.db`)
- **After**: PostgreSQL connection URL with connection pooling

### Schema Changes
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `BLOB` → `BYTEA` (for binary data like encrypted keys)
- `INTEGER` → `BIGINT` (for Telegram IDs)
- Boolean `0`/`1` → `TRUE`/`FALSE`

### Query Syntax
- Parameter placeholders: `?` → `$1, $2, $3...`
- Insert with ID: `cursor.lastrowid` → `RETURNING id`
- Transactions: `conn.commit()` → auto-commit (asyncpg default)

## Migration Steps

### 1. For Local Development

If you're currently using SQLite and want to test PostgreSQL locally:

```bash
# Install PostgreSQL (macOS)
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb polybot

# Set environment variable
export DATABASE_URL="postgresql://localhost:5432/polybot"

# Migrate existing data
python scripts/migrate_sqlite_to_postgresql.py

# Verify migration
python scripts/migrate_sqlite_to_postgresql.py verify

# Run bot with PostgreSQL
python run_all.py
```

### 2. For Render Deployment

The bot is already configured for Render PostgreSQL deployment:

**Step 1**: Push code to GitHub
```bash
git push origin main
```

**Step 2**: Deploy to Render
- Go to [Render Dashboard](https://dashboard.render.com/)
- Create new Web Service from your GitHub repo
- Render will automatically:
  - Create the PostgreSQL database (defined in `render.yaml`)
  - Set `DATABASE_URL` environment variable
  - Run `pip install -r requirements.txt` (installs asyncpg)
  - Initialize empty database tables on first run

**Step 3**: Set Environment Variables
Configure these in Render dashboard (Settings → Environment):
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `MASTER_ENCRYPTION_KEY` - Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `POLYGON_RPC_URL` - Polygon RPC endpoint
- `ALCHEMY_WEBHOOK_SIGNING_KEY` - For deposit webhooks
- `ALCHEMY_WEBHOOK_ID` - Webhook ID
- `ALCHEMY_AUTH_TOKEN` - Alchemy API auth token
- `GAS_SPONSOR_PRIVATE_KEY` - Wallet with POL for gas
- All other bot tokens and API keys from `.env.example`

**Note**: `DATABASE_URL` is automatically set by Render when you add the PostgreSQL database.

### 3. Migrating Existing Data to Render

If you have existing SQLite data you want to move to Render PostgreSQL:

**Option A**: Direct migration (requires network access to Render DB)
```bash
# Get DATABASE_URL from Render dashboard
export DATABASE_URL="postgresql://user:pass@hostname.render.com/database"

# Run migration
python scripts/migrate_sqlite_to_postgresql.py
```

**Option B**: Export/Import approach
```bash
# 1. Export from SQLite to SQL dump
sqlite3 ./data/polybot.db .dump > backup.sql

# 2. Connect to Render PostgreSQL and import
# (Use psql or Render's shell access)
psql $DATABASE_URL < backup.sql
```

## Database Schema

The migration script handles creating all tables with PostgreSQL syntax. Tables include:

- `users` - User accounts with settings and referrals
- `wallets` - Smart contract wallets with encrypted keys
- `orders` - Trading order history
- `positions` - Active market positions
- `stop_loss_orders` - Stop loss configurations
- `price_alerts` - Price notification settings
- `copy_traders` - Copy trading subscriptions
- `referral_commissions` - Referral earnings tracking
- Additional tables for news bot and features

## Connection Pooling

PostgreSQL uses connection pooling for optimal performance:

```python
# Configuration in database/connection.py
pool = await asyncpg.create_pool(
    database_url,
    min_size=2,   # Minimum connections kept open
    max_size=10,  # Maximum concurrent connections
)
```

This allows the bot to handle multiple concurrent users efficiently without opening/closing connections for every query.

## Troubleshooting

### Connection Issues

**Error**: "password authentication failed"
- Check `DATABASE_URL` format: `postgresql://username:password@host:5432/database`
- Verify credentials in Render dashboard

**Error**: "could not connect to server"
- Ensure PostgreSQL database is running in Render
- Check firewall/network settings

### Migration Issues

**Error**: "relation does not exist"
- Database tables not created yet
- Run the bot once to initialize: `python run_all.py`
- Or manually run: `python -c "from database.connection import Database; import asyncio; asyncio.run(Database('$DATABASE_URL').initialize())"`

**Error**: "duplicate key value violates unique constraint"
- Data already exists in PostgreSQL
- Use `ON CONFLICT DO NOTHING` in migration script (already included)

### Performance Issues

If you notice slow queries:
- Check connection pool size in `database/connection.py`
- Monitor database metrics in Render dashboard
- Consider upgrading database plan if needed

## Cost Breakdown

**Render PostgreSQL Pricing**:
- **Starter Plan**: 256MB RAM, 1GB storage - $7/month
  - Suitable for: 10,000+ users
  - Includes: Daily backups, 99.9% uptime

- **Standard Plan**: 4GB RAM, 10GB storage - $25/month
  - Suitable for: 100,000+ users
  - Includes: Point-in-time recovery, high availability

The starter plan ($7/mo) is more than sufficient for most use cases.

## Rollback to SQLite

If you need to rollback to SQLite (not recommended for production):

1. Change `requirements.txt`: `asyncpg` → `aiosqlite`
2. Revert `config/settings.py`: `database_url` → `database_path`
3. Revert `database/connection.py` to SQLite version
4. Update all repositories to use SQLite syntax
5. Revert `render.yaml` to remove PostgreSQL database

Or simply checkout the commit before migration:
```bash
git checkout 71f682a  # Commit before PostgreSQL migration
```

## Additional Resources

- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Render PostgreSQL Guide](https://render.com/docs/databases)
- [Database Connection Pooling Best Practices](https://wiki.postgresql.org/wiki/Number_Of_Database_Connections)

## Support

If you encounter issues during migration:
1. Check Render deployment logs
2. Verify all environment variables are set correctly
3. Review the migration script output for errors
4. Open an issue on GitHub with error details
