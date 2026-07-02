#!/bin/bash

# College Football Market Edge Platform - Demo Script
# Shows the full capabilities of the system

echo "================================================"
echo "  College Football Market Edge Platform - Live Demo"
echo "================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Run setup first:"
    echo "   python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "📊 Demo 1: Basic Game Analysis"
echo "--------------------------------"
echo "Analyzing a marquee matchup: Texas @ Ohio State"
echo ""
python main.py --home "Ohio State" --away "Texas"
echo ""
read -p "Press Enter to continue..."

echo ""
echo "📈 Demo 2: Detailed Factor Breakdown"
echo "--------------------------------"
echo "Same game with factor details to see what drives the prediction"
echo ""
python main.py --home "Ohio State" --away "Texas" --show-factors
echo ""
read -p "Press Enter to continue..."

echo ""
echo "🏈 Demo 3: List Current Week Games"
echo "--------------------------------"
echo "See all Power 4 games available for analysis"
echo ""
python main.py --list-games current | head -20
echo "..."
echo ""
read -p "Press Enter to continue..."

echo ""
echo "🔍 Demo 4: Team Name Validation"
echo "--------------------------------"
echo "System handles many team name variations"
echo ""
python main.py --validate-team "OSU"
echo ""
python main.py --validate-team "Buckeyes"
echo ""
read -p "Press Enter to continue..."

echo ""
echo "⚡ Demo 5: Quick Analysis (Clean Output)"
echo "--------------------------------"
echo "Using the clean prediction script for betting-focused output"
echo ""
python scripts/clean_predict.py "Michigan" "Texas"
echo ""
read -p "Press Enter to continue..."

echo ""
echo "📊 Demo 6: Weekly Analysis"
echo "--------------------------------"
echo "Analyze all Week 1 games with betting lines (showing first few)"
echo ""
python main.py --analyze-week 1 --min-edge 1.0 2>/dev/null | head -30
echo ""
read -p "Press Enter to continue..."

echo ""
echo "🔧 Demo 7: System Health Check"
echo "--------------------------------"
echo "Verify API connections and configuration"
echo ""
python main.py --check-config
echo ""
read -p "Press Enter to continue..."

echo ""
echo "📈 Demo 8: Data Quality Example"
echo "--------------------------------"
echo "Showing how system handles missing data gracefully"
echo ""
echo "Testing with an FCS team (should be filtered):"
python main.py --home "Alabama" --away "Mercer" 2>&1 | grep -E "(FCS|quality|filtered)"
echo ""
echo "Testing with valid teams but no betting line:"
python main.py --home "Army" --away "Navy" 2>&1 | grep -E "(No betting|not available)"
echo ""
read -p "Press Enter to continue..."

echo ""
echo "✨ Demo 9: Cache Performance"
echo "--------------------------------"
echo "First call (cold cache):"
time python main.py --home "Georgia" --away "Florida" --quiet
echo ""
echo "Second call (warm cache - should be much faster):"
time python main.py --home "Georgia" --away "Florida" --quiet
echo ""
read -p "Press Enter to continue..."

echo ""
echo "🎯 Demo 10: Finding Best Bets"
echo "--------------------------------"
echo "Analyzing multiple games to find strongest edges"
echo ""

games=("LSU:Clemson" "Notre Dame:Miami" "Auburn:Baylor")

for game in "${games[@]}"
do
    IFS=':' read -r away home <<< "$game"
    echo "Checking $away @ $home..."
    python main.py --home "$home" --away "$away" 2>/dev/null | grep -E "(Edge Size|Confidence|Recommendation)" | head -3
    echo ""
done

echo ""
echo "================================================"
echo "           Demo Complete!"
echo "================================================"
echo ""
echo "Key Features Demonstrated:"
echo "  ✅ Multi-source data integration (CFBD, ESPN, Odds)"
echo "  ✅ 11-factor quantitative analysis"
echo "  ✅ Automatic weight normalization"
echo "  ✅ Team name normalization (130+ variations)"
echo "  ✅ Cache optimization (78% hit rate)"
echo "  ✅ Graceful error handling"
echo "  ✅ Production-ready architecture"
echo ""
echo "For more information:"
echo "  - README.md: Full documentation"
echo "  - docs/ARCHITECTURE.md: System design"
echo "  - docs/PERFORMANCE.md: Benchmarks and metrics"
echo "  - docs/PROJECT_OVERVIEW.md: Technical details"
echo ""