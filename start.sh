#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
MSF_PASSWORD="${MSF_PASSWORD:-msfrpc}"
LPORT="${LPORT:-4444}"

# LHOST 자동 감지
if [ -z "$LHOST" ]; then
    LHOST=$(ip route get 10.254.254.254 2>/dev/null \
        | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}')
    [ -z "$LHOST" ] && LHOST=$(hostname -I | awk '{print $1}')
fi

R='\033[0;31m'; G='\033[0;32m'; C='\033[0;36m'; Y='\033[1;33m'; N='\033[0m'

echo -e "${C}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║          Web C2 Dashboard            ║"
echo "  ╠══════════════════════════════════════╣"
echo -e "  ║  LHOST  ${Y}$LHOST${C}"
echo -e "  ║  LPORT  ${Y}$LPORT${C}"
echo -e "  ║  DASH   ${Y}http://$LHOST:5000${C}"
echo "  ╚══════════════════════════════════════╝"
echo -e "${N}"

# ── tmux 확인 ─────────────────────────────────────────────────────────────────
if ! command -v tmux &>/dev/null; then
    echo -e "${Y}[*] tmux 설치 중...${N}"
    apt-get install -y tmux -q
fi

# ── 가상환경 ──────────────────────────────────────────────────────────────────
echo -e "${G}[1/3] 가상환경 준비...${N}"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    echo -e "      ${Y}가상환경 생성됨: $VENV${N}"
fi
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/backend/requirements.txt"

# ── 기존 프로세스 정리 ────────────────────────────────────────────────────────
echo -e "${G}[2/3] 기존 프로세스 정리...${N}"
pkill -f msfrpcd            2>/dev/null || true
pkill -f "python.*app\.py"  2>/dev/null || true
fuser -k -n tcp 55553       2>/dev/null || true
fuser -k -n tcp 5000        2>/dev/null || true
sleep 1

# ── msfrpcd 시작 (SSL 기본값 유지) ────────────────────────────────────────────
echo -e "${G}[3/3] msfrpcd 시작 (3초 대기)...${N}"
msfrpcd -P "$MSF_PASSWORD" -f -a 127.0.0.1 -p 55553 \
    >"$SCRIPT_DIR/msfrpcd.log" 2>&1 &
sleep 3

echo -e "\n${G}[+] 준비 완료 — 브라우저에서 접속하세요${N}"
echo -e "    ${Y}http://$LHOST:5000${N}\n"

# ── Flask 대시보드 (포그라운드) ───────────────────────────────────────────────
cd "$SCRIPT_DIR/backend"
exec env MSF_PASSWORD="$MSF_PASSWORD" LHOST="$LHOST" LPORT="$LPORT" \
    "$VENV/bin/python" app.py
