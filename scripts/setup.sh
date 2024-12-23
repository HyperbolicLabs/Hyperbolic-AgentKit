#!/usr/bin/env bash
set -euo pipefail

########################################
# Error handling
########################################
handle_error() {
  log_error "An error occurred on line $1"
  exit 1
}

trap 'handle_error $LINENO' ERR

########################################
# Logging helper functions
########################################
log_info() {
  local msg="$1"
  echo -e "[INFO] $msg"
}

log_error() {
  local msg="$1"
  echo -e "[ERROR] $msg" >&2
}

########################################
# Usage / help
########################################
usage() {
  echo "Usage: $0 [logs]"
  echo "  no arguments  : Run the full setup (install Nethermind/Lighthouse, build & run staking-deposit-cli, etc.)"
  echo "  logs          : Tail all logs (Nethermind, Lighthouse beacon, Lighthouse validator)"
  exit 1
}

########################################
# Health check function
########################################
check_service_health() {
    local service="$1"
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        status=$(sudo supervisorctl status "$service" | awk '{print $2}')
        if [ "$status" = "RUNNING" ]; then
            log_info "$service is running correctly"
            return 0
        fi
        log_info "Attempt $attempt: $service is not running (status: $status). Waiting..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_error "$service failed to start properly after $max_attempts attempts"
    return 1
}

########################################
# Verify JWT setup
########################################
verify_jwt() {
    if [ ! -f "/home/ubuntu/jwt/jwttoken" ]; then
        log_error "JWT token file not found"
        return 1
    fi
    
    local jwt_size
    jwt_size=$(wc -c < /home/ubuntu/jwt/jwttoken)
    # 64 hex characters = 32 bytes in ASCII => 64 length
    if [ "$jwt_size" -ne 64 ]; then
        log_error "JWT token is not the correct size (should be 64 characters)"
        return 1
    fi
    
    local jwt_perms
    jwt_perms=$(stat -c %a /home/ubuntu/jwt/jwttoken)
    if [ "$jwt_perms" != "644" ]; then
        log_error "JWT token has incorrect permissions (should be 644). Correcting..."
        sudo chmod 644 /home/ubuntu/jwt/jwttoken
    fi
}

########################################
# Show live logs for Nethermind / Lighthouse
########################################
if [[ "${1:-}" == "logs" ]]; then
  log_info "Tailing logs for Nethermind, Lighthouse Beacon, and Lighthouse Validator. Press Ctrl+C to stop."
  
  # Check if log files exist, if not create them
  for logfile in \
    /home/ubuntu/logs/nethermind.out.log \
    /home/ubuntu/logs/nethermind.err.log \
    /home/ubuntu/logs/lighthouse_beacon.out.log \
    /home/ubuntu/logs/lighthouse_beacon.err.log \
    /home/ubuntu/logs/lighthouse_validator.out.log \
    /home/ubuntu/logs/lighthouse_validator.err.log; do
    if [ ! -f "$logfile" ]; then
      sudo touch "$logfile"
      sudo chown ubuntu:ubuntu "$logfile"
      sudo chmod 644 "$logfile"
    fi
  done

  # Now tail the logs
  tail -F \
    /home/ubuntu/logs/nethermind.out.log \
    /home/ubuntu/logs/lighthouse_beacon.out.log \
    /home/ubuntu/logs/lighthouse_validator.out.log
  exit 0
fi

########################################
# Environment: Non-interactive for tzdata
########################################
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# Force system timezone to UTC so tzdata won't prompt:
sudo ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime || true

########################################
# Main Setup
########################################

log_info "Updating system packages (non-interactive)..."
sudo apt -y update
sudo apt -y upgrade

log_info "Installing necessary packages (non-interactive)..."
sudo apt -y install wget curl unzip supervisor openssl ccze tar expect tzdata git python3 python3-pip

# Reconfigure tzdata silently (if needed)
sudo dpkg-reconfigure --frontend noninteractive tzdata || true

if [ ! -d "/etc/supervisor/conf.d" ]; then
  sudo mkdir -p /etc/supervisor/conf.d
fi

log_info "Creating directories under /home/ubuntu..."
sudo mkdir -p /home/ubuntu/nethermind
sudo mkdir -p /home/ubuntu/nethermind-data
sudo mkdir -p /home/ubuntu/lighthouse
sudo mkdir -p /home/ubuntu/lighthouse-data
sudo mkdir -p /home/ubuntu/jwt
sudo mkdir -p /home/ubuntu/logs
sudo mkdir -p /home/ubuntu/validator_keys

########################################
# Create and set permissions for log files
########################################
log_info "Setting up log files and permissions..."
sudo touch /home/ubuntu/logs/nethermind.out.log
sudo touch /home/ubuntu/logs/nethermind.err.log
sudo touch /home/ubuntu/logs/lighthouse_beacon.out.log
sudo touch /home/ubuntu/logs/lighthouse_beacon.err.log
sudo touch /home/ubuntu/logs/lighthouse_validator.out.log
sudo touch /home/ubuntu/logs/lighthouse_validator.err.log

# Set proper permissions
sudo chown -R ubuntu:ubuntu /home/ubuntu/logs
sudo chmod 755 /home/ubuntu/logs
sudo chmod 644 /home/ubuntu/logs/*.log

# Also ensure the directories have correct permissions
sudo chown -R ubuntu:ubuntu /home/ubuntu/nethermind-data
sudo chown -R ubuntu:ubuntu /home/ubuntu/lighthouse-data
sudo chown -R ubuntu:ubuntu /home/ubuntu/jwt
sudo chown -R ubuntu:ubuntu /home/ubuntu/validator_keys

NETHERMIND_URL="https://github.com/NethermindEth/nethermind/releases/download/1.30.1/nethermind-1.30.1-2b75a75a-linux-x64.zip"
LIGHTHOUSE_URL="https://github.com/sigp/lighthouse/releases/download/v6.0.1/lighthouse-v6.0.1-x86_64-unknown-linux-gnu.tar.gz"

########################################
# Install Nethermind
########################################
log_info "Downloading Nethermind..."
cd /home/ubuntu/nethermind
sudo wget -q --show-progress "$NETHERMIND_URL" -O nethermind-latest.zip

log_info "Extracting Nethermind..."
sudo unzip -o nethermind-latest.zip
sudo rm nethermind-latest.zip

########################################
# Install Lighthouse
########################################
log_info "Downloading Lighthouse..."
cd /home/ubuntu/lighthouse
sudo wget -q --show-progress "$LIGHTHOUSE_URL" -O lighthouse-latest.tar.gz

log_info "Extracting Lighthouse..."
sudo tar xvf lighthouse-latest.tar.gz --strip-components=0
sudo rm lighthouse-latest.tar.gz

# Safe copy of lighthouse binary with process management
if [ -f "/usr/local/bin/lighthouse" ]; then
  log_info "Stopping Lighthouse services before updating binary..."
  sudo supervisorctl stop lighthousebeacon lighthousevalidator || true
  sleep 2
  sudo cp /home/ubuntu/lighthouse/lighthouse /usr/local/bin/lighthouse
  log_info "Starting Lighthouse services..."
  sudo supervisorctl start lighthousebeacon lighthousevalidator || true
else
  sudo cp /home/ubuntu/lighthouse/lighthouse /usr/local/bin/lighthouse
fi

########################################
# Generate JWT token
########################################
log_info "Generating JWT token..."
sudo openssl rand -hex 32 | tr -d "\n" | sudo tee /home/ubuntu/jwt/jwttoken >/dev/null
sudo chmod 644 /home/ubuntu/jwt/jwttoken
sudo chown ubuntu:ubuntu /home/ubuntu/jwt/jwttoken

########################################
# Supervisor config for Nethermind
########################################
sudo bash -c 'cat >/etc/supervisor/conf.d/nethermind.conf <<EOF
[program:nethermind]
directory=/home/ubuntu/nethermind-data
command=/home/ubuntu/nethermind/Nethermind.Runner \
    --config holesky \
    --datadir /home/ubuntu/nethermind-data \
    --Metrics.Enabled true \
    --Metrics.ExposePort 6061 \
    --Sync.SnapSync true \
    --JsonRpc.JwtSecretFile /home/ubuntu/jwt/jwttoken \
    --JsonRpc.Enabled true \
    --HealthChecks.Enabled true \
    --JsonRpc.EnabledModules="[Eth, Subscribe, Trace, TxPool, Web3, Personal, Proof, Net, Parity, Health, Rpc, Admin]" \
    --JsonRpc.AdditionalRpcUrls=http://127.0.0.1:8555|http|admin \
    --JsonRpc.EnginePort 8551
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/logs/nethermind.err.log
stdout_logfile=/home/ubuntu/logs/nethermind.out.log
EOF
'

########################################
# Supervisor config for Lighthouse Beacon
########################################
sudo bash -c 'cat >/etc/supervisor/conf.d/lighthouse-beacon.conf <<EOF
[program:lighthousebeacon]
directory=/home/ubuntu/lighthouse-data
command=/usr/local/bin/lighthouse bn \
    --network holesky \
    --datadir /home/ubuntu/lighthouse-data \
    --http \
    --execution-endpoint http://127.0.0.1:8551 \
    --checkpoint-sync-url https://holesky.beaconstate.ethstaker.cc \
    --metrics \
    --execution-jwt /home/ubuntu/jwt/jwttoken \
    --gui \
    --validator-monitor-auto
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/logs/lighthouse_beacon.err.log
stdout_logfile=/home/ubuntu/logs/lighthouse_beacon.out.log
EOF
'

########################################
# Supervisor config for Lighthouse Validator
########################################
sudo bash -c 'cat >/etc/supervisor/conf.d/lighthouse-validator.conf <<EOF
[program:lighthousevalidator]
directory=/home/ubuntu/lighthouse-data
command=/usr/local/bin/lighthouse vc \
    --network holesky \
    --datadir /home/ubuntu/lighthouse-data \
    --graffiti EducationTestnet \
    --metrics \
    --suggested-fee-recipient 0x31597a8CE03Ef90Ee351704231680Fa08aD561eD
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/logs/lighthouse_validator.err.log
stdout_logfile=/home/ubuntu/logs/lighthouse_validator.out.log
EOF
'

########################################
# Start or reload Supervisor (with sequential startup)
########################################
log_info "Verifying JWT setup..."
verify_jwt || exit 1

if pgrep supervisord >/dev/null 2>&1; then
  log_info "supervisord is already running. Reloading configs..."
  sudo supervisorctl reread
  sudo supervisorctl update
else
  log_info "Starting supervisord..."
  sudo supervisord -c /etc/supervisor/supervisord.conf
fi

log_info "Starting services in sequence..."
sudo supervisorctl stop all

# Start Nethermind first
log_info "Starting Nethermind..."
sudo supervisorctl start nethermind
log_info "Waiting for Nethermind to initialize (30s)..."
sleep 30
check_service_health nethermind

# Then start Lighthouse beacon
log_info "Starting Lighthouse beacon..."
sudo supervisorctl start lighthousebeacon
log_info "Waiting for Lighthouse beacon to initialize (30s)..."
sleep 30
check_service_health lighthousebeacon

# Finally start the validator
log_info "Starting Lighthouse validator..."
sudo supervisorctl start lighthousevalidator
check_service_health lighthousevalidator

log_info "Current Supervisor processes status:"
sudo supervisorctl status

########################################
# Build & Run staking-deposit-cli from fork
########################################
log_info "Cloning forked staking-deposit-cli repo..."
cd /home/ubuntu
if [ ! -d "staking-deposit-cli" ]; then
  sudo git clone --branch master https://github.com/garyng2000/staking-deposit-cli.git
else
  log_info "Repository already cloned, updating to latest master branch..."
  cd staking-deposit-cli
  sudo git fetch origin master
  sudo git checkout master
  sudo git pull origin master
  cd ..
fi

log_info "Installing dependencies & building deposit-cli..."
cd /home/ubuntu/staking-deposit-cli
sudo pip3 install -r requirements.txt
sudo python3 setup.py install

log_info "Creating password file for the keystore..."
echo "eIpa4axhZQZxFA3" | sudo tee /home/ubuntu/validator_keys/keystore_password.txt >/dev/null

log_info "Generating validator key (non-interactive) with deposit-cli..."
cd /home/ubuntu/staking-deposit-cli
sudo ./deposit.sh \
  --language English \
  --non_interactive \
  new-mnemonic \
  --chain holesky \
  --folder /home/ubuntu/validator_keys \
  --execution_address 0x31597a8CE03Ef90Ee351704231680Fa08aD561eD \
  --mnemonic_language English \
  --num_validators 1 \
  --keystore_password /home/ubuntu/validator_keys/keystore_password.txt \
  2>&1 | sudo tee /home/ubuntu/validator_keys/mnemonic.txt

sudo chown ubuntu:ubuntu /home/ubuntu/validator_keys/mnemonic.txt
sudo chmod 600 /home/ubuntu/validator_keys/mnemonic.txt

log_info "Setup Complete!"
log_info "Run './setup.sh logs' at any time to tail Nethermind & Lighthouse logs."