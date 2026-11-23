#!/bin/sh
set -e

# Orchestra Edge Proxy Container Entrypoint
# Enforces strict fail-closed TLS in production:
# - In production (ENVIRONMENT=production), valid trusted certificates MUST exist at
#   /etc/nginx/certs/live/fullchain.pem and /etc/nginx/certs/live/privkey.pem.
#   If missing, the container terminates immediately with a non-zero exit code.
#   Production NEVER falls back to self-signed development certificates.
# - In non-production environments (development, test, local), quarantined self-signed
#   development certificates at /etc/nginx/certs/orchestra_dev.* are used.

ACTIVE_CERTS_DIR="/etc/nginx/certs/active"
mkdir -p "$ACTIVE_CERTS_DIR"
mkdir -p "/var/www/certbot"

if [ "$ENVIRONMENT" = "production" ]; then
    echo "========================================================"
    echo "  Orchestra Edge Reverse Proxy — PRODUCTION MODE"
    echo "========================================================"

    LIVE_CERT="/etc/nginx/certs/live/fullchain.pem"
    LIVE_KEY="/etc/nginx/certs/live/privkey.pem"

    if [ ! -f "$LIVE_CERT" ] || [ ! -f "$LIVE_KEY" ]; then
        echo "FATAL: Production mode requires valid trusted TLS certificates." >&2
        echo "Missing required files: $LIVE_CERT and/or $LIVE_KEY." >&2
        echo "Self-signed certificate fallback in production is strictly prohibited." >&2
        echo "Provision certificates via Certbot / Let's Encrypt before starting." >&2
        exit 1
    fi

    if [ ! -s "$LIVE_CERT" ] || [ ! -s "$LIVE_KEY" ]; then
        echo "FATAL: Production TLS certificate files exist but are empty." >&2
        echo "Check permissions and content of $LIVE_CERT and $LIVE_KEY." >&2
        exit 1
    fi

    # Symlink active certificates to live trusted certificates
    ln -sf "$LIVE_CERT" "$ACTIVE_CERTS_DIR/tls.crt"
    ln -sf "$LIVE_KEY" "$ACTIVE_CERTS_DIR/tls.key"
    echo "Verified trusted production TLS certificates linked to $ACTIVE_CERTS_DIR."
else
    echo "========================================================"
    echo "  Orchestra Edge Reverse Proxy — DEVELOPMENT / TEST MODE"
    echo "========================================================"

    DEV_CERT="/etc/nginx/certs/orchestra_dev.crt"
    DEV_KEY="/etc/nginx/certs/orchestra_dev.key"

    if [ ! -s "$DEV_CERT" ] || [ ! -s "$DEV_KEY" ]; then
        echo "FATAL: Development certificates missing or empty at $DEV_CERT." >&2
        exit 1
    fi

    ln -sf "$DEV_CERT" "$ACTIVE_CERTS_DIR/tls.crt"
    ln -sf "$DEV_KEY" "$ACTIVE_CERTS_DIR/tls.key"
    echo "Development self-signed certificates linked to $ACTIVE_CERTS_DIR."
fi

exec "$@"
