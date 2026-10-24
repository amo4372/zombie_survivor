#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLSL GPU 渲染后端（可选，v2.1.7）。

PC 端用 OpenGL 3.3+ / Android 用 OpenGL ES 2.0+（moderngl standalone context，经 EGL）。
将「光源合成 → 暗角 → 锐化 → 色调/饱和度 → 低血量红屏 → 爆闪」整条后处理链
用 GLSL 在 GPU 一步完成，替代 CPU 的逐帧 surface 混合；并提供精灵纹理批渲染接口。

安全设计：
- moderngl 未安装 / context 初始化失败 / 运行异常 → available=False，游戏完整回退 pygame 原生渲染；
- 所有公开方法内部捕获异常并返回 None/原样，绝不抛出到游戏主循环。
"""
import math
import pygame


class GLRenderer:
    """GLSL 渲染后端单例（游戏内共享一个实例）"""

    # ---- 合成 shader：光源挖洞 + 暗角 + 后处理链 ----
    _COMPOSITE_VERT = """
#version 100
attribute vec2 in_pos;
attribute vec2 in_uv;
varying vec2 v_uv;
void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

    _COMPOSITE_FRAG = """
#version 100
precision mediump float;
uniform sampler2D u_light;
uniform float u_ambient;
uniform float u_vignette;
varying vec2 v_uv;
void main() {
    vec4 l = texture2D(u_light, v_uv);
    float dark = clamp(u_ambient / 255.0 - l.a, 0.0, 1.0);
    if (u_vignette > 0.5) {
        float d = length(v_uv - vec2(0.5, 0.5)) * 1.15;
        dark *= clamp(1.0 - smoothstep(0.45, 1.0, d), 0.0, 1.0);
    }
    gl_FragColor = vec4(0.0, 0.0, 0.0, dark);
}
"""

    # ---- 后处理 shader：锐化 + 饱和度/亮度/对比度 + 低血量红屏 + 爆闪 ----
    _POST_VERT = """
#version 100
attribute vec2 in_pos;
attribute vec2 in_uv;
varying vec2 v_uv;
void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

    _POST_FRAG = """
#version 100
precision mediump float;
uniform sampler2D u_tex;
uniform vec2 u_texel;
uniform float u_sharpen;   // 0 或 1
uniform float u_sat;       // 饱和度倍数（1.0 = 原样）
uniform float u_hurt;      // 0~1 低血量红屏强度
uniform float u_flash;     // 0~1 爆闪
uniform float u_bright;    // 亮度微调
varying vec2 v_uv;

float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

void main() {
    vec4 c = texture2D(u_tex, v_uv);

    // 1) 锐化（3x3 拉普拉斯，保留 HUD 可读性的轻量锐化）
    if (u_sharpen > 0.5) {
        vec3 sum = vec3(0.0);
        sum += texture2D(u_tex, v_uv + vec2(-u_texel.x, -u_texel.y)).rgb * -1.0;
        sum += texture2D(u_tex, v_uv + vec2( u_texel.x, -u_texel.y)).rgb * -1.0;
        sum += texture2D(u_tex, v_uv + vec2(-u_texel.x,  u_texel.y)).rgb * -1.0;
        sum += texture2D(u_tex, v_uv + vec2( u_texel.x,  u_texel.y)).rgb * -1.0;
        sum += c.rgb * 4.0;
        c.rgb = clamp(c.rgb + (sum * 0.18), 0.0, 1.0);
    }

    // 2) 饱和度
    float g = luma(c.rgb);
    c.rgb = mix(vec3(g), c.rgb, u_sat);

    // 3) 亮度
    c.rgb = clamp(c.rgb + u_bright, 0.0, 1.0);

    // 4) 低血量红屏：边缘渐强红色（中心保持可读）
    if (u_hurt > 0.01) {
        float edge = smoothstep(0.45, 0.95, length(v_uv - vec2(0.5, 0.5)) * 1.05);
        c.rgb = mix(c.rgb, vec3(1.0, 0.25, 0.25), u_hurt * edge * 0.85);
    }

    // 5) 爆闪
    if (u_flash > 0.01) {
        c.rgb = mix(c.rgb, vec3(1.0, 1.0, 1.0), u_flash);
    }

    gl_FragColor = vec4(c.rgb, c.a);
}
"""

    _instance = None

    @classmethod
    def get(cls):
        """获取全局单例（懒初始化，失败自动禁用）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._ctx = None
        self._prog_comp = None
        self._prog_post = None
        self._vao = None
        self._vbo = None
        self._fbo = None
        self._out_tex = None
        self._light_tex = None
        self._scene_tex = None
        self._out_size = (0, 0)
        self._try_init()

    # ---------- 初始化 ----------
    def _try_init(self):
        try:
            import moderngl
        except Exception:
            return
        try:
            ctx = moderngl.create_standalone_context()
            prog_c = ctx.program(vertex_shader=self._COMPOSITE_VERT,
                                 fragment_shader=self._COMPOSITE_FRAG)
            prog_p = ctx.program(vertex_shader=self._POST_VERT,
                                 fragment_shader=self._POST_FRAG)
            vertices = (
                -1.0, -1.0, 0.0, 0.0,
                1.0, -1.0, 1.0, 0.0,
                -1.0, 1.0, 0.0, 1.0,
                1.0, 1.0, 1.0, 1.0,
            )
            import array as _arr
            vbo = ctx.buffer(_arr.array('f', vertices).tobytes())
            vao = ctx.vertex_array(prog_c, [(vbo, '2f2f', 'in_pos', 'in_uv')])
            self._ctx, self._prog_comp, self._prog_post = ctx, prog_c, prog_p
            self._vbo, self._vao = vbo, vao
            self.available = True
        except Exception:
            self.available = False

    # ---------- 工具 ----------
    def _ensure_target(self, w, h):
        if self._out_size == (w, h) and self._fbo is not None:
            return
        self._out_size = (w, h)
        if self._fbo is not None:
            try:
                self._fbo.release()
                self._out_tex.release()
            except Exception:
                pass
        self._out_tex = self._ctx.texture((w, h), 4)
        self._fbo = self._ctx.framebuffer(color_attachments=[self._out_tex])

    def _upload(self, surf, slot):
        """上传 pygame surface 为纹理（RGBA），slot: 'light' | 'scene'"""
        w, h = surf.get_size()
        raw = pygame.image.tostring(surf, "RGBA", True)
        tex = self._light_tex if slot == "light" else self._scene_tex
        if tex is None or tex.size != (w, h):
            if tex is not None:
                try:
                    tex.release()
                except Exception:
                    pass
            tex = self._ctx.texture((w, h), 4)
            if slot == "light":
                self._light_tex = tex
            else:
                self._scene_tex = tex
        tex.write(raw)
        # GL_LINEAR 放大插值（替代 CPU smoothscale）
        tex.filter = (0x2601, 0x2601)
        return tex

    def _run_frag(self, prog, out_w, out_h):
        self._ensure_target(out_w, out_h)
        self._fbo.use()
        self._vao.render(prog)
        data = self._fbo.read(components=4)
        # 直接 frombuffer（不 convert_alpha：避免依赖已 set_mode 的显示格式，
        # 且减少一次像素拷贝；RGBA 表面 blit 语义与 SRCALPHA 一致）
        return pygame.image.frombuffer(data, (out_w, out_h), "RGBA")

    # ---------- 公开 API ----------

    def composite(self, light_surf, ambient, vignette, out_w, out_h):
        """光源合成：暗层挖洞 + 暗角 + 放大（替代 CPU fill+SUB+smoothscale）。失败返回 None。"""
        if not self.available:
            return None
        try:
            tex = self._upload(light_surf, "light")
            self._prog_comp["u_light"].value = 0
            self._prog_comp["u_ambient"].value = float(ambient)
            self._prog_comp["u_vignette"].value = 1.0 if vignette else 0.0
            tex.use(0)
            return self._run_frag(self._prog_comp, out_w, out_h)
        except Exception:
            return None

    def postprocess(self, surf, hurt=0.0, flash=0.0, sharpen=True, sat=1.08, bright=0.0):
        """最终帧后处理：锐化 + 饱和度 + 低血量红屏 + 爆闪。失败返回 None（调用方原样 blit）。"""
        if not self.available:
            return None
        try:
            w, h = surf.get_size()
            tex = self._upload(surf, "scene")
            self._prog_post["u_tex"].value = 0
            self._prog_post["u_texel"].value = (1.0 / w, 1.0 / h)
            self._prog_post["u_sharpen"].value = 1.0 if sharpen else 0.0
            self._prog_post["u_sat"].value = float(sat)
            self._prog_post["u_hurt"].value = float(max(0.0, min(1.0, hurt)))
            self._prog_post["u_flash"].value = float(max(0.0, min(1.0, flash)))
            self._prog_post["u_bright"].value = float(bright)
            tex.use(0)
            return self._run_frag(self._prog_post, w, h)
        except Exception:
            return None
