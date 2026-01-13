# PolyBot Admin Panel

Comprehensive admin panel for managing and monitoring the PolyBot Telegram trading bot.

## Features

### 📊 Dashboard
- Total users (active/inactive count)
- Total USDC balance across all wallets
- Open orders count
- Active positions count
- Real-time system health indicators

### 👥 User Management
- Paginated user list with search
- View detailed user information:
  - Wallet address and balance
  - Active positions and orders
  - User settings
  - Trading history
- Suspend/activate user accounts
- Navigate directly to user's orders or positions

### 📋 Order Management
- List all orders with status filters:
  - Pending
  - Open
  - Filled
  - Cancelled
  - Failed
- View detailed order information
- Cancel orders on behalf of users
- Pagination support

### 🎯 Position Management
- List all positions across all users
- View position details with P&L calculations
- Access to user information from position view
- Pagination support

### 🛑 Stop Loss Management
- View all active stop losses
- Detailed stop loss information:
  - Trigger price
  - Sell percentage
  - Associated position
- Deactivate stop losses when needed

### 👥 Copy Trading Management
- List all copy trading subscriptions
- View trader statistics:
  - Trader name/address
  - Total P&L
  - Active status
- Deactivate subscriptions
- View follower details

### 💰 Wallet & Financial Management
- List all wallets with balances
- Comprehensive deposit history with pagination
- Withdrawal history tracking
- Financial summary:
  - Total deposits
  - Total withdrawals
  - Current total balance

### ⚙️ System Monitoring
- WebSocket connection health status
- Polymarket API connectivity checks
- Database statistics and health
- Component status indicators

### 🔧 System Settings
- Toggle system-wide features:
  - Maintenance mode
  - New user registrations
  - Copy trading feature
  - Stop loss feature
- Easy on/off toggles for each setting

### 📢 Broadcast Messages
- Compose messages to users
- Target specific user groups:
  - All users
  - Active users only
  - Users with balance
- Preview before sending
- Batch delivery with progress tracking
- Rate limiting to avoid Telegram API limits

## Setup

### 1. Configure Admin Access

Add your Telegram user ID to the `.env` file:

```bash
# Get your Telegram user ID by messaging @userinfobot on Telegram
ADMIN_TELEGRAM_IDS=123456789,987654321
```

You can add multiple admin user IDs separated by commas.

### 2. Start the Bot

The admin panel is automatically loaded when you run the bot:

```bash
python run.py
```

### 3. Access Admin Panel

Send `/admin` command to the bot in Telegram. Only users with IDs listed in `ADMIN_TELEGRAM_IDS` will have access.

## Architecture

### File Structure

```
admin/
├── __init__.py              # Module exports
├── config.py                # Admin IDs, pagination settings
├── states.py                # Conversation states
├── application.py           # ConversationHandler factory
├── handlers/                # UI handlers for each feature
│   ├── start.py            # Entry point and main menu
│   ├── dashboard.py        # Dashboard stats
│   ├── users.py            # User management
│   ├── orders.py           # Order management
│   ├── positions.py        # Position management
│   ├── stop_loss.py        # Stop loss management
│   ├── copy_trading.py     # Copy trading management
│   ├── wallets.py          # Financial management
│   ├── system.py           # System monitoring
│   ├── settings.py         # System settings
│   └── broadcast.py        # Broadcast messages
├── services/                # Business logic
│   ├── admin_service.py    # Admin CRUD operations
│   ├── stats_service.py    # Statistics aggregation
│   └── broadcast_service.py # Message broadcasting
├── keyboards/               # Telegram keyboard builders
│   ├── menus.py            # Admin menu keyboards
│   └── pagination.py       # Pagination utilities
└── utils/                   # Utilities
    ├── decorators.py       # @admin_only decorator
    └── formatters.py       # Display formatters
```

### Key Patterns

**Authentication**: All admin handlers use the `@admin_only` decorator which verifies the user's Telegram ID against the whitelist.

**Callback Data Convention**: All admin callbacks are prefixed with `admin_`:
- `admin_dashboard` - Dashboard view
- `admin_users` - User list
- `admin_user_{id}` - Specific user
- `admin_orders_filter_{status}` - Order filter
- `admin_page_{section}_{page}` - Pagination

**State Management**: Separate `AdminState` enum manages the admin conversation flow independently from the main bot conversation.

**Service Layer**: Admin-specific services handle:
- Complex aggregations across multiple repositories
- Statistics calculations
- Broadcast message delivery

## Configuration

### `admin/config.py`

```python
# Pagination
ITEMS_PER_PAGE = 10  # Items per page in lists

# Broadcast
BROADCAST_BATCH_SIZE = 50  # Messages per batch
BROADCAST_DELAY = 0.1  # Seconds between messages
```

### System Settings

System-wide settings are stored in `context.bot_data["system_settings"]` and include:
- `maintenance_mode` - Disable trading for all users
- `new_registrations` - Allow new user registrations
- `copy_trading_enabled` - Enable/disable copy trading
- `stop_loss_enabled` - Enable/disable stop loss feature

## Security

### Admin Authentication

- Admin access is restricted by Telegram user ID whitelist
- No passwords or tokens needed
- IDs are loaded from environment variable
- Failed authentication attempts are logged

### Safety Features

- Confirmation prompts for destructive actions
- All admin actions are logged
- Read-only operations for most features
- Broadcast preview before sending

## UI Design

All admin UI follows the PolyBot emoji convention for consistency:

```
Navigation:  🔐 Admin  🏠 Menu  🔙 Back  ❌ Close  🔄 Refresh
Dashboard:   📊 Stats  👥 Users  📈 Volume  💰 Balance
Users:       👤 User   🔍 Search  ⛔ Suspend  ✅ Activate
Orders:      📋 Orders  ❌ Cancel  📊 Filter
Positions:   🎯 Positions  📉 Close  💹 P&L
System:      ⚙️ System  🔌 WebSocket  🌐 API  💾 Database
Broadcast:   📢 Broadcast  ✉️ Message  📤 Send
```

## Development

### Adding New Admin Features

1. **Create handler** in `admin/handlers/your_feature.py`
2. **Add state** to `admin/states.py`
3. **Wire handler** in `admin/application.py`
4. **Add menu button** in `admin/handlers/start.py`
5. **Test thoroughly**

### Testing Admin Features

```bash
# Run all tests
pytest

# Test specific admin functionality
pytest tests/test_admin/ -v
```

## Troubleshooting

### "Unauthorized access" message
- Verify your Telegram user ID is in `ADMIN_TELEGRAM_IDS`
- Check `.env` file is loaded correctly
- Restart the bot after changing admin IDs

### Commands not working
- Ensure bot is running (`python run.py`)
- Check logs for errors
- Verify database is accessible

### Broadcast not sending
- Check Telegram API rate limits
- Verify user count and batch settings
- Review logs for delivery errors

## Future Enhancements

Potential additions for future versions:
- Export data as CSV/JSON
- Advanced analytics and charts
- Audit log viewer
- Database backup/restore
- Performance metrics dashboard
- Admin action history
- Role-based admin permissions
- Scheduled broadcasts

## Support

For issues or questions:
1. Check logs in the console
2. Review `.env` configuration
3. Ensure all dependencies are installed
4. Check database connectivity

## License

Part of the PolyBot project. See main README for license information.
