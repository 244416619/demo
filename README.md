# 洪水淹没预测系统

演示级原型：给定一块 DEM 和一场降雨，估计可能的淹没水深和淹没范围。它不是经过率定的真实水力学模型，不能用于工程设计、防洪决策或预警。

对应讨论见 [Issue #1](https://github.com/244416619/demo/issues/1)。

当前这个包提供：

- Python 包布局、安装方式和持续集成
- 领域类型（DEM、降雨过程、水深栅格、干湿网格、情景结果）
- 一套带洼地的合成 DEM、两场降雨，以及把它们拼在一起的情景
- 洼地蓄水演算：`floodcast.predict` / `predict_scenario`

HTTP API 和地图界面不在这里。

## 技术栈

| 阶段 | 选择 |
| --- | --- |
| 现在 | Python 3.11+，标准库实现演算（`heapq`），测试用 pytest |
| 后续 API | FastAPI，读写本包的 `to_dict()` / `from_dict()` |
| 后续界面 | Vite + Leaflet，把水深和干湿网格画在地图上 |

领域层和演算都不依赖 Web 框架，也不依赖 NumPy。

## 安装与测试

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

`dev` 额外依赖目前只有 pytest。安装完成后可以直接跑默认情景：

```bash
python -c "from floodcast import predict_scenario; p = predict_scenario(); print(p.result.max_depth_m, p.result.inundated_area_m2, p.spilled)"
```

默认情景是 `bowl_design_storm`：8×8 的洼地，设计暴雨总雨量 50 mm。

## 从 Python 跑一场预测

```python
from floodcast import InundationParameters, predict_scenario

design = predict_scenario("bowl_design_storm")
light = predict_scenario("bowl_light_rain")

print(design.result.max_depth_m)          # 约 1.6 m
print(design.result.inundated_area_m2)    # 1875 m²，三个 25 m 格子
print(design.inundation.depth_at(3, 3))   # 洼地最低点
print(design.water_surface_m)             # 约 5.6 m
print(design.spill_elevation_m)           # 溢流高程 16 m
print(design.spilled)                     # 50 mm 蓄不满，不会溢流
print(design.wet_mask().wet_cell_count)

# 初损从总雨量里扣，单位是毫米。扣掉 48 mm 后，这场暴雨和 2 mm 小雨的净雨相同。
matched = predict_scenario(
    "bowl_design_storm",
    InundationParameters(infiltration_mm=48),
)
print(matched.inundation.depth_m == light.inundation.depth_m)
```

`predict(scenario)` 接受已经拼好的 `Scenario`。`predict_scenario` 按目录里的 id 加载样例，缺省就是 `bowl_design_storm`。

返回的 `InundationPrediction` 里：

| 字段 | 含义 |
| --- | --- |
| `inundation` | 水深栅格，米。0 为干 |
| `result` | `ScenarioResult`：最大水深、淹没面积、湿格子数、雨量和历时 |
| `retained_volume_m3` | 留在洼地里的水 |
| `overflow_volume_m3` | 离开网格的水。包括落在已经朝区外倾斜的格子上、没有进洼地的雨 |
| `spilled` | 某个洼地已经蓄到溢流高程，多余的水向下游走了 |
| `spill_elevation_m` | 盛着最深水的那片洼地的溢流高程。没有积水时是 `None` |
| `water_surface_m` | 这片洼地的水面高程 |
| `overflow_path` | 溢流时从坑底到出口的格子坐标。没有溢流就是空的 |

水深栅格和 DEM 使用同一块 `GridSpec`。`result` 由 `ScenarioResult.from_inundation` 生成。

## 演算在做什么

这是洼地蓄水，不是二维浅水方程。

1. 用 priority-flood 从网格外缘往里算每个格子的溢流高程：水要离开研究区，沿 4 邻域必须漫过的最低高程。同时记下一个下游方向。同样的溢流高程上，优先留在网格内，所以高边坡上的雨会先汇进洼地。
2. 净雨深 = `max(0, 总雨量 − infiltration_mm)`，再换成体积。过程线只提供总雨量；峰现时间不参与演算。`ScenarioResult` 里仍然记录原始总雨量和历时。
3. 净雨顺着下游方向进入沿途第一片洼地。洼地用一个水平水面往上蓄，蓄满后多余的水交给下游的下一片洼地，最后从网格边缘离开。被缺测值围住、到不了边缘的区域视为没有出口的封闭洼地。
4. 真正溢流时，从坑底走到出口的那条路径如果本来是干的，会标上等于湿阈值的示意水深（默认 1 cm），这样干湿网格能看见溢流通道。这笔水已经离开研究区，不计入 `retained_volume_m3`。

在合成洼地上，50 mm 设计暴雨的水面大约到 5.6 m。湿的是三个最低的格子：行 3 列 3（水深约 1.6 m）、行 3 列 4 和行 4 列 3（各约 0.6 m）。高程不低于 8 m 的格子，包括北侧 22 m 的边缘，保持干燥。东南角出口（行 7 列 7，14 m）也是干的，因为洼地还没蓄到 16 m 的溢流高程。

同一块 DEM 上的 2 mm 小雨只在最低点积起约 0.11 m 的水。

洼地库容大约 85000 m³。落在出口一侧、已经朝网格外倾斜的格子上的雨不会倒灌进去。把净雨加大到洼地蓄满以后，多余的水沿 `(3,3) → (3,4) → (3,5) → (3,6) → (4,6) → (5,6) → (6,6) → (6,7) → (7,7)` 离开，最低点水深停在 12 m，再加大雨量也不会把水面抬过溢流高程。

## 目录

```
src/floodcast/
  domain/                 领域类型
    grid.py               规则格网
    dem.py                DEM
    rainfall.py           降雨过程
    inundation.py         水深栅格与干湿网格
    scenario.py           情景与结果元数据
  engine/                 src/floodcast/engine，由 Scenario 生成 InundationRaster
  fixtures/data/          合成样例和说明
tests/                    pytest
.github/workflows/ci.yml  安装项目并运行测试
```

计划中的后续目录，本 PR 不创建：

```
src/floodcast/api/        FastAPI
frontend/                 Vite + Leaflet
```

## 单位

全库统一，避免后面的 API 和界面各写一套：

| 量 | 单位 |
| --- | --- |
| 高程、水深、格网坐标和格子边长 | 米 |
| 淹没面积 | 平方米 |
| 降雨深、初损 | 毫米 |
| 时间 | 小时，情景起点为 0 |

样例格网的 `crs` 是 `LOCAL`：原点在第 0 行上边的左端，列号向东、行号向南，坐标是局部米，不是经纬度。Leaflet 那一层需要自己选一个展示用的原点或图像叠加，不要把这些数字当成 WGS84。

## 领域模型

类型只约束形状，并根据已有水深做阈值分类和汇总。产流和蓄水在 `floodcast.engine`。

| 类型 | 作用 |
| --- | --- |
| `GridSpec` | 行列数、格子边长、左上角原点和 CRS |
| `DigitalElevationModel` | 与格网对齐的地面高程，可带 `nodata` |
| `RainfallInterval` / `RainfallSeries` | 分时段雨量。本单元只接受空间均匀的过程 |
| `ScenarioDocument` | 情景文件：只引用 DEM id 和降雨 id |
| `Scenario` | 把 DEM 对象和降雨对象接在一起的输入 |
| `InundationRaster` | 水深栅格，单位米，0 为干 |
| `WetDryMask` | 水深不小于阈值（默认 0.01 m）的布尔网格 |
| `ScenarioResult` | 最大水深、淹没面积、湿格子数、雨量等元数据 |
| `InundationParameters` | 初损（毫米）和湿阈值（米） |
| `InundationPrediction` | 一次演算的水深、结果元数据和蓄量、溢流 |

水深栅格上的 `wet_mask()`、`max_depth_m` 和 `inundated_area_m2` 是在读一块已经填好的水深。`ScenarioResult.from_inundation(scenario, raster)` 把这些汇总抄到结果记录上，并检查栅格和 DEM 是同一块格网。

JSON 形状由各类型的 `to_dict()` / `from_dict()` 固定，供以后的 FastAPI 直接使用。`Scenario.to_dict()` 写出的是 id 引用，不是整幅 DEM。

## 样例数据

说明在 `src/floodcast/fixtures/data/README.md`，随包安装，也可 `floodcast.read_fixture_notes()` 读取。

- `depression_bowl`：中间低、四周高的 8×8 洼地，东南角有一条更低的边缘，作为溢流通道
- `design_storm`：3 小时、50 mm，雨峰在 1.0–1.5 h
- `light_rain`：2 小时、2 mm
- `bowl_design_storm` 和 `bowl_light_rain`：上面这块 DEM 配两场雨

样例目录不附带水深文件。水深由演算现算。

## 后续单元怎么接

1. **API。** FastAPI 列出 `load_catalog()` 里的情景，对选中的情景调用 `predict_scenario`，用 `Scenario.to_dict()`、`InundationRaster.to_dict()` 和 `ScenarioResult.to_dict()` 作为响应。请求和响应不要另起一套高程或雨量单位。
2. **地图。** Vite + Leaflet 展示 `InundationRaster.depth_m` 和 `wet_mask()`。溢流通道看 `overflow_path`。格网位置用 `GridSpec.cell_center`。样例 CRS 是局部米制网格，界面需要单独处理贴图方式。

## 本 PR 不做的事

- 不做时变的洪水过程线，也不解二维浅水方程
- 不提供 FastAPI 路由、服务进程或 OpenAPI
- 不提供前端页面、Leaflet 地图或 Vite 工程
