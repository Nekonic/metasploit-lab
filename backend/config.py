import os
import socket


def _detect_local_ip():
    # 실제 패킷을 보내지 않고 라우팅 테이블로 현재 아웃바운드 IP 감지
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0)
            s.connect(("10.254.254.254", 1))
            return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())


MSF_HOST = os.environ.get("MSF_HOST", "127.0.0.1")
MSF_PORT = int(os.environ.get("MSF_PORT", 55553))
MSF_PASSWORD = os.environ.get("MSF_PASSWORD", "msfrpc")
TOKEN_REFRESH_INTERVAL = 240

# LHOST: 환경변수로 고정 가능, 없으면 실행 시점 IP 자동 감지
LHOST = os.environ.get("LHOST") or _detect_local_ip()
LPORT = int(os.environ.get("LPORT", 4444))

UPLOAD_DIR = "/tmp/demo_uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif"}
ALLOWED_AUDIO_EXT = {"wav", "mp3"}
