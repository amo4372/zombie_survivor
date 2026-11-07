"""局域网联机模块：权威主机 + 状态快照客户端（v2.2.7 支持最多 4 人）
主机：监听最多 3 个客户端连接（P1=主机，P2/P3/P4=客户端），
      每连接独立线程接收输入帧（按玩家索引），广播世界快照给所有客户端
客户端：连接主机，发送输入帧，接收并渲染世界快照
协议：TCP + JSON 行帧
  client→host: {"type":"input","data":{...}} / {"type":"hello"}
  host→client: {"type":"welcome","index":N} / {"type":"snapshot","data":{...}}
"""
import socket
import threading
import json
import time

DEFAULT_PORT = 26000
PROTOCOL_VERSION = 2      # v2.9.11：版本不一致直接拒绝，避免跨版本快照解析崩溃
MAX_CLIENTS = 4          # 总人数上限（1 主机 + 3 客户端）
CLIENT_SLOTS = MAX_CLIENTS - 1


class NetHost:
    """主机：监听多个客户端，接收各自输入，广播世界快照"""

    def __init__(self, port=DEFAULT_PORT, room_cfg=None, room_name="幸存者房间",
                 host_name="房主"):
        self.port = port
        self.room_cfg = room_cfg or {}
        self.room_name = room_name or "幸存者房间"
        self.host_name = host_name or "房主"
        self.peers = {}          # idx -> {"nickname", "rtt_ms", "version"}
        self.sock = None
        self.running = False
        self.lock = threading.Lock()
        # 客户端索引（1..CLIENT_SLOTS）-> 连接
        self.clients = {}
        self.inputs = {}
        self.pending_picks = {}  # idx -> 客户端发来的升级选卡下标（房主权威消费）
        self.error = None
        # 兼容旧接口（第一个客户端别名）
        self._primary_conn = None

    @property
    def connected(self):
        """是否至少有一个客户端连接（兼容旧逻辑）"""
        with self.lock:
            return len(self.clients) > 0

    @property
    def client_conn(self):
        """第一个客户端的连接（兼容旧逻辑）"""
        with self.lock:
            return self._primary_conn

    @property
    def client_count(self):
        with self.lock:
            return len(self.clients)

    @property
    def full(self):
        with self.lock:
            return len(self.clients) >= CLIENT_SLOTS

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.sock.bind(("0.0.0.0", self.port))
            self.sock.listen(CLIENT_SLOTS)
            self.running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            return True
        except Exception as e:
            self.error = str(e)
            self.running = False
            return False

    def _accept_loop(self):
        while self.running:
            try:
                conn, _addr = self.sock.accept()
            except Exception:
                break
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            # 分配玩家索引（1..CLIENT_SLOTS）
            with self.lock:
                if len(self.clients) >= CLIENT_SLOTS:
                    full = True
                else:
                    full = False
                    used = set(self.clients.keys())
                    idx = 1
                    while idx in used:
                        idx += 1
                    self.clients[idx] = conn
                    if self._primary_conn is None:
                        self._primary_conn = conn
                    self.inputs[idx] = {}
                    idx_to_send = idx
            if full:
                try:
                    conn.sendall((json.dumps({"type": "full"}) + "\n").encode("utf-8"))
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                continue
            # 欢迎消息：告知客户端其玩家索引 + 房间配置（v2.2.9 网络房间同步）
            try:
                _w = {"type": "welcome", "index": idx_to_send,
                      "version": PROTOCOL_VERSION,
                      "room": self.room_name, "host": self.host_name,
                      "max": MAX_CLIENTS}
                if self.room_cfg:
                    _w["room_cfg"] = self.room_cfg
                conn.sendall((json.dumps(_w) + "\n").encode("utf-8"))
            except Exception:
                pass
            threading.Thread(target=self._recv_loop, args=(idx, conn), daemon=True).start()

    def _recv_loop(self, idx, conn):
        buf = b""
        last_seen = time.time()
        try:
            conn.settimeout(2.0)  # 定期醒来检查 running/心跳，断开及时清理
        except Exception:
            pass
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                last_seen = time.time()
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        _ty = msg.get("type")
                        if _ty == "input":
                            with self.lock:
                                self.inputs[idx] = msg.get("data", {})
                                _pk = (msg.get("data") or {}).get("upgrade_pick")
                                if _pk is not None:
                                    self.pending_picks[idx] = int(_pk)
                        elif _ty == "hello":
                            with self.lock:
                                _p = self.peers.setdefault(idx, {})
                                _p["nickname"] = str(msg.get("nickname", ""))[:16]
                                _p["version"] = int(msg.get("version", 0) or 0)
                        elif _ty == "pong":
                            with self.lock:
                                _p = self.peers.setdefault(idx, {})
                                _t0 = _p.get("ping_t0")
                                if _t0:
                                    _p["rtt_ms"] = round((time.time() - _t0) * 1000, 1)
                        elif _ty == "ping":
                            try:
                                conn.sendall((json.dumps({"type": "pong"}) + "\n").encode("utf-8"))
                            except Exception:
                                pass
                    except Exception:
                        pass
            except socket.timeout:
                # 应用层心跳：超过 8s 无任何数据（含半开连接）→ 判定断开
                if time.time() - last_seen > 8.0:
                    break
                continue
            except Exception:
                break
        # 连接断开：清理该玩家
        with self.lock:
            self.clients.pop(idx, None)
            self.inputs.pop(idx, None)
            self.peers.pop(idx, None)
            self.pending_picks.pop(idx, None)
            if self._primary_conn is conn:
                self._primary_conn = next(iter(self.clients.values()), None)

    def pop_upgrade_pick(self, idx):
        """取出并清除某客户端的升级选择（房主权威：由主机应用技能）"""
        with self.lock:
            return self.pending_picks.pop(idx, None)

    def peer_info(self):
        with self.lock:
            return {k: dict(v) for k, v in self.peers.items()}

    def send_ping(self):
        for idx, conn in list(self.clients.items()):
            try:
                with self.lock:
                    self.peers.setdefault(idx, {})["ping_t0"] = time.time()
                conn.sendall((json.dumps({"type": "ping"}) + "\n").encode("utf-8"))
            except Exception:
                pass

    def get_input(self, idx=1):
        """获取指定索引客户端的最近输入（默认 1=P2，兼容旧逻辑）"""
        with self.lock:
            return dict(self.inputs.get(idx, {}))

    def send_snapshot(self, snap):
        """广播世界快照给所有客户端

        v2.9.12：自动补 `type=snapshot` 信封。此前要求调用方自己包好
        （mix_net 里有包），裸 snap 传进来客户端会静默丢弃 —— 测试脚本
        就踩到了这个坑。现在两种调用都正确。
        """
        if not isinstance(snap, dict) or snap.get("type") != "snapshot":
            snap = {"type": "snapshot", "data": snap}
        payload = (json.dumps(snap) + "\n").encode("utf-8")
        with self.lock:
            conns = list(self.clients.values())
        for conn in conns:
            try:
                conn.sendall(payload)
            except Exception:
                pass

    def stop(self):
        self.running = False
        with self.lock:
            conns = list(self.clients.values())
            self.clients.clear()
            self.inputs.clear()
            self._primary_conn = None
        for conn in conns:
            try:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                conn.close()
            except Exception:
                pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


class NetClient:
    """客户端：连接主机，发送输入帧，接收世界快照"""

    def __init__(self, ip, port=DEFAULT_PORT, nickname="玩家"):
        self.ip = ip
        self.port = port
        self.nickname = nickname or "玩家"
        self.rtt_ms = None
        self.server_room = ""
        self.server_host = ""
        self.server_version = 0
        self.disconnect_reason = None
        self.sock = None
        self.running = False
        self.lock = threading.Lock()
        self.snapshot = {}
        self.connected = False
        self.error = None
        self.player_index = 1  # 主机分配（默认 P2；多人在 1..3）
        self.room_cfg = {}  # v2.2.9 主机下发的房间配置

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.connected = True
            self.running = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            # 发送 hello，等待 welcome 获取玩家索引
            try:
                self.sock.sendall((json.dumps({
                "type": "hello", "nickname": self.nickname,
                "version": PROTOCOL_VERSION}) + "\n").encode("utf-8"))
            except Exception:
                pass
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
                        elif msg.get("type") == "welcome":
                            with self.lock:
                                self.player_index = int(msg.get("index", 1))
                                self.server_version = int(msg.get("version", 0) or 0)
                                self.server_room = str(msg.get("room", ""))
                                self.server_host = str(msg.get("host", ""))
                                if self.server_version and self.server_version != PROTOCOL_VERSION:
                                    self.error = (f"版本不一致：主机 v{self.server_version}，"
                                                  f"本机 v{PROTOCOL_VERSION}，请先更新到同一版本")
                                    self.connected = False
                                _rc = msg.get("room_cfg")
                                if isinstance(_rc, dict):
                                    self.room_cfg = _rc
                        elif msg.get("type") == "ping":
                            try:
                                self.sock.sendall((json.dumps({"type": "pong"}) + "\n").encode("utf-8"))
                            except Exception:
                                pass
                        elif msg.get("type") == "pong":
                            with self.lock:
                                _t0 = getattr(self, "_ping_t0", None)
                                if _t0:
                                    self.rtt_ms = round((time.time() - _t0) * 1000, 1)
                        elif msg.get("type") == "full":
                            with self.lock:
                                self.error = "房间已满"
                            self.connected = False
                    except Exception:
                        pass
            except Exception:
                break
        with self.lock:
            self.connected = False

    def send_ping(self):
        try:
            if self.sock:
                self._ping_t0 = time.time()
                self.sock.sendall((json.dumps({"type": "pong"}) + "\n").encode("utf-8"))
        except Exception:
            pass

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
                # v2.9.12：必须先 shutdown，否则 recv 线程仍持有 socket 引用，
                # 单纯 close 不会中断它的阻塞 recv，对端收不到 FIN →
                # 房主一直认为玩家在线（要等 8s 心跳超时才清理）。
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.sock.close()
        except Exception:
            pass
        self.connected = False
