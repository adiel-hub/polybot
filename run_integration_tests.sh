#!/bin/bash
# Integration Test Runner for PolyBot
# This script helps you run integration tests safely

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "================================================================================"
echo "                    PolyBot Integration Test Runner"
echo "================================================================================"
echo ""

# Check if test.env exists
if [ ! -f "test.env" ]; then
    echo -e "${RED}❌ test.env not found!${NC}"
    echo ""
    echo "Please create test.env first:"
    echo "  cp .env.example test.env"
    echo "  # Then edit test.env with your credentials"
    echo ""
    exit 1
fi

# Check configuration
echo -e "${BLUE}📋 Checking test environment configuration...${NC}"
python setup_test_env.py --check

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Configuration incomplete!${NC}"
    echo ""
    echo "Run the setup wizard:"
    echo "  python setup_test_env.py"
    echo ""
    exit 1
fi

echo ""
echo "================================================================================"
echo "                         Select Test Mode"
echo "================================================================================"
echo ""
echo "1) 🆓 Free Tests Only (no real money spent)"
echo "2) 💰 Expensive Tests (costs real money - deposits, trades, withdrawals)"
echo "3) 📊 Specific Test File"
echo "4) 🔍 List All Tests"
echo "5) ❌ Exit"
echo ""
read -p "Select option [1-5]: " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}Running free tests...${NC}"
        echo ""
        ENV_FILE=test.env pytest tests/integration/ -v -m "not expensive" -s
        ;;
    2)
        echo ""
        echo -e "${YELLOW}⚠️  WARNING: These tests cost REAL MONEY!${NC}"
        echo ""
        echo "Estimated costs:"
        echo "  • Deposit tests: ~\$1-10 USDC + gas"
        echo "  • Withdrawal tests: Gas only"
        echo "  • Trading tests: ~\$10-20 USDC + gas"
        echo ""
        read -p "Are you sure you want to continue? [y/N]: " confirm

        if [[ $confirm =~ ^[Yy]$ ]]; then
            echo ""
            echo -e "${GREEN}Running expensive tests...${NC}"
            echo ""
            ENV_FILE=test.env pytest tests/integration/ -v -m expensive -s
        else
            echo "Cancelled."
            exit 0
        fi
        ;;
    3)
        echo ""
        echo "Available test files:"
        echo "  1) test_real_deposits.py"
        echo "  2) test_real_withdrawals.py"
        echo "  3) test_real_trading_flow.py"
        echo ""
        read -p "Select file [1-3]: " file_choice

        case $file_choice in
            1) TEST_FILE="test_real_deposits.py" ;;
            2) TEST_FILE="test_real_withdrawals.py" ;;
            3) TEST_FILE="test_real_trading_flow.py" ;;
            *) echo "Invalid choice"; exit 1 ;;
        esac

        echo ""
        echo -e "${GREEN}Running tests/integration/$TEST_FILE...${NC}"
        echo ""
        ENV_FILE=test.env pytest "tests/integration/$TEST_FILE" -v -s
        ;;
    4)
        echo ""
        echo -e "${BLUE}Listing all integration tests...${NC}"
        echo ""
        ENV_FILE=test.env pytest tests/integration/ --collect-only -q
        ;;
    5)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo -e "${GREEN}✅ Test run complete!${NC}"
echo "================================================================================"
echo ""
