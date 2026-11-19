# 面部时域与描边实验

先完成 UE 宿主准备，保留生成的关卡、材质、网格、纹理和已编译的 Win64 FaceKeyLight。实验在 Windows 启动独立 UE 5.8.3 DX12 / SM6 游戏进程。外层使用 Python 3.13、NumPy 和 Pillow。 [宿主准备](../../../README.md#ue-材质与截图)

默认从 `ue/host` 读取 `FaceProject.uproject`，`TA_FACE_HOST` 可指定同结构的其他宿主。用 `UE_EDITOR_CMD` 指定可执行文件，或将 `UnrealEditor-Cmd.exe` 所在目录加到 `PATH`。可用 `TA_FACE_SHADER` 为描边实验指定替代的 `FaceProject.ush`。

从包含 FaceTemporal、FaceOutline 的目录执行。每组 32 帧，运行器验证后复用完整组。描边准备命令在其宿主副本中创建验证关卡，输出写入实验子目录。

```powershell
python -B FaceTemporal/run.py
python -B FaceTemporal/analyze.py
python -B FaceOutline/run.py init
python -B FaceOutline/run.py prepare
python -B FaceOutline/run.py capture all
python -B FaceOutline/analyze.py
python -B FaceTemporal/review_cut.py
```

描边分析和视频需要支持中文的字体。默认为系统搜索路径中的 `msyh.ttc`，可用 `FACE_REVIEW_FONT` 指定。视频需要 `PATH` 上的 FFmpeg，或通过 `FFMPEG_EXE` 指定，且需要 libx264。输出为 `FaceTemporal/evidence/face_temporal_review.mp4`。若 TSR 后参考首帧缺少诊断轮廓，运行 `python -B FaceOutline/run.py capture after_ref4 retake` 延长预热重拍，再重跑分析。

反面壳沿顶点法线外扩 0.24 cm 并翻转剔除。两条模板路径使用八邻域，384² 半径为 2 px，1536² 参考为 8 px。UE 5.8.3 延迟渲染中使用 Scene Color Before DOF 和 Scene Color After Tonemapping，对应该实验的 TSR 前和 TSR 后位置。洋红为诊断色，三种描边分别按自己的参考测量。 [实测结果](../../../README.md#已实测)

### TSR 加宽权重

在上面的同一工作目录运行。用新的输出目录可以强制重新渲染所有组。每组写入独立的 PNG、相机、MID 和 CVar 回执。

```powershell
$env:TA_FACE_RUNS = Join-Path $PWD 'tsr_width_runs'
python -B FaceTemporal/run.py --tsr-width
python -B FaceTemporal/measure_tsr.py --runs $env:TA_FACE_RUNS --tools ../../../tools --out tsr_width_metrics baseline original quarter sixteenth bypass
```

眼鼻嘴 ROI 为 x=126…280、y=145…322，沿用原指标。头部外轮廓在同帧 4×4 均值下采样参考上以显示亮度 >0.1 分离头部和黑背景，沿二值边界运行同一梯度、膨胀及跨帧并集。最终在该区域测量原始亮度残差的相邻帧绝对变化。这个定义适用于本实验的纯黑背景。

单视口个人关卡可在 AA 设置生效后调用 `apply_face_width(head.face_material)`。函数读取 `r.AntiAliasingMethod`，TSR 时把现有 MID 的 `EnableAA` 设为 0，其他模式使用调用者请求的权重（默认 1）。切换 AA 后再调用一次。也可在运行该关卡的 UE Python 控制台执行 `tsr_width.py`。历史对照组继续显式设置原权重。 [UE Python 入口](../../python/tsr_width.py) · [材质 Custom 节点](../../shaders/FaceProject.ush)

GPU 配对在同一已准备好的宿主运行，输出目录须为新目录。Windows 启动器等待两次无其他 UE 进程的检查。每段开始、采样中及结束用 tasklist 记录独占情况。三个候选各与自己的零权重基线配三对，每段 20 秒。统计脚本校验原生 GPUTime、截图尺寸、逐段设置和进程检查，然后写入 summary.json。

```powershell
python -B TsrWidthPerf/run.py tsr_width_gpu
python -B TsrWidthPerf/gpu_stats.py tsr_width_gpu
```
