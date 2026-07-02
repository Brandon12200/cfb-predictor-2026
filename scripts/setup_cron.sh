#!/bin/bash

# Cron Setup Script for College Football Market Edge Platform
#
# This script helps set up automated cron jobs for weekly predictions and results checking.
# It provides interactive setup and validation of cron job scheduling.
#
# Usage:
#   ./scripts/setup_cron.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "College Football Market Edge Platform"
echo "Cron Job Setup Assistant"
echo "=========================================="
echo

# Function to get absolute path
get_absolute_path() {
    echo "$(cd "$1" && pwd)"
}

# Function to validate cron time format
validate_cron_time() {
    local cron_time="$1"
    
    # Basic validation - should have 5 fields
    if [[ $(echo "$cron_time" | wc -w) -ne 5 ]]; then
        return 1
    fi
    
    return 0
}

# Function to explain cron time format
explain_cron() {
    echo "Cron format: minute hour day_of_month month day_of_week"
    echo "Examples:"
    echo "  '0 8 * * 2'  = Every Tuesday at 8:00 AM"
    echo "  '30 9 * * 1' = Every Monday at 9:30 AM"
    echo "  '0 20 * * 0' = Every Sunday at 8:00 PM"
    echo
    echo "Day of week: 0=Sunday, 1=Monday, 2=Tuesday, ..., 6=Saturday"
    echo
}

# Function to create cron job entry
create_cron_entry() {
    local schedule="$1"
    local mode="$2"
    local project_path="$3"
    
    echo "$schedule cd '$project_path' && ./scripts/automate_weekly.sh $mode >> logs/cron.log 2>&1"
}

# Function to add cron jobs
setup_cron_jobs() {
    local project_path="$1"
    local predictions_schedule="$2"
    local results_schedule="$3"
    
    echo "Setting up cron jobs..."
    
    # Create logs directory if it doesn't exist
    mkdir -p "$project_path/logs"
    
    # Get current crontab (if any)
    local temp_cron=$(mktemp)
    crontab -l 2>/dev/null > "$temp_cron" || true
    
    # Add comment header for our jobs
    echo "" >> "$temp_cron"
    echo "# College Football Market Edge Platform - Automated Jobs" >> "$temp_cron"
    echo "# Generated on $(date)" >> "$temp_cron"
    
    # Add predictions job
    if [[ -n "$predictions_schedule" ]]; then
        local pred_entry=$(create_cron_entry "$predictions_schedule" "predictions" "$project_path")
        echo "$pred_entry" >> "$temp_cron"
        echo "Added: Weekly predictions - $predictions_schedule"
    fi
    
    # Add results checking job
    if [[ -n "$results_schedule" ]]; then
        local results_entry=$(create_cron_entry "$results_schedule" "results" "$project_path")
        echo "$results_entry" >> "$temp_cron"
        echo "Added: Weekly results check - $results_schedule"
    fi
    
    # Install new crontab
    crontab "$temp_cron"
    rm "$temp_cron"
    
    echo "✅ Cron jobs installed successfully!"
}

# Function to show current relevant cron jobs
show_current_jobs() {
    echo "Current cron jobs related to this project:"
    echo "----------------------------------------"
    
    local current_jobs=$(crontab -l 2>/dev/null | grep -E "(cfb|college|football|market|edge)" || true)
    
    if [[ -z "$current_jobs" ]]; then
        echo "No existing jobs found."
    else
        echo "$current_jobs"
    fi
    echo
}

# Function to remove existing jobs
remove_existing_jobs() {
    echo "Removing existing College Football Market Edge Platform cron jobs..."
    
    local temp_cron=$(mktemp)
    crontab -l 2>/dev/null | grep -v -E "(College Football Market Edge Platform|automate_weekly\.sh)" > "$temp_cron" || true
    
    crontab "$temp_cron"
    rm "$temp_cron"
    
    echo "✅ Existing jobs removed."
}

# Main setup function
main() {
    local project_path=$(get_absolute_path "$PROJECT_DIR")
    
    echo "Project directory: $project_path"
    echo
    
    # Check if automation script exists
    if [[ ! -f "$project_path/scripts/automate_weekly.sh" ]]; then
        echo "❌ Error: automate_weekly.sh not found"
        echo "Please ensure the automation script is present."
        exit 1
    fi
    
    # Check if virtual environment exists
    if [[ ! -d "$project_path/venv" ]]; then
        echo "⚠️  Warning: Virtual environment not found at $project_path/venv"
        echo "Make sure to create it before running cron jobs:"
        echo "  python -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        echo
    fi
    
    # Show current jobs
    show_current_jobs
    
    # Ask if user wants to remove existing jobs
    read -p "Remove existing College Football cron jobs? (y/n): " -r remove_existing
    if [[ $remove_existing =~ ^[Yy]$ ]]; then
        remove_existing_jobs
        echo
    fi
    
    # Interactive setup
    echo "Setting up new cron jobs..."
    echo
    
    # Predictions schedule
    echo "WEEKLY PREDICTIONS SETUP:"
    echo "Recommended: Tuesday morning (after lines are set, before games)"
    explain_cron
    
    local predictions_schedule=""
    while true; do
        read -p "Enter cron schedule for weekly predictions (or 'skip' to skip): " -r pred_input
        
        if [[ "$pred_input" == "skip" ]]; then
            echo "Skipping predictions automation."
            break
        elif validate_cron_time "$pred_input"; then
            predictions_schedule="$pred_input"
            echo "✅ Valid schedule: $predictions_schedule"
            break
        else
            echo "❌ Invalid cron format. Please try again."
        fi
    done
    
    echo
    
    # Results schedule
    echo "RESULTS CHECKING SETUP:"
    echo "Recommended: Monday morning (after weekend games are complete)"
    
    local results_schedule=""
    while true; do
        read -p "Enter cron schedule for results checking (or 'skip' to skip): " -r results_input
        
        if [[ "$results_input" == "skip" ]]; then
            echo "Skipping results automation."
            break
        elif validate_cron_time "$results_input"; then
            results_schedule="$results_input"
            echo "✅ Valid schedule: $results_schedule"
            break
        else
            echo "❌ Invalid cron format. Please try again."
        fi
    done
    
    echo
    
    # Confirm setup
    if [[ -n "$predictions_schedule" || -n "$results_schedule" ]]; then
        echo "SUMMARY OF CRON JOBS TO BE CREATED:"
        echo "===================================="
        
        if [[ -n "$predictions_schedule" ]]; then
            echo "Predictions: $predictions_schedule"
        fi
        
        if [[ -n "$results_schedule" ]]; then
            echo "Results:     $results_schedule"
        fi
        
        echo
        read -p "Create these cron jobs? (y/n): " -r confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            setup_cron_jobs "$project_path" "$predictions_schedule" "$results_schedule"
        else
            echo "❌ Setup cancelled."
            exit 0
        fi
    else
        echo "No cron jobs to create."
        exit 0
    fi
    
    echo
    echo "🎉 Cron setup completed!"
    echo
    echo "IMPORTANT NOTES:"
    echo "- Logs will be written to: $project_path/logs/"
    echo "- Make sure your virtual environment is properly set up"
    echo "- Test the automation script manually first:"
    echo "    cd $project_path"
    echo "    ./scripts/automate_weekly.sh both"
    echo
    echo "To view/edit cron jobs later:"
    echo "  crontab -l  (view current jobs)"
    echo "  crontab -e  (edit jobs)"
    echo
    echo "To monitor cron execution:"
    echo "  tail -f $project_path/logs/cron.log"
}

# Handle interruption
trap 'echo "Setup interrupted"; exit 1' INT TERM

# Run main function
main "$@"