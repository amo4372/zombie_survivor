# -*- coding: utf-8 -*-
"""训练测评报告生成 —— HTML + 内嵌 SVG（零第三方依赖）

输入：评估数据 dict
    {
      "model": "rl/models/ppo_zombie_v2.zip",
      "device": "cpu",
      "total_timesteps": 30000,
      "train_time_min": 0.4,
      "history": [{"step": 0, "mean_reward": -10.2}, ...],   # 训练过程曲线
      "eval": {                                              # 每类型评估
        "normal": {"rewards": [...], "wins": 4, "deaths": 2,
                   "episodes": 8, "avg_steps": 450, "avg_bites": 1.2},
        ...
      }
    }
输出：rl/reports/report_<ts>.html + report_<ts>.json
"""
import os
import json
import time
import html as _html


def _sma(values, window=5):
    """滑动平均（窗口默认5，末端保留原始值避免拖尾）"""
    if len(values) <= window:
        return values
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        out.append(sum(values[lo:i + 1]) / (i - lo + 1))
    return out


def _svg_line_chart(points, w=720, h=260, color="#4fc3f7"):
    """训练 reward 曲线 → 原始 polyline + 面积 + 滑动平均趋势线"""
    if len(points) < 2:
        return "<p>训练过程数据不足，无法绘制曲线</p>"
    xs = [p["step"] for p in points]
    ys = [p["mean_reward"] for p in points]
    sm = _sma(ys, window=max(3, min(8, len(points) // 3)))
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(min(ys), min(sm)), max(max(ys), max(sm))
    pad = 24
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1
    def px(x):
        return pad + (x - x0) / (x1 - x0) * (w - 2 * pad)
    def py(y):
        return h - pad - (y - y0) / (y1 - y0) * (h - 2 * pad)
    pts = " ".join(f"{px(p['step']):.1f},{py(p['mean_reward']):.1f}" for p in points)
    sm_pts = " ".join(f"{px(xs[i]):.1f},{py(sm[i]):.1f}" for i in range(len(sm)))
    area = f"{px(x0):.1f},{py(y0):.1f} {pts} {px(x1):.1f},{py(y0):.1f}"
    ticks = ""
    for v in [y0, (y0 + y1) / 2, y1]:
        ticks += f'<text x="{pad-6}" y="{py(v)+4}" font-size="11" fill="#999" text-anchor="end">{v:.0f}</text>'
    xlabels = ""
    for i in range(5):
        xi = x0 + (x1 - x0) * i / 4
        xlabels += f'<text x="{px(xi):.1f}" y="{h-8}" font-size="11" fill="#999" text-anchor="middle">{int(xi)}</text>'
    return f'''<svg viewBox="0 0 {w} {h}" width="100%" style="background:#14171c;border-radius:10px">
  <polygon points="{area}" fill="{color}" opacity="0.10"/>
  <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" opacity="0.45"/>
  <polyline points="{sm_pts}" fill="none" stroke="#ffb74d" stroke-width="3"/>
  {ticks}{xlabels}
  <text x="{pad}" y="14" font-size="12" fill="#aaa">训练过程 平均奖励（细线=原始 / 橙粗线=滑动平均趋势）</text>
</svg>'''


def _svg_stacked_bar(rows, series_names, series_colors, w=720, h=260, title="技能使用"):
    """堆叠柱状图：rows=[(label, [v1,v2,...]), ...]"""
    labels = [r[0] for r in rows]
    vals = [[float(v) for v in r[1]] for r in rows]
    mx = max([sum(v) for v in vals] + [1.0])
    pad_l, pad_b, pad_t, pad_r = 44, 40, 30, 16
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b
    def px(i): return pad_l + cw * (i + 0.5) / max(len(rows), 1)
    def py(v): return pad_t + ch * (1 - v / mx)
    bars = ""
    bw = min(cw / max(len(rows), 1) * 0.6, 60)
    for i, vs in enumerate(vals):
        acc = 0.0
        for j, v in enumerate(vs):
            if v <= 0:
                continue
            col = series_colors.get(list(series_names.keys())[j], "#888")
            bars += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (
                px(i) - bw / 2, py(acc + v), bw, max(v / mx * ch, 1), col)
            acc += v
    labs = "".join(
        '<text x="%.1f" y="%.0f" font-size="11" fill="#aaa" text-anchor="middle">%s</text>' % (
            px(i), h - pad_b + 16, _html.escape(str(labels[i])))
        for i in range(len(rows)))
    leg = "".join(
        '<rect x="%.0f" y="%.0f" width="10" height="10" fill="%s"/><text x="%.0f" y="%.0f" font-size="11" fill="#ccc">%s</text>' % (
            w - 180, pad_t + j * 16, series_colors[k], w - 164, pad_t + j * 16 + 10, _html.escape(str(v)))
        for j, (k, v) in enumerate(series_names.items()))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            '<text x="%d" y="14" font-size="12" fill="#aaa">%s</text>'
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2a3140"/><line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2a3140"/>'
            '%s%s%s</svg>') % (
            w, h, w, h, pad_l, _html.escape(title), pad_l, pad_t, pad_l, h - pad_b,
            pad_l, h - pad_b, w - pad_r, h - pad_b, bars, labs, leg)


def _svg_pair_bar(rows, w=720, h=260, title="伤害"):
    """双柱对比：rows=[(label, v1, v2), ...]"""
    labels = [r[0] for r in rows]
    v1 = [float(r[1]) for r in rows]
    v2 = [float(r[2]) for r in rows]
    mx = max(max(v1 + v2, default=0), 1.0)
    pad_l, pad_b, pad_t, pad_r = 44, 40, 30, 16
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b
    def px(i): return pad_l + cw * (i + 0.5) / max(len(rows), 1)
    def py(v): return pad_t + ch * (1 - v / mx)
    bw = min(cw / max(len(rows), 1) * 0.4, 46)
    bars = ""
    for i in range(len(rows)):
        bars += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#4fc3f7"/>' % (
            px(i) - bw - 2, py(v1[i]), bw, max(v1[i] / mx * ch, 1))
        bars += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#ffb74d"/>' % (
            px(i) + 2, py(v2[i]), bw, max(v2[i] / mx * ch, 1))
    labs = "".join(
        '<text x="%.1f" y="%.0f" font-size="11" fill="#aaa" text-anchor="middle">%s</text>' % (
            px(i), h - pad_b + 16, _html.escape(str(labels[i])))
        for i in range(len(rows)))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            '<text x="%d" y="14" font-size="12" fill="#aaa">%s</text>'
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2a3140"/><line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2a3140"/>'
            '%s%s'
            '<rect x="%.0f" y="%.0f" width="10" height="10" fill="#4fc3f7"/><text x="%.0f" y="%.0f" font-size="11" fill="#ccc">输出</text>'
            '<rect x="%.0f" y="%.0f" width="10" height="10" fill="#ffb74d"/><text x="%.0f" y="%.0f" font-size="11" fill="#ccc">承受</text>'
            '</svg>') % (
            w, h, w, h, pad_l, _html.escape(title), pad_l, pad_t, pad_l, h - pad_b,
            pad_l, h - pad_b, w - pad_r, h - pad_b, bars, labs,
            w - 170, pad_t, w - 154, pad_t + 10, w - 170, pad_t + 18, w - 154, pad_t + 28)




def _svg_bar_chart(rows, labels, w=720, h=260, color="#ffb74d"):
    """横向条形图（每类型多指标）"""
    if not rows:
        return ""
    pad_l = 90
    pad_r = 60
    n = len(rows)
    bar_h = (h - 40) / n
    parts = []
    for i, (lab, val) in enumerate(zip(labels, rows)):
        y = 20 + i * bar_h
        vmax = max(rows) or 1
        bw = max(6, (w - pad_l - pad_r) * val / vmax)
        parts.append(f'''<text x="{pad_l-8}" y="{y+bar_h/2+4}" font-size="12" fill="#ccc" text-anchor="end">{_html.escape(lab)}</text>
<rect x="{pad_l}" y="{y+4}" width="{bw:.1f}" height="{bar_h-10}" rx="4" fill="{color}" opacity="0.85"/>
<text x="{pad_l+bw+6:.1f}" y="{y+bar_h/2+4}" font-size="11" fill="#eee">{val}</text>''')
    return f'''<svg viewBox="0 0 {w} {h}" width="100%" style="background:#14171c;border-radius:10px">{''.join(parts)}</svg>'''


def build_report(data, out_dir="rl/reports"):
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    ev = data.get("eval", {})
    types = list(ev.keys())
    # 平均奖励条形
    avg_rew = [float(sum(ev[t]["rewards"]) / max(len(ev[t]["rewards"]), 1)) for t in types]
    win_rate = [ev[t]["wins"] / max(ev[t]["episodes"], 1) for t in types]
    avg_steps = [ev[t]["avg_steps"] for t in types]
    skill_keys = ["spit", "dash", "summon", "aoe", "throw"]
    skill_names = {"spit": "吐酸", "dash": "冲刺", "summon": "召唤", "aoe": "咆哮", "throw": "投掷"}
    skill_colors = {"spit": "#4fc3f7", "dash": "#ffb74d", "summon": "#81c784", "aoe": "#f06292", "throw": "#ba68c8"}
    # 表格行
    rows = ""
    for t in types:
        e = ev[t]
        ar = avg_rew[types.index(t)]
        wr = win_rate[types.index(t)]
        sk_sum = sum(float(e["skills"].get(k, 0)) for k in skill_keys)
        rows += f'''<tr><td><b>{_html.escape(t)}</b></td>
<td>{ar:.1f}</td><td style="color:{"#4caf50" if e["wins"] else "#999"}">{e["wins"]}/{e["episodes"]}</td>
<td>{wr*100:.0f}%</td><td>{e["deaths"]}/{e["episodes"]}</td>
<td>{e.get("avg_dmg_dealt",0):.0f}</td><td>{e.get("avg_dmg_taken",0):.0f}</td>
<td>{e.get("avg_move",0)/1000:.1f}k</td><td>{e.get("avg_bite_hits",0):.1f}</td>
<td>{e.get("avg_spit_hits",0):.1f}</td><td>{e.get("avg_throw_hits",0):.1f}</td>
<td>{e.get("avg_hazard",0):.1f}</td><td>{sk_sum:.1f}</td><td>{e["avg_steps"]:.0f}</td></tr>'''
    # 技能使用分布（堆叠柱）+ 伤害输出/承受（双柱）
    sk_svg = _svg_stacked_bar(
        [(t, [ev[t]["skills"].get(k, 0) for k in skill_keys]) for t in types],
        skill_names, skill_colors, title="各僵尸类型技能使用次数/局（含投掷）")
    dmg_svg = _svg_pair_bar(
        [(t, ev[t].get("avg_dmg_dealt", 0), ev[t].get("avg_dmg_taken", 0)) for t in types],
        title="每局平均伤害：输出(蓝) vs 承受(橙)")
    hist_svg = _svg_line_chart(data.get("history", []))
    bar_svg = _svg_bar_chart(avg_rew, types)
    bar2_svg = _svg_bar_chart([wr * 100 for wr in win_rate], types, color="#81c784")
    html_doc = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>僵尸AI 训练测评报告</title>
<style>
body{{background:#0e1116;color:#ddd;font-family:"Microsoft YaHei",sans-serif;margin:0;padding:24px}}
h1{{color:#fff;font-size:22px}} h2{{color:#4fc3f7;font-size:17px;margin-top:28px}}
.card{{background:#1a1f27;border:1px solid #2a3140;border-radius:12px;padding:16px;margin-top:12px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #2a3140;padding:8px 10px;text-align:center}}
th{{background:#20272f;color:#8fd0ff}} .tag{{color:#ffb74d;font-size:12px}}
.verdict{{color:#81c784;font-weight:bold}}
</style></head><body>
<h1>🧟 僵尸AI 训练测评报告</h1>
<div class="tag">模型: {_html.escape(data.get("model",""))} · 设备: {_html.escape(data.get("device",""))} ·
训练步数: {data.get("total_timesteps",0):,} · 耗时: {("仅评估模式（断点累计训练耗时见训练日志）" if data.get("train_time_min",0)<=0 else f"{data['train_time_min']:.1f} 分钟")}</div>
<h2>训练过程</h2><div class="card">{hist_svg}</div>
<h2>各僵尸类型平均奖励</h2><div class="card">{bar_svg}</div>
<h2>各僵尸类型玩家击杀率 (%)</h2><div class="card">{bar2_svg}</div>
<h2>每局伤害：输出 vs 承受</h2><div class="card">{dmg_svg}</div>
<h2>技能使用分布（含投掷）</h2><div class="card">{sk_svg}</div>
<h2>详细数据</h2><div class="card"><table>
<tr><th>类型</th><th>平均奖励</th><th>击杀玩家</th><th>击杀率</th><th>自身死亡</th><th>伤害输出</th><th>承受伤害</th><th>移动(k)</th><th>咬中</th><th>吐酸命中</th><th>投掷命中</th><th>地形惩罚</th><th>技能次数</th><th>存活步数</th></tr>
{rows}</table>
<div style="margin-top:12px" class="tag">结论：
{_verdict(data)}
</div></div>
</body></html>'''
    html_path = os.path.join(out_dir, f"report_{ts}.html")
    json_path = os.path.join(out_dir, f"report_{ts}.json")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=float)
    print(f"[REPORT] 测评报告已生成: {html_path}")
    print(f"[REPORT] 原始数据: {json_path}")
    return html_path


def _verdict(data):
    """自动结论：用数据说话"""
    ev = data.get("eval", {})
    if not ev:
        return "无评估数据，请先训练。"
    best = max(ev, key=lambda t: (sum(ev[t]["rewards"]) / max(len(ev[t]["rewards"]), 1), ev[t]["wins"]))
    e = ev[best]
    wr = e["wins"] / max(e["episodes"], 1)
    s = f"综合最强: <b>{best}</b>（平均奖励 {sum(e['rewards'])/max(len(e['rewards']),1):.1f}，击杀率 {wr*100:.0f}%）"
    any_win = any(ev[t]["wins"] > 0 for t in ev)
    s += "<br>整体策略" + ("<span class='verdict'>已学会击杀玩家</span>" if any_win else "尚未击杀玩家（需继续训练/调奖励）")
    return s
