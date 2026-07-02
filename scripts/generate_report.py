#!/usr/bin/env python3
"""
Performance Report Generator for College Football Market Edge Platform.

Generates comprehensive performance reports with advanced analytics,
confidence calibration, and factor performance analysis.

Usage:
    python scripts/generate_report.py [options]

Examples:
    python scripts/generate_report.py                           # Basic report
    python scripts/generate_report.py --comprehensive           # Full analysis
    python scripts/generate_report.py --save-html report.html   # Save as HTML
    python scripts/generate_report.py --factor-analysis         # Focus on factors
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.performance_analyzer import performance_analyzer
from utils.prediction_storage import prediction_storage


def generate_html_report(report_content: str, title: str = "Performance Report") -> str:
    """
    Convert text report to HTML format.
    
    Args:
        report_content: Text report content
        title: HTML page title
        
    Returns:
        HTML formatted report
    """
    # Convert text report to HTML with basic styling
    lines = report_content.split('\n')
    html_lines = []
    
    html_lines.append(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                margin: 40px;
                background-color: #f8f9fa;
                line-height: 1.6;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                margin: -40px -40px 30px -40px;
                border-radius: 8px 8px 0 0;
            }}
            .section {{
                margin: 30px 0;
            }}
            .metric {{
                background-color: #ecf0f1;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #3498db;
            }}
            .recommendation {{
                background-color: #e8f5e8;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #27ae60;
            }}
            .warning {{
                background-color: #fff3cd;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #ffc107;
            }}
            h1, h2 {{
                color: #2c3e50;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }}
            .stat-card {{
                background-color: #f8f9fa;
                padding: 20px;
                border-radius: 5px;
                text-align: center;
            }}
            .stat-value {{
                font-size: 2em;
                font-weight: bold;
                color: #2c3e50;
            }}
            .stat-label {{
                color: #7f8c8d;
                margin-top: 10px;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
    """)
    
    current_section = []
    in_section = False
    
    for line in lines:
        if line.startswith("="):
            if current_section and in_section:
                # End current section
                html_lines.append("</div>")
            if "ANALYSIS" in line or "SUMMARY" in line or "PERFORMANCE" in line:
                # Start new section
                html_lines.append('<div class="section">')
                html_lines.append(f"<h2>{line.replace('=', '').strip()}</h2>")
                in_section = True
            current_section = []
        elif line.startswith("-"):
            if current_section:
                html_lines.append("</div>")
            html_lines.append('<div class="section">')
            html_lines.append(f"<h3>{line.replace('-', '').strip()}</h3>")
            current_section = []
        elif line.strip().startswith("•") or (line.strip() and line.strip()[0].isdigit() and ". " in line):
            # Recommendation or numbered list
            html_lines.append(f'<div class="recommendation">{line.strip()}</div>')
        elif ":" in line and any(word in line.lower() for word in ["rate", "score", "total", "average", "predictions"]):
            # Metric line
            html_lines.append(f'<div class="metric">{line.strip()}</div>')
        elif line.strip():
            html_lines.append(f"<p>{line.strip()}</p>")
        else:
            html_lines.append("<br>")
    
    if in_section:
        html_lines.append("</div>")
    
    html_lines.append("""
        </div>
    </body>
    </html>
    """)
    
    return "".join(html_lines)


def generate_summary_dashboard() -> str:
    """Generate a quick summary dashboard."""
    performance_data = prediction_storage.load_performance_tracker()
    overall = performance_data.get('overall_performance', {})
    
    lines = []
    lines.append("=" * 60)
    lines.append("PERFORMANCE DASHBOARD")
    lines.append("=" * 60)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append()
    
    # Key metrics
    total_preds = overall.get('total_predictions', 0)
    correct_preds = overall.get('correct_predictions', 0)
    win_rate = overall.get('win_rate', 0)
    avg_confidence = overall.get('average_confidence', 0)
    weeks_tracked = performance_data.get('weeks_tracked', 0)
    
    lines.append("KEY METRICS:")
    lines.append(f"  📊 Total Predictions: {total_preds}")
    lines.append(f"  ✅ Successful Bets: {correct_preds}")
    lines.append(f"  🎯 Win Rate: {win_rate:.1%}" if win_rate else "  🎯 Win Rate: N/A")
    lines.append(f"  🎪 Average Confidence: {avg_confidence:.1f}%" if avg_confidence else "  🎪 Average Confidence: N/A")
    lines.append(f"  📅 Weeks Tracked: {weeks_tracked}")
    lines.append()
    
    # Recent performance
    weekly_breakdown = performance_data.get('weekly_breakdown', {})
    if weekly_breakdown:
        lines.append("RECENT PERFORMANCE:")
        recent_weeks = list(weekly_breakdown.items())[-3:]  # Last 3 weeks
        
        for week_key, week_data in recent_weeks:
            week_num = week_key.split('_')[-1]
            predictions = week_data.get('predictions', 0)
            wins = week_data.get('wins', 0)
            rate = week_data.get('win_rate', 0)
            
            lines.append(f"  Week {week_num}: {wins}/{predictions} ({rate:.1%})" if predictions > 0 else f"  Week {week_num}: No predictions")
        
        lines.append()
    
    # Status assessment
    lines.append("SYSTEM STATUS:")
    if total_preds == 0:
        lines.append("  🟡 No predictions yet - system ready to collect data")
    elif total_preds < 10:
        lines.append("  🟡 Early stage - collecting initial performance data")
    elif win_rate and win_rate > 0.65:
        lines.append("  🟢 Strong performance - system exceeding expectations")
    elif win_rate and win_rate > 0.55:
        lines.append("  🟢 Good performance - system meeting expectations") 
    elif win_rate and win_rate > 0.45:
        lines.append("  🟡 Moderate performance - monitor closely")
    else:
        lines.append("  🔴 Underperforming - review system logic")
    
    lines.append()
    
    # Next actions
    lines.append("RECOMMENDED ACTIONS:")
    if total_preds == 0:
        lines.append("  • Run weekly_predictions.py to start collecting data")
        lines.append("  • Set up weekly automation for consistent tracking")
    elif total_preds < 20:
        lines.append("  • Continue collecting data for statistical significance")
        lines.append("  • Monitor individual factor performance")
    else:
        lines.append("  • Run comprehensive analysis with --comprehensive flag")
        lines.append("  • Review confidence calibration")
        lines.append("  • Analyze factor performance for optimization")
    
    lines.append()
    lines.append("=" * 60)
    
    return "\n".join(lines)


def generate_factor_focus_report() -> str:
    """Generate a report focused on factor performance."""
    factor_analysis = performance_analyzer.analyze_factor_performance()
    
    lines = []
    lines.append("=" * 60)
    lines.append("FACTOR PERFORMANCE DEEP DIVE")
    lines.append("=" * 60)
    lines.append()
    
    factor_success = factor_analysis.get("factor_success_rates", {})
    
    if not factor_success:
        lines.append("❌ Insufficient data for factor analysis")
        lines.append("   Need at least 3 predictions with factor breakdowns")
        return "\n".join(lines)
    
    # Factor rankings
    lines.append("FACTOR EFFECTIVENESS RANKING:")
    lines.append("-" * 40)
    
    sorted_factors = sorted(
        factor_success.items(),
        key=lambda x: x[1].get("effectiveness_score", 0),
        reverse=True
    )
    
    for i, (factor_name, data) in enumerate(sorted_factors, 1):
        effectiveness = data.get("effectiveness_score", 0)
        occurrences = data.get("total_occurrences", 0)
        directional = data.get("directional_accuracy", 0)
        
        lines.append(f"{i:2d}. {factor_name}")
        lines.append(f"     Effectiveness Score: {effectiveness:.3f}")
        lines.append(f"     Directional Accuracy: {directional:.1%}")
        lines.append(f"     Total Occurrences: {occurrences}")
        lines.append()
    
    # Recommendations
    recommendations = factor_analysis.get("recommendations", [])
    if recommendations:
        lines.append("FACTOR OPTIMIZATION RECOMMENDATIONS:")
        lines.append("-" * 40)
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append()
    
    # Detailed breakdown for top 3 factors
    lines.append("TOP FACTOR DETAILED ANALYSIS:")
    lines.append("-" * 40)
    
    top_factors = sorted_factors[:3]
    for factor_name, data in top_factors:
        lines.append(f"{factor_name.upper()}:")
        lines.append(f"  When Positive: {data.get('positive_impact_rate', 0):.1%} success rate")
        lines.append(f"  When Negative: {data.get('negative_impact_rate', 0):.1%} success rate")
        lines.append(f"  Average Impact: {data.get('average_impact_magnitude', 0):.3f}")
        lines.append(f"  Directional Accuracy: {data.get('directional_accuracy', 0):.1%}")
        lines.append()
    
    return "\n".join(lines)


def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(
        description='Generate performance analysis reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Quick dashboard
  %(prog)s --comprehensive          Full analysis report
  %(prog)s --factor-analysis        Factor performance focus
  %(prog)s --save-html report.html  Save as HTML
  %(prog)s --save-text report.txt   Save as text
        """
    )
    
    parser.add_argument('--comprehensive', action='store_true',
                       help='Generate comprehensive analysis report')
    parser.add_argument('--factor-analysis', action='store_true',
                       help='Focus on factor performance analysis')
    parser.add_argument('--save-html', type=str,
                       help='Save report as HTML file')
    parser.add_argument('--save-text', type=str,
                       help='Save report as text file')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress console output')
    
    args = parser.parse_args()
    
    if not args.quiet:
        print("=" * 60)
        print("College Football Market Edge Platform - Report Generator")
        print("=" * 60)
        print()
    
    try:
        # Generate appropriate report
        if args.comprehensive:
            if not args.quiet:
                print("🔍 Generating comprehensive performance analysis...")
            report_content = performance_analyzer.generate_comprehensive_report()
            report_title = "Comprehensive Performance Analysis"
        elif args.factor_analysis:
            if not args.quiet:
                print("📊 Generating factor performance analysis...")
            report_content = generate_factor_focus_report()
            report_title = "Factor Performance Analysis"
        else:
            if not args.quiet:
                print("📋 Generating performance dashboard...")
            report_content = generate_summary_dashboard()
            report_title = "Performance Dashboard"
        
        # Save to files if requested
        if args.save_html:
            html_content = generate_html_report(report_content, report_title)
            with open(args.save_html, 'w') as f:
                f.write(html_content)
            if not args.quiet:
                print(f"💾 HTML report saved to: {args.save_html}")
        
        if args.save_text:
            with open(args.save_text, 'w') as f:
                f.write(report_content)
            if not args.quiet:
                print(f"💾 Text report saved to: {args.save_text}")
        
        # Display report unless quiet
        if not args.quiet:
            if args.save_html or args.save_text:
                print()
            print(report_content)
        
        return 0
        
    except KeyboardInterrupt:
        if not args.quiet:
            print("\n❌ Interrupted by user")
        return 1
    except Exception as e:
        if not args.quiet:
            print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())