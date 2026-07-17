#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

BOOTSTRAP_SUDO=0
# Set to 1 to attempt passwordless sudo setup on remote server
# Set to 0 to skip this step (requires pre-configured sudo access)

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOGDIR="./logs"
LOGFILE="${LOGDIR}/deploy_${TIMESTAMP}.log"
mkdir -p "${LOGDIR}"

log() {
  printf "%s [%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2" | tee -a "${LOGFILE}"
}

die() {
  log "ERROR" "$2"
  exit "${1:-1}"
}

cleanup_workspace() {
  if [[ -n "${WORKDIR:-}" && -d "${WORKDIR}" ]]; then
    rm -rf "${WORKDIR}"
    log "DEBUG" "Removed temporary workspace ${WORKDIR}"
  fi
}

cleanup_remote_resources() {
  log "INFO" "Stage 7: Cleaning remote Docker artifacts"
  ssh -i "${SSH_KEY_PATH}" -o StrictHostKeyChecking=no -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" <<'EOF'
set -o errexit
set -o pipefail
set -o nounset
sudo docker ps -a --filter "status=exited" --format '{{.ID}}' | xargs -r sudo docker rm -v || true
sudo docker image prune -f || true
sudo docker network prune -f || true
if [[ -d /etc/nginx/sites-enabled ]]; then
  sudo find /etc/nginx/sites-enabled -xtype l -delete || true
fi
EOF
}

rotate_logs() {
  gzip -c "${LOGFILE}" > "${LOGFILE}.gz" || true
  find "${LOGDIR}" -type f -name "deploy_*.log.gz" -mtime +30 -exec rm -f {} \;
}

trap cleanup_workspace EXIT

log "INFO" "Stage 0.5: Starting logging and housekeeping"

load_env() {
  local env_file="${1:-.env}"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck source=/dev/null
    . "${env_file}"
    set +a
    log "INFO" "Loaded environment from ${env_file}"
  fi
}

load_env

CLEANUP_MODE=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --cleanup)
      CLEANUP_MODE=1
      shift
      ;;
    *)
      die 2 "Unknown argument $1"
      ;;
  esac
done

log "INFO" "Stage 1: Collecting deployment parameters"

if [[ -z "${GIT_REPO_URL:-}" ]]; then
  read -rp "Git repository URL: " GIT_REPO_URL
fi
if [[ -z "${GIT_PAT:-}" ]]; then
  read -rsp "Personal Access Token (leave blank for public repos): " GIT_PAT
  printf '\n'
fi
if [[ -z "${BRANCH:-}" ]]; then
  read -rp "Branch name (default: main): " BRANCH
  BRANCH="${BRANCH:-main}"
fi
if [[ -z "${REMOTE_USER:-}" ]]; then
  read -rp "Remote SSH username (default: deploy): " REMOTE_USER
  REMOTE_USER="${REMOTE_USER:-deploy}"
fi
if [[ -z "${REMOTE_HOST:-}" ]]; then
  read -rp "Remote SSH host/IP: " REMOTE_HOST
fi
if [[ -z "${SSH_KEY_PATH:-}" ]]; then
  read -rp "Path to SSH private key (default: ~/.ssh/id_rsa): " SSH_KEY_PATH
  SSH_KEY_PATH="${SSH_KEY_PATH:-${HOME}/.ssh/id_rsa}"
fi

if (( CLEANUP_MODE == 0 )); then
  if [[ -z "${DOMAIN_NAME:-}" ]]; then
    read -rp "Domain name (e.g. imdue.example.com): " DOMAIN_NAME
  fi
  [ -n "${DOMAIN_NAME}" ] || die 14 "Domain name is required"
  if [[ -z "${CERTBOT_EMAIL:-}" ]]; then
    read -rp "TLS email for Let's Encrypt: " CERTBOT_EMAIL
  fi
  [ -n "${CERTBOT_EMAIL}" ] || die 14 "TLS email is required for HTTPS"
fi

if (( CLEANUP_MODE == 0 )); then
  if [[ -z "${APP_PORT:-}" ]]; then
    read -rp "Application host port (compose defaults to 8000): " APP_PORT
    APP_PORT="${APP_PORT:-8000}"
  fi
  case "${APP_PORT}" in
    ''|*[!0-9]*)
      die 12 "Invalid port number: ${APP_PORT}"
      ;;
  esac
fi

[ -n "${GIT_REPO_URL}" ] || die 10 "Git repository URL is required"
[ -n "${REMOTE_HOST}" ] || die 13 "Remote host/IP is required"

log "INFO" "Parameters collected: repo=${GIT_REPO_URL}, branch=${BRANCH}, host=${REMOTE_HOST}"

WORKDIR="./workspace_${TIMESTAMP}"
mkdir -p "${WORKDIR}"
log "INFO" "Stage 2: Cloning repository into ${WORKDIR}"

CLONE_URL="${GIT_REPO_URL}"
if [[ -n "${GIT_PAT}" && "${GIT_REPO_URL}" =~ ^https:// ]]; then
  CLONE_URL="${GIT_REPO_URL/https:\/\//https://${GIT_PAT}@}"
  log "INFO" "Using Personal Access Token for HTTPS clone"
elif [[ -n "${GIT_PAT}" ]]; then
  log "WARN" "PAT supplied but repository URL is not HTTPS; ensure SSH access is configured"
fi

git clone -b "${BRANCH}" "${CLONE_URL}" "${WORKDIR}/repo"

DEPLOY_MODE="none"
if [[ -f "${WORKDIR}/repo/docker-compose.yml" ]]; then
  DEPLOY_MODE="compose"
  log "INFO" "Detected docker-compose.yml"
elif [[ -f "${WORKDIR}/repo/Dockerfile" ]]; then
  DEPLOY_MODE="dockerfile"
  log "INFO" "Detected Dockerfile"
else
  log "WARN" "No Docker manifest detected; deployment steps will be limited"
fi

git -C "${WORKDIR}/repo" fetch --tags --force 2>/dev/null || true
GIT_VERSION="$(git -C "${WORKDIR}/repo" describe --tags --long 2>/dev/null || git -C "${WORKDIR}/repo" rev-parse HEAD 2>/dev/null || echo 'unknown') ($(git -C "${WORKDIR}/repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown'))"
log "INFO" "Git version: ${GIT_VERSION}"

SSH_BASE_OPTS="-i ${SSH_KEY_PATH} -o BatchMode=yes -o StrictHostKeyChecking=no"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

run_remote_setup() {
  log "INFO" "Stage 3: Preparing remote server environment"
  ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<'EOF'
set -o errexit
set -o nounset
set -o pipefail
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common
if ! command -v docker &>/dev/null; then
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "${USER}" || true
sudo systemctl enable --now docker
if ! command -v nginx &>/dev/null; then
  sudo apt-get install -y nginx
fi
if ! command -v certbot &>/dev/null; then
  sudo apt-get install -y certbot
fi
sudo systemctl enable --now nginx
echo "--- Installed versions ---"
docker --version
docker compose version
nginx -v
certbot --version
EOF
}

run_remote_bootstrap_sudo() {
  log "INFO" "Stage 2.5: Configuring passwordless sudo for ${REMOTE_USER}"
  ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo mkdir -p /etc/sudoers.d
echo "${REMOTE_USER} ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-deploy-nopasswd >/dev/null
sudo chmod 440 /etc/sudoers.d/90-deploy-nopasswd
EOF
}

perform_remote_connectivity_checks() {
  ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" "echo 'SSH_OK'" >/dev/null 2>&1 || die 21 "Cannot SSH into ${REMOTE_HOST}"
  log "INFO" "SSH connectivity verified"
}

if (( CLEANUP_MODE == 1 )); then
  perform_remote_connectivity_checks
  cleanup_remote_resources
  rotate_logs
  log "INFO" "Cleanup-only mode completed"
  exit 0
fi

perform_remote_connectivity_checks
if (( BOOTSTRAP_SUDO == 1 )); then
  run_remote_bootstrap_sudo
fi
run_remote_setup

APP_NAME="$(basename "${GIT_REPO_URL}" .git)"
REMOTE_APP_PATH="/opt/${APP_NAME}"

log "INFO" "Stage 4: Deploying ${APP_NAME} to ${REMOTE_HOST}:${REMOTE_APP_PATH}"
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo mkdir -p '${REMOTE_APP_PATH}'
sudo chown -R '${REMOTE_USER}':'${REMOTE_USER}' '${REMOTE_APP_PATH}'
EOF

RSYNC_OPTS="-avz --delete --exclude 'sessions/' --exclude 'reports/' --exclude 'uploads/' --exclude '.env' -e \"ssh ${SSH_BASE_OPTS}\""
eval rsync ${RSYNC_OPTS} "${WORKDIR}/repo/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_APP_PATH}/"

LOCAL_ENV_FILE=".env"
if [[ -f "${LOCAL_ENV_FILE}" ]]; then
  log "INFO" "Uploading ${LOCAL_ENV_FILE} to ${REMOTE_APP_PATH}/.env"
  scp ${SSH_BASE_OPTS} "${LOCAL_ENV_FILE}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_APP_PATH}/.env"
else
  log "WARN" "${LOCAL_ENV_FILE} not found; skipping remote .env update"
fi

ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
cd '${REMOTE_APP_PATH}'
mkdir -p sessions reports uploads
if [[ -f docker-compose.yml ]]; then
  export GIT_VERSION="${GIT_VERSION}"
  export APP_PORT="${APP_PORT}"
  sudo -E docker compose down || true
  sudo -E docker compose build
  sudo -E docker compose up -d --remove-orphans
elif [[ -f Dockerfile ]]; then
  sudo docker build --build-arg GIT_VERSION="${GIT_VERSION}" -t "${APP_NAME}:latest" .
  sudo docker stop "${APP_NAME}" || true
  sudo docker rm "${APP_NAME}" || true
  sudo docker run -d -p '${APP_PORT}:8000' --env-file .env --name "${APP_NAME}" "${APP_NAME}:latest"
else
  echo "Skipping Docker build because no manifest is present"
fi
sleep 5
if curl -fs "http://localhost:${APP_PORT}" >/dev/null 2>&1; then
  echo "Application reachable on port ${APP_PORT}."
else
  echo "WARNING: Application not responding yet." >&2
fi
EOF

log "INFO" "Stage 5: Configuring Nginx reverse proxy"
NGINX_CONFIG_NAME="${APP_NAME}.conf"
NGINX_PATH="/etc/nginx/sites-available/${NGINX_CONFIG_NAME}"
NGINX_LINK="/etc/nginx/sites-enabled/${NGINX_CONFIG_NAME}"
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo mkdir -p /var/www/certbot
sudo tee ${NGINX_PATH} >/dev/null <<'CONF'
server {
  listen 80;
  listen [::]:80;
  server_name ${DOMAIN_NAME};

  location /.well-known/acme-challenge/ {
    root /var/www/certbot;
  }

  location / {
    return 301 https://\$host\$request_uri;
  }
}
CONF
EOF
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo ln -sf ${NGINX_PATH} ${NGINX_LINK}
sudo nginx -t
sudo systemctl reload nginx
EOF

log "INFO" "Stage 5.1: Requesting TLS certificate"
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo certbot certonly --webroot -w /var/www/certbot -d ${DOMAIN_NAME} -m ${CERTBOT_EMAIL} --agree-tos --non-interactive --keep-until-expiring
sudo systemctl enable --now certbot.timer
EOF

log "INFO" "Stage 5.2: Enabling HTTPS"
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo tee ${NGINX_PATH} >/dev/null <<'CONF'
server {
  listen 80;
  listen [::]:80;
  server_name ${DOMAIN_NAME};

  location /.well-known/acme-challenge/ {
    root /var/www/certbot;
  }

  location / {
    return 301 https://\$host\$request_uri;
  }
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name ${DOMAIN_NAME};

  ssl_certificate /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem;

  client_max_body_size 512M;

  location / {
    proxy_pass http://localhost:${APP_PORT};
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host \$host;
    proxy_cache_bypass \$http_upgrade;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
  }
}
CONF
EOF
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o nounset
set -o pipefail
sudo nginx -t
sudo systemctl reload nginx
EOF

log "INFO" "Stage 6: Validating deployment"
ssh ${SSH_BASE_OPTS} "${SSH_TARGET}" <<EOF
set -o errexit
set -o pipefail
set -o nounset
if sudo systemctl is-active --quiet docker; then
  echo "Docker: Active"
else
  echo "Docker: Inactive"
fi
if sudo systemctl is-active --quiet nginx; then
  echo "Nginx: Active"
else
  echo "Nginx: Inactive"
fi
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
if curl -fs "https://${DOMAIN_NAME}" >/dev/null 2>&1; then
  echo "SUCCESS: Application reachable via Nginx"
else
  echo "ERROR: Application not responding through Nginx!" >&2
  exit 1
fi
EOF

cleanup_remote_resources
rotate_logs
log "INFO" "Deployment completed"
