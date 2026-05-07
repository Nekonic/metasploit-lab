import logging
from config import MSF_HOST, MSF_PORT, MSF_PASSWORD

logger = logging.getLogger(__name__)


class MsfClient:
    _instance = None

    def __init__(self):
        self.client = None
        self._connected = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self):
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
            self.client = MsfRpcClient(MSF_PASSWORD, host=MSF_HOST, port=MSF_PORT, ssl=False)
            self._connected = True
            logger.info("MSF-RPC 연결 성공")
            return True
        except Exception as e:
            logger.error(f"MSF-RPC 연결 실패: {e}")
            self._connected = False
            return False

    def reconnect(self):
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
            self.client = MsfRpcClient(MSF_PASSWORD, host=MSF_HOST, port=MSF_PORT, ssl=False)
            self._connected = True
        except Exception as e:
            logger.error(f"재인증 실패: {e}")
            self._connected = False

    def get_sessions(self):
        if not self._connected:
            return {}
        try:
            sessions = self.client.sessions.list
            result = {}
            for sid, info in sessions.items():
                result[str(sid)] = {
                    "id": str(sid),
                    "ip": info.get("session_host", "unknown"),
                    "type": info.get("type", "unknown"),
                    "info": info.get("info", ""),
                    "platform": info.get("platform", ""),
                }
            return result
        except Exception as e:
            logger.error(f"세션 조회 실패: {e}")
            return {}

    def run_command(self, session_id, cmd, timeout=30):
        if not self._connected:
            return None
        try:
            session = self.client.sessions.session(str(session_id))
            result = session.run_with_output(cmd, timeout=timeout)
            return result
        except Exception as e:
            logger.error(f"명령 실행 실패 [{cmd}]: {e}")
            raise

    def kill_all_sessions(self):
        if not self._connected:
            return False
        try:
            sessions = self.client.sessions.list
            for sid in list(sessions.keys()):
                try:
                    self.client.sessions.kill(sid)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Kill all 실패: {e}")
            return False

    def is_connected(self):
        return self._connected
