# -*- coding: utf-8 -*-
"""跨网段联机架构（v2.9.11）：传输层抽象 + P2P 打洞 + 中继骨架

设计原则：**房主权威**（Host Authoritative）
  · 客户端只上传输入帧（移动/射击/技能/升级选择），不模拟世界
  · 房主跑完整世界模拟，按 20Hz 广播状态快照
  · 客户端插值渲染快照，所有伤害/掉落/升级判定只在房主发生
  → 天然防作弊，且存档/数据库/回放只在房主一侧维护三种传输路径：

  ┌────────────────┬──────────────────────┬──────────────────────────────┐
  │ 场景           │ 方案                 │ 本版状态                     │
  ├────────────────┼──────────────────────┼──────────────────────────────┤
  │ 同一 WiFi      │ TCP 直连 + UDP 广播  │ ✅ 已完成（net.py +           │
  │                │ 自动发现房间         │    net_discovery.py）         │
  ├────────────────┼──────────────────────┼──────────────────────────────┤
  │ 邻居家 / 同城  │ UDP 打洞（P2P）      │ ⚠️ 骨架已就位，需要一台公网    │
  │ 不同宽带       │ STUN 端点 + 信令交换 │    信令服务器交换端点；        │
  │                │                      │    对称 NAT 需回退中继        │
  ├────────────────┼──────────────────────┼──────────────────────────────┤
  │ 其他地区 /     │ 房间码 + 中继转发    │ ⚠️ 接口已定义，需部署中继      │
  │ 移动网络       │ （Relay）            │    服务；延迟取决于中继位置    │
  └────────────────┴──────────────────────┴──────────────────────────────┘

为什么要信令/中继：两台都在家用路由器后面的设备没有公网 IP，
广播包出不了局域网。必须有一个**双方都能访问的公网节点**帮忙交换
「我看到的外网 IP:端口」，双方同时向对方打洞；打不通就由该节点转发。

本模块把三种方式收敛到同一个 Transport 接口，游戏逻辑（mix_net.py）
只依赖 send/recv/close，未来接入打洞或中继不需要改游戏代码。
"""
import abc
import json
import socket
import threading
import time
import hashlib

SIGNAL_DEFAULT = ("", 26002)     # 留空 = 未部署信令服务器
RELAY_DEFAULT = ("", 26003)


class Transport(abc.ABC):
    """传输层统一接口（房主权威模型下双向都是「输入帧 / 快照」JSON 行）"""

    @abc.abstractmethod
    def send(self, obj: dict) -> bool:
        ...

    @abc.abstractmethod
    def recv(self) -> dict | None:
        """非阻塞取一条消息，无消息返回 None"""
        ...

    @abc.abstractmethod
    def is_connected(self) -> bool:
        ...

    @abc.abstractmethod
    def close(self):
        ...

    @property
    def mode_name(self):
        return self.__class__.__name__


def room_code(seed: str = "") -> str:
    """6 位房间码（跨网加入用，避免手输公网 IP）"""
    _s = (seed or str(time.time())).encode("utf-8")
    _h = hashlib.sha1(_s).hexdigest().upper()
    return _h[:6]


class P2PEndpoint:
    """UDP 打洞端点：向信令服务器登记，并与对端同时发包穿透 NAT。

    注意：这是**骨架**。没有可用的公网信令服务器时 register() 会返回
    False，游戏应自动回退到「房间码 + 中继」或提示用户仍在同一局域网
    直连。真实部署需要：
      1) 一台有公网 IP 的轻量信令服务（交换 ip:port，几 KB/局）
      2) 打洞失败时的 TURN 中继（转发快照，带宽随人数增长）
    """

    def __init__(self, signal_addr=SIGNAL_DEFAULT, local_port=0,
                 room="", nickname="玩家"):
        self.signal_addr = signal_addr
        self.room = room or room_code()
        self.nickname = nickname
        self.sock = None
        self.public_endpoint = None      # (ip, port) 由信令服务回填
        self.peer_endpoint = None
        self.punched = False
        self.error = None

    def register(self):
        """向信令服务器登记本端，拿回公网端点 + 同房间对端列表"""
        _host, _port = self.signal_addr
        if not _host:
            self.error = "未配置公网信令服务器（跨网 P2P 暂不可用）"
            return False
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("", self.local_port))
            self.sock.settimeout(2.0)
            _msg = json.dumps({"op": "register", "room": self.room,
                               "nick": self.nickname}).encode("utf-8")
            self.sock.sendto(_msg, (_host, _port))
            _data, _ = self.sock.recvfrom(4096)
            _r = json.loads(_data.decode("utf-8", "replace"))
            self.public_endpoint = tuple(_r.get("endpoint") or ()) or None
            _peers = _r.get("peers") or []
            if _peers:
                self.peer_endpoint = tuple(_peers[0])
            return bool(self.public_endpoint)
        except Exception as e:
            self.error = f"信令登记失败: {e}"
            return False

    def punch(self, tries=12, interval=0.25):
        """双方同时向对端公网端点发包，在 NAT 上打通映射"""
        if not self.sock or not self.peer_endpoint:
            return False
        for _ in range(tries):
            try:
                self.sock.sendto(b"ZSPUNCH", self.peer_endpoint)
            except Exception:
                pass
            try:
                self.sock.settimeout(interval)
                _d, _a = self.sock.recvfrom(64)
                if _d.startswith(b"ZSPUNCH") and tuple(_a[:2]) == self.peer_endpoint:
                    self.punched = True
                    return True
            except Exception:
                pass
            time.sleep(interval)
        self.error = "打洞失败（多为对称 NAT），请改用房间码中继"
        return False


class RelaySession:
    """房间码中继骨架：客户端与房主都连中继，由中继按房间码转发 JSON 行。

    房主权威不变：房主仍跑完整模拟，中继只是把「输入帧 / 快照」搬运。
    需要部署一台公网中继服务（可复用信令服务器进程）。
    """

    def __init__(self, relay_addr=RELAY_DEFAULT, room="", role="client",
                 nickname="玩家"):
        self.relay_addr = relay_addr
        self.room = room or room_code()
        self.role = role              # "host" / "client"
        self.nickname = nickname
        self.sock = None
        self.connected = False
        self.error = None
        self._buf = b""

    def connect(self):
        _host, _port = self.relay_addr
        if not _host:
            self.error = "未配置中继服务器（跨地区联机暂不可用）"
            return False
        try:
            self.sock = socket.create_connection((_host, _port), timeout=5)
            self.sock.settimeout(0.5)
            self.sock.sendall((json.dumps({
                "op": "join", "room": self.room, "role": self.role,
                "nick": self.nickname}) + "\n").encode("utf-8"))
            self.connected = True
            return True
        except Exception as e:
            self.error = f"中继连接失败: {e}"
            return False

    def send(self, obj):
        try:
            self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            return True
        except Exception:
            self.connected = False
            return False

    def recv(self):
        try:
            _d = self.sock.recv(8192)
            if not _d:
                self.connected = False
                return None
            self._buf += _d
            if b"\n" in self._buf:
                _line, self._buf = self._buf.split(b"\n", 1)
                return json.loads(_line.decode("utf-8", "replace"))
        except socket.timeout:
            return None
        except Exception:
            self.connected = False
        return None

    def close(self):
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


def create_transport(mode="lan", **kw):
    """工厂：lan → 现有 TCP（net.py）；p2p / relay → 本模块骨架。

    游戏侧（mix_net.py）目前只启用 lan；p2p/relay 返回的对象已实现
    send/recv 语义，接入时只需把 NetHost/NetClient 的收发替换掉。
    """
    if mode == "p2p":
        _ep = P2PEndpoint(
            signal_addr=kw.get("signal_addr", SIGNAL_DEFAULT),
            room=kw.get("room", ""), nickname=kw.get("nickname", "玩家"))
        _ok = _ep.register() and _ep.punch()
        return (_ep if _ok else None), (_ep.error if not _ok else None)
    if mode == "relay":
        _r = RelaySession(
            relay_addr=kw.get("relay_addr", RELAY_DEFAULT),
            room=kw.get("room", ""), role=kw.get("role", "client"),
            nickname=kw.get("nickname", "玩家"))
        return (_r if _r.connect() else None), (_r.error if not _r.connected else None)
    return None, "未知传输模式"
