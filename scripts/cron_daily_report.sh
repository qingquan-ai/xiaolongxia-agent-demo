#!/usr/bin/env bash

set -u

APP_DIR="/root/xiaolongxia-agent-demo"
ENV_FILE="$APP_DIR/.env"
LOG_FILE="$APP_DIR/cron_daily_report.log"
RESPONSE_FILE="/tmp/xiaolongxia_cron_daily_response.json"
REPORT_URL="http://127.0.0.1:8000/api/reports/daily"

cleanup() {
  rm -f "$RESPONSE_FILE"
}
trap cleanup EXIT

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log_line() {
  printf '[%s] %s\n' "$(timestamp)" "$1" >> "$LOG_FILE"
}

trim_value() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_outer_quotes() {
  local value="$1"
  if [[ ${#value} -ge 2 ]]; then
    if [[ ${value:0:1} == '"' && ${value: -1} == '"' ]]; then
      value="${value:1:${#value}-2}"
    elif [[ ${value:0:1} == "'" && ${value: -1} == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi
  printf '%s' "$value"
}

read_cron_secret() {
  local line
  local value

  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi

  line="$(grep -E '^[[:space:]]*CRON_SECRET[[:space:]]*=' "$ENV_FILE" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi

  value="${line#*=}"
  value="$(trim_value "$value")"
  value="$(strip_outer_quotes "$value")"
  if [[ -z "$value" ]]; then
    return 1
  fi

  printf '%s' "$value"
}

log_line "cron daily report started"

CRON_SECRET="$(read_cron_secret || true)"
if [[ -z "$CRON_SECRET" ]]; then
  log_line "result=failed reason=CRON_SECRET missing"
  log_line "cron daily report finished"
  exit 1
fi

HTTP_STATUS="$(
  curl -sS \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$REPORT_URL" \
    -H "X-Cron-Secret: $CRON_SECRET"
)"
CURL_EXIT_CODE=$?

RESPONSE_BODY=""
if [[ -f "$RESPONSE_FILE" ]]; then
  RESPONSE_BODY="$(cat "$RESPONSE_FILE")"
fi

log_line "http_status=$HTTP_STATUS"
log_line "curl_exit_code=$CURL_EXIT_CODE"
log_line "response=$RESPONSE_BODY"

if [[ "$CURL_EXIT_CODE" -eq 0 && "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]; then
  log_line "result=success"
  log_line "cron daily report finished"
  exit 0
fi

log_line "result=failed"
log_line "cron daily report finished"
exit 1
