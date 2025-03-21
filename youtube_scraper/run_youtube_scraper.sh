#!/bin/bash

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOGS_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOGS_DIR}/youtube_scraper_$(date +%Y%m%d_%H%M%S).log"
PYTHON_SCRIPT="${SCRIPT_DIR}/main.py"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "${LOG_FILE}"
}

# Create logs directory if it doesn't exist
mkdir -p "${LOGS_DIR}"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    log "ERROR: Poetry is not installed. Please install Poetry first."
    exit 1
fi

# Check if the script exists
if [ ! -f "${PYTHON_SCRIPT}" ]; then
    log "ERROR: YouTube scraper script not found at ${PYTHON_SCRIPT}"
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    log "ERROR: ffmpeg is not installed or not in PATH"
    exit 1
fi

# Go to script directory
cd "${SCRIPT_DIR}"

# Check if processed_videos.db exists
if [ ! -f "processed_videos.db" ]; then
    log "No database found. Initializing..."
    poetry run python -c "import video_database; video_database.initialize_database()" 2>&1 | tee -a "${LOG_FILE}"
fi

# Check if directories exist
mkdir -p downloaded_videos split_videos jsonoutputs

# Run the script with timeout to prevent hanging
log "Running YouTube scraper with Poetry..."
timeout 12h poetry run python "${PYTHON_SCRIPT}" 2>&1 | tee -a "${LOG_FILE}"

# Show database statistics after completion
log "Showing database statistics..."
poetry run python db_utilities.py stats 2>&1 | tee -a "${LOG_FILE}"

# Check exit status
EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    log "Script timed out after 12 hours."
elif [ $EXIT_CODE -ne 0 ]; then
    log "Script failed with exit code ${EXIT_CODE}."
else
    log "Script completed successfully."
fi

log "Log file: ${LOG_FILE}"
exit $EXIT_CODE 