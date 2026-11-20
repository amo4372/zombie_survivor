# -*- coding: utf-8 -*-
"""局域网房间发现（UDP 广播，v2.9.11 / v2.9.19 加固）

主机每 0.6s 广播一条信标，客户端监听同端口即可看到「同一 WiFi / 同一局域网」
里所有房间，点一下直接加入，不用手输 IP。

v2.9.19：Android 与家用路由常丢弃 255.255.255.255 全局广播，因此同时发送
**子网定向广播**（由本机 IP 推导 /24、/16）与常见热点网段；信标里附带
host_ip，客户端不再依赖 UDP 源地址。监听端加 SO_REUSEPORT，避免端口占用
导致「同一 WiFi 两台设备互相看不见」。

跨网段（邻居家 / 外地）广播到不了，需要走 net_p2p.py 的信令 + 打洞 / 中继，
本模块只负责局域网这一段。
"""
import socket
import threading
import time
import json

BROADCAST_PORT = 26001
MAGIC = "ZSLAN1"


def local_lan_ip():
    """取本机局域网地址（UDP connect 不实际发包），优先私有网段。"""
    _cands = []
    try:
        _sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            _sk.connect(("8.8.8.8", 80))
            _cands.append(_sk.getsockname()[0])
        finally:
            _sk.close()
    except Exception:
        pass
    try:
        _cands.append(socket.gethostbyname(socket.gethostname()))
    except Exception:
        pass
    for _ip in _cands:
        if _ip and _ip != "127.0.0.1" and not _ip.startswith("169.254."):
            return _ip
    return _cands[0] if _cands else "127.0.0.1"


def all_local_addresses():
    """v2.9.21：房主页面列出**全部**网卡地址（含陶瓦/EasyTier 虚拟网卡）。"""
    try:
        from net import local_addresses
        return local_addresses()
    except Exception:
        return [local_lan_ip()]


def broadcast_targets():
    """全局广播 + 子网定向广播 + 常见热点网段。"""
    _out = ["255.255.255.255", "<broadcast>"]
    _ip = local_lan_ip()
    _parts = _ip.split(".")
    if len(_parts) == 4 and _ip != "127.0.0.1":
        _out.append(".".join(_parts[:3]) + ".255")       # /24
        _out.append(".".join(_parts[:2]) + ".255.255")   # /16
    for _p in ("192.168.43.255", "192.168.0.255", "192.168.1.255",
               "10.0.2.255", "172.20.10.255"):
        if _p not in _out:
            _out.append(_p)
    return _out


class RoomBeacon:
    """主机信标：周期性广播房间信息"""

    def __init__(self, tcp_port, room_name="幸存者房间", host_name="房主",
                 max_players=4, mode="TIMED", get_player_count=None,
                 get_started=None):
        self.tcp_port = int(tcp_port)
        self.room_name = room_name or "幸存者房间"
        self.host_name = host_name or "房主"
        self.max_players = int(max_players)
        self.mode = mode
        self.get_player_count = get_player_count
        self.get_started = get_started
        self.running = False
        self.sock = None
        self._th = None
        self.error = None

    def _payload(self):
        try:
            _n = int(self.get_player_count()) if self.get_player_count else 1
        except Exception:
            _n = 1
        try:
            _st = bool(self.get_started()) if self.get_started else False
        except Exception:
            _st = False
        return json.dumps({
            "magic": MAGIC,
            "port": self.tcp_port,
            "host_ip": local_lan_ip(),
            "room": self.room_name,
            "host": self.host_name,
            "players": _n,
            "max": self.max_players,
            "mode": self.mode,
            "started": _st,
            "t": time.time(),
        }, ensure_ascii=False).encode("utf-8")

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
            self.running = True
            self._th = threading.Thread(target=self._loop, daemon=True)
            self._th.start()
            return True
        except Exception as e:
            self.error = str(e)
            self.running = False
            return False

    def _loop(self):
        _targets = broadcast_targets()
        while self.running:
            try:
                _data = self._payload()
                for _addr in _targets:
                    try:
                        self.sock.sendto(_data, (_addr, BROADCAST_PORT))
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.6)

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None


class RoomDiscovery:
    """客户端发现：收集局域网内所有主机信标（带超时清理）"""

    TIMEOUT = 4.0

    def __init__(self):
        self.rooms = {}
        self.running = False
        self.sock = None
        self._th = None
        self.error = None
        self.lock = threading.Lock()

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception:
                pass
            self.sock.bind(("0.0.0.0", BROADCAST_PORT))
            self.sock.settimeout(0.5)
            self.running = True
            self._th = threading.Thread(target=self._loop, daemon=True)
            self._th.start()
            return True
        except Exception as e:
            self.error = str(e)
            self.running = False
            return False

    def _loop(self):
        while self.running:
            try:
                _data, _addr = self.sock.recvfrom(4096)
                _m = json.loads(_data.decode("utf-8", "replace"))
                if _m.get("magic") != MAGIC:
                    continue
                _ip = str(_m.get("host_ip") or _addr[0])
                _key = (_ip, int(_m.get("port", 26000)))
                with self.lock:
                    self.rooms[_key] = {
                        "ip": _ip,
                        "host_ip": _ip,
                        "src_ip": _addr[0],
                        "port": int(_m.get("port", 26000)),
                        "room": str(_m.get("room", "")),
                        "host": str(_m.get("host", "")),
                        "players": int(_m.get("players", 1)),
                        "max": int(_m.get("max", 4)),
                        "mode": str(_m.get("mode", "")),
                        "started": bool(_m.get("started", False)),
                        "last": time.time(),
                    }
            except socket.timeout:
                continue
            except Exception:
                continue

    def list_rooms(self):
        _now = time.time()
        with self.lock:
            for _k in [k for k, v in self.rooms.items()
                       if _now - v["last"] > self.TIMEOUT]:
                self.rooms.pop(_k, None)
            _out = [dict(v, age=round(_now - v["last"], 1))
                    for v in self.rooms.values()]
        return sorted(_out, key=lambda r: (r["started"], r["room"], r["ip"]))

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
