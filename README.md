# 洪水淹没预测系统

演示级原型：给定一块 DEM 和一场降雨，描述可能的淹没水深和淹没范围。它不是经过率定的真实水力学模型，不能用于工程设计、防洪决策或预警。

对应讨论见 [Issue #1](https://github.com/244416619/demo/issues/1)。

当前这个包只提供后续单元可以共用的骨架：

- Python 包布局、安装方式和持续集成
- 领域类型（数据形状和签名，不含演算）
- 一套带洼地的合成 DEM、两场降雨，以及把它们拼在一起的情景

淹没计算、HTTP API 和地图界面不在这里。

## 技术栈

| 阶段 | 选择 |
| --- | --- |
| 现在 | Python 3.11+，领域对象用标准库 dataclass，测试用 pytest |
| 后续 API | FastAPI，读写本包的 `to_dict()` / `from_dict()` |
| 后续界面 | Vite + Leaflet，把水深和干湿网格画在地图上 |

领域层不依赖 Web 框架。演算单元以后可以单独依赖数值库，API 再调用它。

## 安装与测试

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

`dev` 额外依赖目前只有 pytest。安装完成后可以确认样例能加载：

```bash
python -c "from floodcast import load_scenario; s = load_scenario(); print(s.scenario_id, s.dem.spec.nrows, s.rainfall.total_depth_mm)"
```

默认情景是 `bowl_design_storm`：8×8 的洼地，设计暴雨总雨量 50 mm。

## 目录

```
src/floodcast/
  domain/                 领域类型
    grid.py               规则格网
    dem.py                DEM
    rainfall.py           降雨过程
    inundation.py         水深栅格与干湿网格
    scenario.py           情景与结果元数据
  fixtures/data/          合成样例和说明
tests/                    pytest
.github/workflows/ci.yml  安装项目并运行测试
```

计划中的后续目录，本 PR 不创建：

```
src/floodcast/engine/     由 Scenario 生成 InundationRaster
src/floodcast/api/        FastAPI
frontend/                 Vite + Leaflet
```

## 单位

全库统一，避免后面的 API 和界面各写一套：

| 量 | 单位 |
| --- | --- |
| 高程、水深、格网坐标和格子边长 | 米 |
| 淹没面积 | 平方米 |
| 降雨深 | 毫米 |
| 时间 | 小时，情景起点为 0 |

样例格网的 `crs` 是 `LOCAL`：原点在第 0 行上边的左端，列号向东、行号向南，坐标是局部米，不是经纬度。Leaflet 那一层需要自己选一个展示用的原点或图像叠加，不要把这些数字当成 WGS84。

## 领域模型

类型只约束形状，并根据已有水深做阈值分类和汇总。它们不产流，也不做汇流。

| 类型 | 作用 |
| --- | --- |
| `GridSpec` | 行列数、格子边长、左上角原点和 CRS |
| `DigitalElevationModel` | 与格网对齐的地面高程，可带 `nodata` |
| `RainfallInterval` / `RainfallSeries` | 分时段雨量。本单元只接受空间均匀的过程 |
| `ScenarioDocument` | 情景文件：只引用 DEM id 和降雨 id |
| `Scenario` | 把 DEM 对象和降雨对象接在一起的输入 |
| `InundationRaster` | 已有的水深栅格，单位米，0 为干 |
| `WetDryMask` | 水深不小于阈值（默认 0.01 m）的布尔网格 |
| `ScenarioResult` | 最大水深、淹没面积、湿格子数、雨量等元数据 |

水深栅格上的 `wet_mask()`、`max_depth_m` 和 `inundated_area_m2` 是在读一块已经填好的水深。`ScenarioResult.from_inundation(scenario, raster)` 把这些汇总抄到结果记录上，并检查栅格和 DEM 是同一块格网。调用方必须自己提供水深。

JSON 形状由各类型的 `to_dict()` / `from_dict()` 固定，供以后的 FastAPI 直接使用。`Scenario.to_dict()` 写出的是 id 引用，不是整幅 DEM。

```python
from floodcast import ScenarioResult, load_scenario

scenario = load_scenario("bowl_design_storm")
dem = scenario.dem
print(dem.elevation_at(3, 3))          # 洼地最低点，4 m
print(scenario.rainfall.total_depth_mm)  # 50 mm

# 演算单元以后会生成 depth。这里只演示类型，数字是手写的。
# result = ScenarioResult.from_inundation(scenario, depth_raster)
```

## 样例数据

说明在 `src/floodcast/fixtures/data/README.md`，随包安装，也可 `floodcast.read_fixture_notes()` 读取。

- `depression_bowl`：中间低、四周高的 8×8 洼地，东南角有一条更低的边缘，方便以后做溢流
- `design_storm`：3 小时、50 mm，雨峰在 1.0–1.5 h
- `light_rain`：2 小时、2 mm
- `bowl_design_storm` 和 `bowl_light_rain`：上面这块 DEM 配两场雨

没有附带淹没结果文件。

## 后续单元怎么接

1. **演算。** 读取 `Scenario`，在 DEM 格网上写出 `InundationRaster`，再用 `ScenarioResult.from_inundation` 生成最大水深和淹没面积。算法替换不应改掉这些类型的字段名和单位。
2. **API。** FastAPI 列出 `load_catalog()` 里的情景，用 `Scenario.to_dict()` 和 `ScenarioResult.to_dict()` 作为响应。请求和响应不要另起一套高程或雨量单位。
3. **地图。** Vite + Leaflet 展示 `InundationRaster.depth_m` 和 `wet_mask()`。格网位置用 `GridSpec.cell_center`。样例 CRS 是局部米制网格，界面需要单独处理贴图方式。

## 本 PR 不做的事

- 不实现产流、汇流、水位演算或任何淹没预报算法
- 不提供 FastAPI 路由、服务进程或 OpenAPI
- 不提供前端页面、Leaflet 地图或 Vite 工程
