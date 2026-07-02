#!/usr/bin/env python3
"""
Factor Validation Script for College Football Market Edge Platform.

Runs comprehensive validation tests on all factors to ensure they produce
realistic, varied outputs rather than uniform/unrealistic patterns.

Usage:
    python scripts/validate_factors.py [options]

Options:
    --factor FACTOR_NAME    Validate specific factor only
    --quick                Run quick validation (fewer test scenarios)
    --output FORMAT        Output format: text, json, html (default: text)
    --save PATH            Save results to file
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from engine.factor_validator import factor_validator, ValidationResult
from factors.factor_registry import factor_registry


def format_text_output(validation_results: dict) -> str:
    """Format validation results as readable text."""
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("FACTOR VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append(f"Validation Time: {validation_results['validation_timestamp']}")
    lines.append()
    
    # System Summary
    summary = validation_results['system_summary']
    lines.append("SYSTEM SUMMARY:")
    lines.append(f"  Overall Health: {summary['system_health']}")
    lines.append(f"  Total Factors: {summary['total_factors']}")
    lines.append(f"  Passed: {summary['passed_factors']} ({summary['pass_rate']:.1%})")
    lines.append(f"  Warnings: {summary['warning_factors']}")
    lines.append(f"  Failed: {summary['failed_factors']}")
    lines.append(f"  Errors: {summary['error_factors']}")
    lines.append(f"  Test Scenarios: {summary['test_scenarios_used']}")
    lines.append()
    
    # Recommendations
    if summary['recommendations']:
        lines.append("RECOMMENDATIONS:")
        for rec in summary['recommendations']:
            lines.append(f"  • {rec}")
        lines.append()
    
    # Individual Factor Results
    lines.append("INDIVIDUAL FACTOR RESULTS:")
    lines.append("-" * 40)
    
    individual = validation_results['individual_factors']
    for factor_name, result in individual.items():
        overall = result.get('overall_result', ValidationResult.ERROR)
        status_symbol = {
            ValidationResult.PASS: "✅",
            ValidationResult.WARNING: "⚠️ ",
            ValidationResult.FAIL: "❌",
            ValidationResult.ERROR: "🚨"
        }.get(overall, "?")
        
        lines.append(f"{status_symbol} {factor_name}")
        lines.append(f"    Result: {overall.value.upper()}")
        
        if 'error' in result:
            lines.append(f"    Error: {result['error']}")
            lines.append()
            continue
        
        tests_passed = result.get('tests_passed', 0)
        tests_total = result.get('tests_total', 0)
        pass_rate = result.get('pass_rate', 0)
        
        lines.append(f"    Tests: {tests_passed}/{tests_total} passed ({pass_rate:.1%})")
        
        # Show key test results
        tests = result.get('tests', {})
        
        # Uniformity
        uniformity = tests.get('uniformity_test', {})
        if uniformity:
            result_str = uniformity['result'].value
            cv = uniformity.get('coefficient_of_variation', 0)
            unique = uniformity.get('unique_values', 0)
            lines.append(f"    Uniformity: {result_str.upper()} (CV: {cv:.6f}, Unique: {unique})")
        
        # Variety
        variety = tests.get('variety_test', {})
        if variety:
            result_str = variety['result'].value
            unique_vals = variety.get('unique_values', 0)
            variety_ratio = variety.get('variety_ratio', 0)
            lines.append(f"    Variety: {result_str.upper()} ({unique_vals} unique, {variety_ratio:.1%} ratio)")
        
        # Range compliance
        range_test = tests.get('range_compliance_test', {})
        if range_test:
            result_str = range_test['result'].value
            range_util = range_test.get('range_utilization', 0)
            lines.append(f"    Range: {result_str.upper()} ({range_util:.1%} utilization)")
        
        # Activation
        activation = tests.get('activation_test', {})
        if activation:
            result_str = activation['result'].value
            activation_rate = activation.get('activation_rate', 0)
            lines.append(f"    Activation: {result_str.upper()} ({activation_rate:.1%} rate)")
        
        lines.append()
    
    lines.append("=" * 60)
    lines.append("VALIDATION COMPLETE")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def format_json_output(validation_results: dict) -> str:
    """Format validation results as JSON."""
    # Convert enum values to strings for JSON serialization
    def convert_enums(obj):
        if isinstance(obj, dict):
            return {k: convert_enums(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_enums(item) for item in obj]
        elif isinstance(obj, ValidationResult):
            return obj.value
        else:
            return obj
    
    json_data = convert_enums(validation_results)
    return json.dumps(json_data, indent=2)


def format_html_output(validation_results: dict) -> str:
    """Format validation results as HTML."""
    summary = validation_results['system_summary']
    
    # Simple HTML template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Factor Validation Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .summary {{ margin: 20px 0; }}
            .factor {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ddd; }}
            .pass {{ border-left-color: #28a745; }}
            .warning {{ border-left-color: #ffc107; }}
            .fail {{ border-left-color: #dc3545; }}
            .error {{ border-left-color: #6f42c1; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Factor Validation Report</h1>
            <p>Generated: {validation_results['validation_timestamp']}</p>
        </div>
        
        <div class="summary">
            <h2>System Summary</h2>
            <p><strong>Health:</strong> {summary['system_health']}</p>
            <p><strong>Pass Rate:</strong> {summary['passed_factors']}/{summary['total_factors']} ({summary['pass_rate']:.1%})</p>
        </div>
        
        <h2>Individual Factors</h2>
    """
    
    individual = validation_results['individual_factors']
    for factor_name, result in individual.items():
        overall = result.get('overall_result', ValidationResult.ERROR)
        css_class = overall.value
        
        html += f'<div class="factor {css_class}">'
        html += f'<h3>{factor_name}</h3>'
        html += f'<p><strong>Result:</strong> {overall.value.upper()}</p>'
        
        if 'tests_passed' in result:
            html += f'<p><strong>Tests:</strong> {result["tests_passed"]}/{result["tests_total"]} passed</p>'
        
        html += '</div>'
    
    html += """
        </body>
    </html>
    """
    
    return html


def main():
    """Main validation script."""
    parser = argparse.ArgumentParser(description='Validate College Football Market Edge Platform factors')
    parser.add_argument('--factor', type=str, help='Validate specific factor only')
    parser.add_argument('--quick', action='store_true', help='Run quick validation')
    parser.add_argument('--output', choices=['text', 'json', 'html'], default='text',
                       help='Output format')
    parser.add_argument('--save', type=str, help='Save results to file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    print("College Football Market Edge Platform - Factor Validation")
    print("=" * 50)
    
    try:
        if args.factor:
            # Validate single factor
            if args.factor not in factor_registry.factors:
                print(f"Error: Factor '{args.factor}' not found")
                print(f"Available factors: {', '.join(factor_registry.factors.keys())}")
                return 1
            
            print(f"Validating single factor: {args.factor}")
            factor = factor_registry.factors[args.factor]
            result = factor_validator.validate_single_factor(args.factor, factor)
            
            # Create mock full results for formatting
            validation_results = {
                'individual_factors': {args.factor: result},
                'system_summary': {
                    'system_health': 'SINGLE_FACTOR_TEST',
                    'total_factors': 1,
                    'passed_factors': 1 if result.get('overall_result') == ValidationResult.PASS else 0,
                    'warning_factors': 1 if result.get('overall_result') == ValidationResult.WARNING else 0,
                    'failed_factors': 1 if result.get('overall_result') == ValidationResult.FAIL else 0,
                    'error_factors': 1 if result.get('overall_result') == ValidationResult.ERROR else 0,
                    'pass_rate': 1 if result.get('overall_result') == ValidationResult.PASS else 0,
                    'test_scenarios_used': len(factor_validator.test_scenarios),
                    'recommendations': []
                },
                'validation_timestamp': factor_validator._get_timestamp()
            }
        else:
            # Validate all factors
            print("Validating all factors...")
            print("This may take a few minutes...")
            validation_results = factor_validator.validate_all_factors()
        
        # Format output
        if args.output == 'json':
            output = format_json_output(validation_results)
        elif args.output == 'html':
            output = format_html_output(validation_results)
        else:  # text
            output = format_text_output(validation_results)
        
        # Save to file if requested
        if args.save:
            with open(args.save, 'w') as f:
                f.write(output)
            print(f"Results saved to: {args.save}")
        else:
            print(output)
        
        # Return appropriate exit code
        if 'system_summary' in validation_results:
            failed = validation_results['system_summary']['failed_factors']
            errors = validation_results['system_summary']['error_factors']
            if failed > 0 or errors > 0:
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        return 1
    except Exception as e:
        print(f"Error during validation: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())