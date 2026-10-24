"""局域网联机模块：权威主机 + 状态快照客户端
主机：监听客户端连接，接收客户端输入帧，广播世界快照
客户端：连接主机，发送输入帧，接收并渲染世界快照
协议：TCP + JSON 行帧
"""
import socket
import threading
import json

DEFAULT_PORT = 26000


class NetHost:
    """主机：监听一个客户端，接收其输入，发送世界快照"""

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.sock = None
        self.client_conn = None
        self.running = False
        self.lock = threading.Lock()
        self.client_input = {}
        self.connected = False
        self.error = None

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 低延迟：禁用 Nagle 算法，小包立即发送
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.sock.bind(("0.0.0.0", self.port))
            self.sock.listen(1)
            self.running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            return True
        except Exception as e:
            self.error = str(e)
            self.running = False
            return False

    def _accept_loop(self):
        try:
            conn, _addr = self.sock.accept()
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            with self.lock:
                self.client_conn = conn
                self.connected = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
        except Exception:
            pass

    def _recv_loop(self):
        buf = b""
        while self.running:
            try:
                data = self.client_conn.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        if msg.get("type") == "input":
                            with self.lock:
                                self.client_input = msg.get("data", {})
                    except Exception:
                        pass
            except Exception:
                break
        with self.lock:
            self.connected = False

    def get_input(self):
        with self.lock:
            return dict(self.client_input)

    def send_snapshot(self, snap):
        try:
            if self.client_conn:
                self.client_conn.sendall((json.dumps(snap) + "\n").encode("utf-8"))
        except Exception:
            pass

    def stop(self):
        self.running = False
        try:
            if self.client_conn:
                self.client_conn.close()
            if self.sock:
                self.sock.close()
        except Exception:
            pass


class NetClient:
    """客户端：连接主机，发送输入帧，接收世界快照"""

    def __init__(self, ip, port=DEFAULT_PORT):
        self.ip = ip
        self.port = port
        self.sock = None
        self.running = False
        self.lock = threading.Lock()
        self.snapshot = {}
        self.connected = False
        self.error = None

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
            # 低延迟：禁用 Nagle 算法
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.connected = True
            self.running = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except Exception as e:
            self.error = str(e)
            self.connected = False
            return False

    def _recv_loop(self):
        buf = b""
        while self.running:
            try:
                data = self.sock.recv(8192)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        if msg.get("type") == "snapshot":
                            with self.lock:
                                self.snapshot = msg.get("data", {})
                    except Exception:
                        pass
            except Exception:
                break
        with self.lock:
            self.connected = False

    def send_input(self, data):
        try:
            if self.sock:
                self.sock.sendall((json.dumps({"type": "input", "data": data}) + "\n").encode("utf-8"))
        except Exception:
            pass

    def get_snapshot(self):
        with self.lock:
            return dict(self.snapshot)

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
