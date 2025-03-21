# Setting Up a Periodic Job for YouTube Scraper

This document provides instructions on how to set up a periodic job to run the YouTube scraper automatically.

## Prerequisites

Ensure Poetry is installed and the project dependencies are set up:

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Verify the installation
poetry --version

# Install project dependencies
cd /path/to/Hyperbolic-AgentKit
poetry install
```

## Using Cron (macOS/Linux)

Cron is a time-based job scheduler in Unix-like operating systems. You can use it to schedule jobs (commands or shell scripts) to run periodically at fixed times, dates, or intervals.

### Viewing Current Cron Jobs

To view your current cron jobs:

```bash
crontab -l
```

### Editing Cron Jobs

To edit your cron jobs:

```bash
crontab -e
```

### Example Cron Job Setups

Here are some example cron job configurations:

#### Run Daily at 2 AM

```
0 2 * * * /Users/amr/Hyperbolic-AgentKit/youtube_scraper/run_youtube_scraper.sh
```

#### Run Weekly on Sunday at 3 AM

```
0 3 * * 0 /Users/amr/Hyperbolic-AgentKit/youtube_scraper/run_youtube_scraper.sh
```

#### Run Twice a Week (Monday and Thursday at 4 AM)

```
0 4 * * 1,4 /Users/amr/Hyperbolic-AgentKit/youtube_scraper/run_youtube_scraper.sh
```

### Notes on Cron Syntax

The cron syntax consists of five fields:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of the month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * * <command to execute>
```

## Using Launchd (macOS Only)

For macOS, you can also use launchd, which is the preferred method for scheduling recurring tasks.

### Create a Property List File

Create a file named `com.yourusername.youtube-scraper.plist` in the `~/Library/LaunchAgents/` directory:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourusername.youtube-scraper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/amr/Hyperbolic-AgentKit/youtube_scraper/run_youtube_scraper.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/amr/Hyperbolic-AgentKit/youtube_scraper/logs/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/amr/Hyperbolic-AgentKit/youtube_scraper/logs/launchd_stderr.log</string>
</dict>
</plist>
```

### Load the Job

Load the job with:

```bash
launchctl load ~/Library/LaunchAgents/com.yourusername.youtube-scraper.plist
```

### Unload the Job

If you need to unload the job:

```bash
launchctl unload ~/Library/LaunchAgents/com.yourusername.youtube-scraper.plist
```

## Using Task Scheduler (Windows)

On Windows, you can use Task Scheduler:

1. Open Task Scheduler (search for it in the Start menu)
2. Click "Create Basic Task"
3. Give it a name and description
4. Set the trigger (daily, weekly, etc.)
5. Choose "Start a program" as the action
6. Browse to the location of your script (you might need a batch file wrapper)
7. Complete the wizard

## Troubleshooting

If your scheduled job isn't running as expected:

1. Check that the script has execute permissions: `chmod +x run_youtube_scraper.sh`
2. Verify all paths in the script are absolute paths
3. Check log files in the `logs` directory for error messages
4. Ensure the user running the cron job has access to all required directories and files
5. Test the script manually before setting up the scheduled job
6. Ensure your computer is on and not in sleep mode when the job is scheduled to run
7. Make sure Poetry is in the PATH of the user running the cron job 