# 多光向面部烘焙

从仓库根目录运行总入口。Cycles CPU 使用直接漫反射与黑环境；BVH 对照按同一 UV 表面的法线朝向及射线自遮挡计算。两条路径分别拟合一次亮到暗的转换，保存归一化角阈值。 [运行命令](../../README.md#blender-烘焙)

默认鼻口保护区是局部坐标 |X| < 0.065、Y < −0.085、0.035 < Z < 0.19 米与有效 UV 的交集。轻、中、强档连通域面积阈值为 33 / 133 / 333 像素，局部中值窗口为 3 / 3 / 5。触及覆盖边界或保护区的小岛保留。 [保护区图](PublicHead/cycles_Protect_NoseMouth.png) · [六光向对照](PublicHead/renders_cycles_ContactSheet.png)

替换样本时使用静态头模，UV 三角形内部无重叠、UV 在 0–1，按 −Y 前向、+Z 向上布置。在独立工作副本提取网格，根据目标头模调整鼻口遮罩、左右通道映射和预览机位。遮罩与烘焙图等分辨率，白色为保护。

```powershell
blender -b --factory-startup --disable-autoexec --python-exit-code 7 --python tools/face_sdf/extract_head.py -- path/to/head.blend HeadObject
python -B tools/face_sdf/process_thresholds.py --cycles --protect path/to/nose_mouth_mask.png
```

遮罩命令读取先前烘焙和拟合生成的数组。替换头模后先完成烘焙和拟合，再用遮罩重算清理与预览。自定义头模需更新来源哈希才能通过固定样本的源保护断言。

颈根限定版在保留原始耳影与鼻口角阈值的同时，只在样本颈根应用强档。切线为 Z < 0.04535 米，排除鼻口保护区。对照图三列依次为原始、颈根限定、强档。 [候选纹理](neck_review_v001/source/T_PublicHead_cycles_neck_project_RGBA16.png) · [颈根遮罩](neck_review_v001/source/CC0_neck_mask.png) · [主机位](../../examples/neck/三栏对照_main.png) · [镜像机位](../../examples/neck/三栏对照_mirror.png)
