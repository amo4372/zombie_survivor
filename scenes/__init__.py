# -*- coding: utf-8 -*-
"""场景（页面）系统 —— v2.8.8 模块化重构

背景
----
此前所有页面都靠 `GameState` 枚举 + `Renderer` 里一个巨大的 if/elif 分派，
新增一个页面要改 4~5 处（枚举、渲染分派、输入分派、按钮初始化、状态切换），
页面之间还互相耦合，改一处容易碰坏另一处。

现在提供三层：

    Scene          页面基类：enter / exit / update / draw / handle_event
    SceneManager   场景栈：push / pop / replace，支持返回上一层
    SceneSpec      声明式页面描述，支持**批量创建**页面

批量创建
--------
`build_scenes(specs)` 一次性构造一批页面，自动完成：
按钮对象创建、布局、注册到管理器、绑定返回逻辑。
这样新增一个"信息展示页"（武器/地图/角色）只需写一份数据，不用改渲染分派。
"""

from collections import OrderedDict

try:
    from ui_pkg.base import Button
except Exception:                              # pragma: no cover
    Button = None


class Scene:
    """页面基类

    子类按需重写 on_enter / on_exit / update / draw / handle_event。
    默认实现都是安全的空操作，未重写的生命周期不会报错。
    """

    #: 页面唯一标识（对应 GameState 名或自定义 key）
    key = "scene"
    #: 显示标题
    title = ""
    #: 返回到哪个页面（None = 不可返回）
    back_to = None

    def __init__(self, game, key=None, title="", back_to=None):
        self.game = game
        if key:
            self.key = key
        if title:
            self.title = title
        if back_to is not None:
            self.back_to = back_to
        self.buttons = OrderedDict()
        self.scroll = 0
        self.active = False

    # ---------------- 生命周期 ----------------
    def on_enter(self, **kwargs):
        """进入页面时调用（可接收参数）"""
        self.scroll = 0
        self.active = True

    def on_exit(self):
        """离开页面时调用"""
        self.active = False

    # ---------------- 每帧 ----------------
    def update(self, dt):
        pass

    def draw(self, renderer):
        """由 Renderer 的 draw 实现负责；基类不画任何东西"""
        pass

    def handle_event(self, event):
        """返回 True 表示事件已消费"""
        return False

    # ---------------- 按钮辅助 ----------------
    def add_button(self, name, x, y, w, h, text, color=None, **kw):
        """创建并登记一个按钮"""
        if Button is None:
            return None
        try:
            _b = Button(x, y, w, h, text, **({"color": color} if color else {}), **kw)
        except Exception:
            try:
                _b = Button(x, y, w, h, text)
            except Exception:
                return None
        self.buttons[name] = _b
        return _b

    def draw_buttons(self, screen, font, scale=1.0):
        for _b in self.buttons.values():
            try:
                if getattr(_b, 'visible', True):
                    _b.draw(screen, font, scale)
            except Exception:
                pass

    def clicked(self, name, mouse_pos, mouse_pressed, touch_events=None, scale=1.0):
        """指定按钮本帧是否被点击"""
        _b = self.buttons.get(name)
        if _b is None:
            return False
        try:
            return bool(_b.update(mouse_pos, mouse_pressed, touch_events or [], scale))
        except Exception:
            return False


class SceneManager:
    """场景栈管理器

    支持 push（进入新页面，可返回）/ replace（替换，不可返回）/ pop（返回）。
    """

    def __init__(self, game):
        self.game = game
        self.scenes = OrderedDict()
        self.stack = []

    def register(self, scene):
        """登记一个页面"""
        if scene is None:
            return None
        self.scenes[scene.key] = scene
        return scene

    def register_many(self, scenes):
        """批量登记"""
        _out = []
        for _s in scenes or []:
            _out.append(self.register(_s))
        return _out

    def get(self, key):
        return self.scenes.get(key)

    @property
    def current(self):
        if not self.stack:
            return None
        return self.scenes.get(self.stack[-1])

    def push(self, key, **kwargs):
        """进入页面（保留返回路径）"""
        _s = self.scenes.get(key)
        if _s is None:
            return None
        try:
            _s.on_enter(**kwargs)
        except Exception:
            pass
        if key not in self.stack:
            self.stack.append(key)
        return _s

    def replace(self, key, **kwargs):
        """替换当前页面（不留返回路径）"""
        _s = self.scenes.get(key)
        if _s is None:
            return None
        if self.stack:
            try:
                _old = self.scenes.get(self.stack[-1])
                if _old is not None:
                    _old.on_exit()
            except Exception:
                pass
            self.stack[-1] = key
        else:
            self.stack.append(key)
        try:
            _s.on_enter(**kwargs)
        except Exception:
            pass
        return _s

    def pop(self):
        """返回上一层"""
        if not self.stack:
            return None
        _key = self.stack.pop()
        try:
            _s = self.scenes.get(_key)
            if _s is not None:
                _s.on_exit()
        except Exception:
            pass
        return self.current

    def clear(self):
        for _k in list(self.stack):
            try:
                _s = self.scenes.get(_k)
                if _s is not None:
                    _s.on_exit()
            except Exception:
                pass
        self.stack.clear()


class SceneSpec:
    """声明式页面描述 —— 用于批量创建

    字段：
        key        页面标识
        title      标题
        klass      Scene 子类（默认 Scene）
        back_to    返回目标页面的 key
        buttons    [(name, x, y, w, h, text), ...]
    """

    __slots__ = ("key", "title", "klass", "back_to", "buttons", "extra")

    def __init__(self, key, title="", klass=None, back_to=None,
                 buttons=None, **extra):
        self.key = key
        self.title = title
        self.klass = klass or Scene
        self.back_to = back_to
        self.buttons = buttons or []
        self.extra = extra

    def build(self, game):
        """按描述构造页面实例"""
        try:
            _s = self.klass(game, key=self.key, title=self.title,
                            back_to=self.back_to)
        except Exception:
            _s = Scene(game, key=self.key, title=self.title,
                       back_to=self.back_to)
        for _b in self.buttons:
            try:
                if len(_b) >= 6:
                    _name, _x, _y, _w, _h, _text = _b[:6]
                    _s.add_button(_name, _x, _y, _w, _h, _text)
            except Exception:
                continue
        return _s


def build_scenes(game, specs, manager=None):
    """批量创建并登记页面

    返回 SceneManager（传入 manager 时复用之）。
    """
    _mgr = manager or SceneManager(game)
    _mgr.register_many([_sp.build(game) for _sp in specs or []])
    return _mgr
