"""P0-2 光照矩阵自动截图（UE 编辑器 Python）。

在编辑器里：Output Log 选 Python，执行
    py "<repo>/ue/python/light_matrix_capture.py"
等截图全部写完并恢复灯光，再关闭编辑器。

做什么：
- 找关卡里带 Tag `LM_Sun` 的方向光（没有就取第一盏 DirectionalLight）；
- 按 ROWS（时段，改光强和颜色）× COLS（光向 yaw/pitch）逐格设置；
- 每格等 WARMUP_TICKS 帧（让 Lumen / TSR 收敛），再用视口截一张高分辨率图，命名为
  LM_<行>__<列>.png，存在 Saved/Screenshots/<平台>/ 下；
- 跑完把灯恢复原状。不保存关卡。
之后用 tools/contact_sheet.py 拼成网格。

【推测】unreal.AutomationLibrary.take_high_res_screenshot 的签名以你 UE 版本的 Python API 为准；
如果报参数错误，在 Output Log 里执行 help(unreal.AutomationLibrary.take_high_res_screenshot) 对照修改。
"""
import unreal

RES_X, RES_Y = 1920, 1080
WARMUP_TICKS = 90          # 约 1.5 秒 @60fps；Lumen 收敛慢就加大
AFTER_SHOT_TICKS = 30      # 截图是异步的，留出写盘时间

# 时段：强度（lux）和颜色（线性 RGB）。按你的场景改。
ROWS = {
    "day":   (75000.0, (1.0, 0.98, 0.95)),
    "dusk":  (8000.0,  (1.0, 0.62, 0.38)),
    "night": (2.0,     (0.55, 0.65, 1.0)),
}
# 光向：(yaw, pitch)，pitch 为负表示从上往下照
COLS = {
    "front_y000_p-30": (0.0, -30.0),
    "side_y090_p-30":  (90.0, -30.0),
    "back_y180_p-30":  (180.0, -30.0),
    "top_y000_p-75":   (0.0, -75.0),
}


def find_sun():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    lights = [a for a in actors if isinstance(a, unreal.DirectionalLight)]
    tagged = [a for a in lights if "LM_Sun" in [str(t) for t in a.tags]]
    if tagged:
        return tagged[0]
    if lights:
        return lights[0]
    raise RuntimeError("关卡里没有 DirectionalLight")


class Runner:
    def __init__(self):
        self.sun = find_sun()
        self.comp = self.sun.get_component_by_class(unreal.DirectionalLightComponent)
        self.orig = (self.sun.get_actor_rotation(), self.comp.intensity, self.comp.light_color)
        self.jobs = [(r, c) for r in ROWS for c in COLS]
        self.idx, self.wait, self.state = 0, 0, "set"
        self.in_tick = False
        self.finished = False
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        unreal.log(f"[LM] {len(self.jobs)} 格，开始")

    def tick(self, _dt):
        # High-res capture pumps Slate and can re-enter this callback synchronously.
        if self.in_tick or self.finished:
            return
        self.in_tick = True
        try:
            if self.wait > 0:
                self.wait -= 1
                return
            if self.idx >= len(self.jobs):
                self.finish()
                return
            row, col = self.jobs[self.idx]
            if self.state == "set":
                inten, color = ROWS[row]
                yaw, pitch = COLS[col]
                self.sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), False)
                self.comp.set_intensity(inten)
                self.comp.set_light_color(unreal.LinearColor(color[0], color[1], color[2], 1.0))
                self.state, self.wait = "shoot", WARMUP_TICKS
            elif self.state == "shoot":
                name = f"LM_{row}__{col}"
                unreal.AutomationLibrary.take_high_res_screenshot(RES_X, RES_Y, name)
                unreal.log(f"[LM] {self.idx + 1}/{len(self.jobs)} {name}")
                self.idx += 1
                self.state, self.wait = "set", AFTER_SHOT_TICKS
        except Exception as e:  # 出错也要恢复灯光、注销回调
            unreal.log_error(f"[LM] 失败：{e}")
            self.finish()
        finally:
            self.in_tick = False

    def finish(self):
        if self.finished:
            return
        self.finished = True
        unreal.unregister_slate_post_tick_callback(self.handle)
        rot, inten, color = self.orig
        self.sun.set_actor_rotation(rot, False)
        self.comp.set_intensity(inten)
        # light_color is an 8-bit Color property; SetLightColor requires LinearColor.
        self.comp.set_editor_property("light_color", color)
        unreal.log(f"[LM] 结束，已完成 {self.idx}/{len(self.jobs)}，灯光已恢复。截图在 Saved/Screenshots/")


_runner = Runner()
