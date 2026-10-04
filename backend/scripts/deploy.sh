#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Deploy
# Deploys the Worker (backend) and Pages (frontend).
#
# Usage:
#   bash backend/scripts/deploy.sh            # deploy both
#   bash backend/scripts/deploy.sh --backend  # Worker only
#   bash backend/scripts/deploy.sh --frontend # Pages only
#   bash backend/scripts/deploy.sh --staging  # deploy to staging
#   bash backend/scripts/deploy.sh --dry-run  # preview only
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

DEPLOY_BACKEND=true
DEPLOY_FRONTEND=true
ENV="production"
DRY_RUN=false
PAGES_PROJECT="marcbantu"

# ---------- Parse args ----------
for arg in "$@"; do
    case $arg in
        --backend)   DEPLOY_FRONTEND=false ;;
        --frontend)  DEPLOY_BACKEND=false ;;
        --staging)   ENV="staging" ;;
        --dry-run)   DRY_RUN=true ;;
        --help|-h)
            echo "Usage: bash deploy.sh [options]"
            echo ""
            echo "Options:"
            echo "  --backend        Deploy only the Worker"
            echo "  --frontend       Deploy only the Pages site"
            echo "  --staging        Deploy to staging environment"
            echo "  --dry-run        Preview without deploying"
            echo ""
            exit 0
            ;;
    esac
done

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}▶${NC} $1"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ---------- Banner ----------
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Marcbantu Africa — Deployment${NC}"
echo -e "${BLUE}║   Environment: ${ENV}${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}║   Mode: DRY RUN (no changes)${NC}"
fi
echo -e "${BLUE}╚═══════════════════════════════════════════════╝${NC}"
echo ""

# ---------- Pre-flight checks ----------
log "Pre-flight checks..."

if ! command -v wrangler &> /dev/null; then
    err "wrangler not found. Install with: npm install -g wrangler"
    exit 1
fi
ok "wrangler installed"

# Check login
if ! wrangler whoami &> /dev/null; then
    err "Not logged in to Cloudflare. Run: wrangler login"
    exit 1
fi
ok "Cloudflare auth OK"

# Check wrangler.toml
if [ ! -f "$ROOT_DIR/wrangler.toml" ]; then
    err "wrangler.toml not found at $ROOT_DIR"
    exit 1
fi
ok "wrangler.toml found"

# ---------- Git status check ----------
if [ -d "$ROOT_DIR/.git" ]; then
    log "Git status:"
    git -C "$ROOT_DIR" status --short | head -20
    if [ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]; then
        warn "You have uncommitted changes"
        if [ "$DRY_RUN" != true ]; then
            read -p "Continue anyway? (y/N): " ans
            if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
                err "Aborted"
                exit 1
            fi
        fi
    else
        ok "Working directory clean"
    fi
fi

# ---------- Deploy Backend ----------
if [ "$DEPLOY_BACKEND" = true ]; then
    step "Deploying Backend (Cloudflare Worker)"

    cd "$ROOT_DIR"

    # Apply remote migrations first
    log "Applying migrations to remote database..."
    if [ -x "$SCRIPT_DIR/db_setup.sh" ]; then
        if [ "$DRY_RUN" != true ]; then
            bash "$SCRIPT_DIR/db_setup.sh" --remote --no-seed
        else
            warn "[DRY RUN] Would run: db_setup.sh --remote --no-seed"
        fi
    fi

    # Deploy
    log "Deploying Worker..."
    if [ "$DRY_RUN" != true ]; then
        if [ "$ENV" = "staging" ]; then
            wrangler deploy --env staging
        else
            wrangler deploy
        fi
        ok "Backend deployed"
    else
        warn "[DRY RUN] Would run: wrangler deploy --env $ENV"
    fi
fi

# ---------- Deploy Frontend ----------
if [ "$DEPLOY_FRONTEND" = true ]; then
    step "Deploying Frontend (Cloudflare Pages)"

    if [ ! -d "$FRONTEND_DIR" ]; then
        err "Frontend directory not found: $FRONTEND_DIR"
        exit 1
    fi

    # Pre-deploy sanity — check for required files
    REQUIRED_FILES=(
        "index.html"
        "dashboard.html"
        "login.html"
        "assets/js/api.js"
        "assets/js/app.js"
        "assets/css/main.css"
        "manifest.json"
        "sw.js"
    )

    for f in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$FRONTEND_DIR/$f" ]; then
            warn "Missing: $f"
        fi
    done

    log "Publishing to Cloudflare Pages..."
    cd "$ROOT_DIR"

    if [ "$DRY_RUN" != true ]; then
        if [ "$ENV" = "staging" ]; then
            wrangler pages deploy "$FRONTEND_DIR" \
                --project-name="${PAGES_PROJECT}-staging" \
                --branch=staging \
                --commit-dirty=true
        else
            wrangler pages deploy "$FRONTEND_DIR" \
                --project-name="$PAGES_PROJECT" \
                --branch=main \
                --commit-dirty=true
        fi
        ok "Frontend deployed"
    else
        warn "[DRY RUN] Would run: wrangler pages deploy"
    fi
fi

# ---------- Post-deploy verification ----------
step "Post-deployment Verification"

if [ "$DRY_RUN" != true ]; then
    # Determine URLs
    if [ "$ENV" = "staging" ]; then
        API_URL="https://marcbantu-api-staging.workers.dev"
    else
        API_URL="https://api.marcbantu.africa"
    fi

    log "Checking API health..."
    sleep 3

    if command -v curl &> /dev/null; then
        HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/health" || echo "000")
        if [ "$HEALTH" = "200" ]; then
            ok "API health: $HEALTH"
            curl -s "$API_URL/api/health" | head -c 200
            echo ""
        else
            warn "API health check returned: $HEALTH"
        fi
    fi
fi

# ---------- Summary ----------
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Deployment Complete${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""

if [ "$DEPLOY_BACKEND" = true ]; then
    if [ "$ENV" = "staging" ]; then
        echo "  Backend:  https://marcbantu-api-staging.workers.dev"
    else
        echo "  Backend:  https://api.marcbantu.africa"
    fi
fi

if [ "$DEPLOY_FRONTEND" = true ]; then
    if [ "$ENV" = "staging" ]; then
        echo "  Frontend: https://marcbantu-staging.pages.dev"
    else
        echo "  Frontend: https://marcbantu.africa"
    fi
fi

echo ""
echo "View logs:"
echo "  wrangler tail"
echo ""