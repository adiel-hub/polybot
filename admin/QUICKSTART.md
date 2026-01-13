# Admin Panel Quick Start Guide

Get started with the PolyBot admin panel in 3 simple steps!

## Step 1: Get Your Telegram User ID

1. Open Telegram
2. Search for `@userinfobot`
3. Send `/start` to the bot
4. Copy your user ID (it will be a number like `123456789`)

## Step 2: Configure Admin Access

Add your Telegram user ID to the `.env` file:

```bash
# Open .env file
nano .env

# Add this line (replace with your actual user ID)
ADMIN_TELEGRAM_IDS=123456789

# For multiple admins, separate with commas
ADMIN_TELEGRAM_IDS=123456789,987654321,555666777
```

Save the file and restart the bot:

```bash
python run.py
```

## Step 3: Access the Admin Panel

1. Open your Telegram bot
2. Send the command: `/admin`
3. You'll see the admin main menu with quick stats

That's it! You now have full admin access.

## Admin Panel Menu

When you send `/admin`, you'll see these options:

```
📊 Dashboard       - View detailed system statistics
👥 Users          - Manage user accounts
📋 Orders         - View and cancel orders
🎯 Positions      - Monitor all positions
🛑 Stop Loss      - Manage stop losses
👥 Copy Trading   - View copy trading subscriptions
💰 Wallets        - Financial overview (deposits/withdrawals)
⚙️ System         - Monitor system health
🔧 Settings       - Toggle system features
📢 Broadcast      - Send messages to users
```

## Common Admin Tasks

### View System Overview
1. `/admin` → `📊 Dashboard`
2. See total users, balance, orders, positions
3. Click `🔄 Refresh` to update stats

### Search for a User
1. `/admin` → `👥 Users`
2. Click `🔍 Search`
3. Enter Telegram user ID
4. View user details, wallet, positions

### Cancel an Order
1. `/admin` → `📋 Orders`
2. Find the order (use filters if needed)
3. Click on the order
4. Click `❌ Cancel Order`
5. Confirm cancellation

### Broadcast a Message
1. `/admin` → `📢 Broadcast`
2. Select target audience:
   - All users
   - Active users only
   - Users with balance
3. Type your message
4. Preview and confirm
5. Monitor delivery progress

### Toggle System Features
1. `/admin` → `🔧 Settings`
2. Click any toggle to enable/disable:
   - 🔧 Maintenance Mode
   - 👤 New Registrations
   - 👥 Copy Trading
   - 🛑 Stop Loss

### Monitor System Health
1. `/admin` → `⚙️ System`
2. View:
   - 🔌 WebSocket status
   - 🌐 API connectivity
   - 💾 Database stats
3. Click `🔄 Refresh` for latest status

## Navigation Tips

- **🔙 Back**: Return to previous screen
- **🏠 Menu**: Return to admin main menu
- **❌ Close**: Exit admin panel
- **◀️ ▶️**: Navigate pages (for lists)
- **🔄 Refresh**: Update current view

## Security Best Practices

✅ **DO:**
- Keep your Telegram user ID private
- Regularly review admin access list
- Test broadcasts with single user first
- Review logs after admin actions

❌ **DON'T:**
- Share your admin credentials
- Grant admin access to untrusted users
- Cancel orders without investigation
- Send broadcasts without preview

## Troubleshooting

### "Unauthorized access" error
**Solution**: Check your user ID is in `ADMIN_TELEGRAM_IDS` in `.env` file

### Admin panel not responding
**Solution**: Restart the bot with `python run.py`

### Can't see recent changes
**Solution**: Click `🔄 Refresh` button or re-enter the section

### Broadcast not sending
**Solution**: Check user count and wait for rate limiting

## Need Help?

- Check [admin/README.md](README.md) for detailed documentation
- Review bot logs for errors
- Verify `.env` configuration
- Ensure database is accessible

## Pro Tips

💡 Use the search function to quickly find users by ID
💡 Filter orders by status to find specific types quickly
💡 Refresh dashboard regularly to monitor system health
💡 Always preview broadcasts before sending
💡 Use pagination efficiently for large lists
💡 Bookmark frequently used admin sections

---

**You're all set!** Send `/admin` to your bot to get started. 🚀
