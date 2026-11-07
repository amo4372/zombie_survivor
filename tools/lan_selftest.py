#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单设备联机自检（v2.9.12）

只有一台设备时，用**本机 TCP 回环**把「房主 + 客户端」两个角色
在同一进程里跑起来，验证 v2.9.11 的完整联机链路。
不需要第二台手机/电脑，也不需要真的连 WiFi。

用法：
    python tools/lan_selftest.py
    python tools/lan_selftest.py --quick     # 跳过 RTT / 信标（更快）

另外（可选）同一台设备真开两个游戏窗口：
    1) 窗口 A：主菜单 → 多人联机 → 创建房间（监听 26000）
    2) 窗口 B：主菜单 → 多人联机 → IP 填 127.0.0.1 → 加入
    客户端不 bind 端口，所以两个进程在一台机器上不冲突。
    注意：两进程共用同一份 config.json / 存档，仅用于验证联机，别用来刷记录。
"""
import os
import sys
import time
import socket
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK]  " + label)
    else:
        FAIL += 1
        print("  [FAIL]" + label)


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    quick = "--quick" in sys.argv
    import net

    print("=== 丧尸幸存者 单设备联机自检 (v2.9.12) ===")
    print("本机回环，无需第二台设备 / 无需 WiFi\n")

    port = free_port()

    # ---- 1) 房间发现（UDP 广播 -> 本机探针） ----
    if not quick:
        try:
            from net_discovery import RoomBeacon, RoomDiscovery, BROADCAST_PORT
            beacon = RoomBeacon(port, room_name="单设备测试房",
                                host_name="本机房主",
                                get_player_count=lambda: 1)
            payload = beacon._payload()
            _m = __import__("json").loads(payload.decode("utf-8"))
            check(_m.get("room") == "单设备测试房" and _m.get("host") == "本机房主",
                  "UDP 信标 payload 含房间名 / 房主名")
            check(_m.get("port") == port, "信标携带 TCP 端口（点房间即可加入）")
            beacon.start()
            disc = RoomDiscovery()
            _dok = disc.start()
            time.sleep(1.35)
            rooms = disc.list_rooms() if _dok else []
            if any(r.get("room") == "单设备测试房" for r in rooms):
                check(True, "UDP 广播在本机可被发现")
            else:
                print("  [WARN] 本机回环未收到 UDP 广播（255.255.255.255 不回环，"
                      "属正常；真机同一 WiFi 下可发现）")
            beacon.stop()
            disc.stop()
        except Exception as e:
            check(False, f"房间发现异常: {e}")

    # ---- 2) TCP 回环：房主 + 客户端 ----
    host = net.NetHost(port, room_cfg={"difficulty": "普通", "mode": "无尽"},
                       room_name="回环房", host_name="房主A")
    ok = host.start()
    check(ok, f"房主监听 127.0.0.1:{port} 成功 ({host.error or 'OK'})")
    if not ok:
        print(f"\n===== 自检: PASS={PASS} FAIL={FAIL} =====")
        return 1

    cli = net.NetClient("127.0.0.1", port, nickname="测试P2")
    check(cli.start(), f"客户端连接成功 ({cli.error or 'OK'})")
    time.sleep(0.3)
    check(cli.connected, "客户端 connected = True")
    check(cli.player_index == 1, f"分配玩家索引 P2 ({cli.player_index})")
    check(cli.server_version == net.PROTOCOL_VERSION,
          f"协议版本握手一致 (v{cli.server_version})")
    check(cli.server_room == "回环房" and cli.server_host == "房主A",
          "welcome 下发房间名 / 房主名")
    check(cli.room_cfg.get("difficulty") == "普通", "房间配置下发")

    # ---- 3) 输入帧 / 房主权威升级 ----
    cli.send_input({"mx": 1.0, "my": -0.5, "shoot": True, "upgrade_pick": 2})
    time.sleep(0.25)
    inp = host.get_input(1)
    check(inp.get("mx") == 1.0 and inp.get("my") == -0.5,
          "移动/射击输入帧送达房主")
    check(host.pop_upgrade_pick(1) == 2, "升级选卡下标送达房主（房主权威）")
    check(host.pop_upgrade_pick(1) is None, "选卡下标只消费一次（不重复升级）")

    # ---- 4) 快照广播 ----
    host.send_snapshot({"t": 1.0, "players": [{"x": 10, "y": 20},
                                              {"x": 60, "y": 20}],
                        "enemies": [], "wave": 1})
    time.sleep(0.25)
    snap = cli.get_snapshot()
    check(bool(snap) and snap.get("wave") == 1, "世界快照广播到客户端")

    # ---- 5) ping / RTT / 昵称 ----
    if not quick:
        host.send_ping()
        time.sleep(0.35)
        info = host.peer_info()
        check(1 in info and info[1].get("nickname") == "测试P2",
              "房主拿到客户端昵称")
        check("rtt_ms" in info.get(1, {}), "ping/pong 测出 RTT")

    # ---- 6) 断线清理 ----
    cli.stop()
    time.sleep(0.9)
    check(not host.connected, "客户端断开后房主清理连接")

    host.stop()
    print(f"\n===== 自检: PASS={PASS} FAIL={FAIL} =====")
    if FAIL:
        print("有失败项，请把输出贴给开发者。")
        return 1
    print("联机协议链路全部正常。")
    print("提示：同一台设备还可以真开两个游戏窗口，")
    print("      A 建房、B 填 127.0.0.1 加入，验证实际画面与操作。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
