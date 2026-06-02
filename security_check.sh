#!/usr/bin/env bash
set -u -o pipefail

# WSL/Hermes local security healthcheck.
# Non-destructive: reads service state, package status, listeners, permissions, Docker metadata, and Hermes health.

WARNINGS=0
FAILURES=0

section() {
  printf '\n==== %s ====\n' "$1"
}

ok() {
  printf '[OK] %s\n' "$1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAILURES=$((FAILURES + 1))
  printf '[FAIL] %s\n' "$1"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

redact() {
  sed -E 's/(api[_-]?key|token|secret|password|credential|authorization|bearer|gho_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AIza[[:alnum:]_-]+)/[REDACTED]/Ig'
}

check_command() {
  if have "$1"; then ok "command available: $1"; else warn "command missing: $1"; fi
}

section "Host"
date -Is
printf 'user=%s\n' "$(whoami)"
printf 'pwd=%s\n' "$(pwd)"
uname -a
if grep -qi microsoft /proc/version 2>/dev/null; then ok "WSL detected"; else warn "WSL not detected"; fi

section "Required Commands"
for cmd in ss systemctl docker hermes curl apt stat; do
  check_command "$cmd"
done

section "Pending OS Updates"
if have apt; then
  pending_count="$(apt list --upgradable 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
  printf 'pending_updates=%s\n' "$pending_count"
  if [ "$pending_count" = "0" ]; then
    ok "no pending apt upgrades"
  else
    warn "$pending_count apt package(s) pending upgrade"
    apt list --upgradable 2>/dev/null | sed -n '1,30p' | redact
  fi
else
  warn "apt unavailable; skipped package check"
fi

section "Systemd Failed Units"
if have systemctl; then
  system_failed="$(systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')"
  user_failed="$(systemctl --user --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')"
  printf 'system_failed_units=%s\n' "$system_failed"
  printf 'user_failed_units=%s\n' "$user_failed"
  if [ "$system_failed" = "0" ]; then ok "no failed system units"; else fail "failed system units present"; systemctl --failed --no-pager; fi
  if [ "$user_failed" = "0" ]; then ok "no failed user units"; else fail "failed user units present"; systemctl --user --failed --no-pager; fi
else
  warn "systemctl unavailable; skipped failed-unit check"
fi

section "Network Listeners"
if have ss; then
  listeners="$(ss -ltnp 2>/dev/null || true)"
  printf '%s\n' "$listeners" | redact
  external="$(printf '%s\n' "$listeners" | awk 'NR>1 && ($4 ~ /(^0\.0\.0\.0:|^\*:|^\[::\]:|^:::)/) {print}')"
  if [ -n "$external" ]; then
    warn "externally bound TCP listeners found"
    printf '%s\n' "$external" | redact
  else
    ok "no externally bound TCP listeners detected"
  fi
else
  warn "ss unavailable; skipped listener check"
fi

section "Expected Local Services"
if have systemctl; then
  for svc in caddy ssh.socket docker; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then ok "$svc active"; else warn "$svc not active"; fi
  done
  if systemctl --user is-active --quiet hermes-gateway 2>/dev/null; then ok "hermes-gateway active"; else warn "hermes-gateway not active"; fi
fi

section "HTTP Smoke Checks"
if have curl; then
  if curl -fsSI --max-time 5 http://127.0.0.1:80/ >/tmp/security_check_caddy_headers.$$ 2>/dev/null; then
    ok "Caddy localhost HTTP responds"
    sed -n '1,5p' /tmp/security_check_caddy_headers.$$ | redact
  else
    warn "Caddy localhost HTTP did not respond"
  fi
  rm -f /tmp/security_check_caddy_headers.$$

  if curl -fsSI --max-time 5 http://127.0.0.1:8080/ >/tmp/security_check_searxng_headers.$$ 2>/dev/null; then
    ok "SearXNG localhost HTTP responds"
    sed -n '1,5p' /tmp/security_check_searxng_headers.$$ | redact
  else
    warn "SearXNG localhost HTTP did not respond"
  fi
  rm -f /tmp/security_check_searxng_headers.$$
fi

section "Docker"
if have docker; then
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon reachable"
    docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | redact
    if docker inspect searxng >/dev/null 2>&1; then
      docker inspect searxng | python3 -c '
import json, sys
obj=json.load(sys.stdin)[0]
hc=obj.get("HostConfig", {})
ports=obj.get("NetworkSettings", {}).get("Ports", {})
print("searxng_privileged=%s" % hc.get("Privileged"))
print("searxng_cap_drop=%s" % hc.get("CapDrop"))
print("searxng_security_opt=%s" % hc.get("SecurityOpt"))
print("searxng_ports=%s" % ports)
if hc.get("Privileged"):
    sys.exit(2)
if hc.get("CapDrop") != ["ALL"]:
    sys.exit(3)
if "no-new-privileges:true" not in (hc.get("SecurityOpt") or []):
    sys.exit(4)
for bindings in ports.values():
    for b in bindings or []:
        if b.get("HostIp") not in ("127.0.0.1", "::1"):
            sys.exit(5)
' >/tmp/security_check_docker.$$ 2>&1
      docker_status=$?
      cat /tmp/security_check_docker.$$ | redact
      rm -f /tmp/security_check_docker.$$
      case "$docker_status" in
        0) ok "SearXNG container hardening matches baseline" ;;
        2) fail "SearXNG container is privileged" ;;
        3) warn "SearXNG does not drop all capabilities" ;;
        4) warn "SearXNG missing no-new-privileges" ;;
        5) warn "SearXNG has non-localhost published port" ;;
        *) warn "SearXNG Docker hardening check returned status $docker_status" ;;
      esac
    else
      warn "searxng container not found"
    fi
  else
    warn "Docker daemon not reachable"
  fi
else
  warn "docker unavailable; skipped Docker checks"
fi

section "Sensitive File Permissions"
check_perm() {
  local path="$1"
  local expected="$2"
  if [ ! -e "$path" ]; then
    warn "missing $path"
    return
  fi
  local actual
  actual="$(stat -c '%a' "$path" 2>/dev/null || true)"
  stat -c '%A %U:%G %s %n' "$path" 2>/dev/null | redact
  if [ "$actual" = "$expected" ]; then
    ok "$path permission is $expected"
  else
    warn "$path permission is $actual; expected $expected"
  fi
}
check_perm "$HOME/.hermes" 700
check_perm "$HOME/.hermes/config.yaml" 600
check_perm "$HOME/.hermes/.env" 600
check_perm "$HOME/.hermes/auth.json" 600
check_perm "$HOME/.codex" 700
check_perm "$HOME/.codex/auth.json" 600
check_perm "$HOME/.ssh" 700

section "Hermes"
if have hermes; then
  hermes --version 2>&1 | redact || warn "hermes --version failed"
  if hermes doctor >/tmp/security_check_hermes_doctor.$$ 2>&1; then
    ok "hermes doctor completed"
  else
    warn "hermes doctor returned non-zero"
  fi
  tail -45 /tmp/security_check_hermes_doctor.$$ | redact
  rm -f /tmp/security_check_hermes_doctor.$$

  if timeout 120 hermes chat -q 'Health check: reply with exactly HERMES_OK and nothing else.' --quiet >/tmp/security_check_hermes_smoke.$$ 2>&1; then
    if grep -q 'HERMES_OK' /tmp/security_check_hermes_smoke.$$; then
      ok "Hermes model/provider smoke test passed"
    else
      warn "Hermes smoke completed but expected token missing"
    fi
  else
    warn "Hermes model/provider smoke test failed"
  fi
  cat /tmp/security_check_hermes_smoke.$$ | redact
  rm -f /tmp/security_check_hermes_smoke.$$
else
  warn "hermes unavailable; skipped Hermes checks"
fi

section "Summary"
printf 'warnings=%s\n' "$WARNINGS"
printf 'failures=%s\n' "$FAILURES"
if [ "$FAILURES" -gt 0 ]; then
  printf 'status=FAIL\n'
  exit 2
fi
if [ "$WARNINGS" -gt 0 ]; then
  printf 'status=WARN\n'
  exit 1
fi
printf 'status=OK\n'
exit 0
