#!/usr/bin/env bash
# Import resources you already created in the Cloudflare dashboard.
# Fill IDs, then: bash import.example.sh
set -euo pipefail
: "${ACCOUNT_ID:?set ACCOUNT_ID}"
: "${APP_ID:?set APP_ID}"
: "${POLICY_EMAIL_ID:?set POLICY_EMAIL_ID}"
# SERVICE_TOKEN_ID / POLICY_SERVICE_ID — only if already created in UI

terraform import -var-file=local.secrets.tfvars \
  'cloudflare_zero_trust_access_policy.allow_email' \
  "${ACCOUNT_ID}/${POLICY_EMAIL_ID}"

# terraform import -var-file=local.secrets.tfvars \
#   'cloudflare_zero_trust_access_service_token.desktop' \
#   "accounts/${ACCOUNT_ID}/${SERVICE_TOKEN_ID}"

# terraform import -var-file=local.secrets.tfvars \
#   'cloudflare_zero_trust_access_policy.service_auth_desktop' \
#   "${ACCOUNT_ID}/${POLICY_SERVICE_ID}"

terraform import -var-file=local.secrets.tfvars \
  'cloudflare_zero_trust_access_application.gateway' \
  "accounts/${ACCOUNT_ID}/${APP_ID}"
