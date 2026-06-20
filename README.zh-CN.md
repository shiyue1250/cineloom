<h1 align="center">Cineloom</h1>

<p align="center"><b>面向 Blender 视频序列编辑器（VSE）的「模型无关」AI 影片装配工作台。</b><br/>
Linux 优先 · 可远端生成 · GPL-3.0。</p>

<p align="center">
  <img src="https://img.shields.io/badge/Blender-5.2%2B-orange" alt="Blender 5.2+">
  <img src="https://img.shields.io/badge/Linux-first-5ad571" alt="Linux-first">
  <img src="https://img.shields.io/badge/License-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later">
  <img src="https://img.shields.io/badge/forked%20from-Pallaidium-violet" alt="forked from Pallaidium">
</p>

<p align="center"><a href="README.md">English</a> · <b>中文</b></p>

<hr>

> **Cineloom 是 [Pallaidium](https://github.com/tin2tin/Pallaidium)（作者 *tintwotin*）的 fork**（GPL-3.0-or-later）。
> 它保留了 Pallaidium 的「AI ↔ VSE」桥接，并新增三项增量：**让 Linux 成为一等公民**、
> **把「编辑」与「生成」解耦**（远端 GPU 后端）、以及**聚焦质量**的 LTX-2.3 路线。详见 [NOTICE.md](NOTICE.md)。

一部影片往往要到做完，你才真正明白它本该怎么拍。Cineloom 把这种「事后才懂」变成工作流：
用 AI 生成镜头、配音、配字幕，然后在**专业时间线**上剪成片 —— 全部在 Blender 的视频序列编辑器里完成。

它的价值**不在某一个模型**。模型只会越来越强；Cineloom 是围绕模型的**「模型无关」装配层** ——
生成、配音、字幕、剪辑、节奏、同步、导出，组织成一条顺手的影片流水线。模型是**可插拔的零件**：
今天 LTX-2.3，明天换新模型，**换个插件即可，框架不动。**

## 为什么是 Cineloom（相对 Pallaidium 的三项增量）

| 增量 | 含义 |
|---|---|
| **① Linux 一等公民** | 一套稳定、经过验证的依赖安装脚本（`scripts/install_linux.sh`），替代原版易崩的一键按钮；外加代理感知的权重下载器（`scripts/download_models.py`）。 |
| **② 编辑 ⇄ 生成解耦** | **远端后端**：Blender 在桌面剪辑（无需大显卡），生成请求 POST 给 GPU 服务器。选一个「Cineloom Remote · …」模型，请求就发往**你自建的** [Cineloom 服务器](#cineloom-生成服务器-server)，或**任意你自己运行的 OpenAI 兼容 `/v1` 端点**。 |
| **③ 聚焦 + 画质** | 基于经过验证的 `diffusers` + `sdnq` int8 栈，容器化的 LTX-2.3 生成服务。 |

## 架构

```
┌─ Linux 桌面 / 工作站（有显示） ─────┐        ┌─ GPU 服务器（无界面） ───────────┐
│  Blender VSE + Cineloom 插件        │        │  Cineloom 服务器（server/）       │
│   • 时间线剪辑 · 字幕 · 配音同步     │  /v1   │   diffusers LTX-2.3 + sdnq int8  │
│   • 「Cineloom Remote · …」模型 ────┼──────▶ │   POST /v1/videos → mp4          │
│   • 无需大显卡                      │ ◀──────┤   （或任意 OpenAI /v1 后端）      │
└─────────────────────────────────────┘ 文件   └──────────────────────────────────┘
```

编辑端保持轻量，重活在服务器。一个偏好项（远端后端 URL）即可在本地 ↔ 远端之间切换生成。

> **关于后端：** 这是一个**模型无关**的装配框架。它**不内置、也不绑定任何托管模型服务**。
> 你需要**自行部署** `server/` 里的 Cineloom 服务器（在你自己的 GPU 机器上），或**接入你自己的**
> 任意 OpenAI 兼容 `/v1` 服务。仓库里**不打包任何模型权重**。

## 安装（Linux）

### 1. Blender ≥ 5.2

下载官方 Linux 版（`blender-x.y-linux-x64.tar.xz`）解压即用，无需系统安装。

### 2. Cineloom 插件

克隆本仓库并将插件打包（仓库根目录**就是**扩展本体；`server/`、`scripts/`、`docs/`
已由 `blender_manifest.toml` 排除）：

```bash
git clone https://github.com/shiyue1250/cineloom.git
# 在 Blender 中：Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk ▸ 选择仓库目录
# （或用 blender --command extension build 构建 .zip）
```

### 3. 依赖（经过验证的配方）

不要用易崩的一键按钮，改用安装脚本，安装进 Blender 自带的 Python：

```bash
# 仅安装 LTX-2.3 核心路线（建议先这样）：
scripts/install_linux.sh --blender /path/to/blender --core-only

# 受限网络下，让 pip + HF 走你自己的代理：
scripts/install_linux.sh --blender /path/to/blender --proxy http://127.0.0.1:1081

# 全量（完整 requirements_linux.txt）：
scripts/install_linux.sh --blender /path/to/blender --full
```

经过验证的核心栈：`torch 2.8 + cu12.8 · diffusers 0.38 · sdnq 0.2 · transformers 4.57 · opencv`。

### 4. 权重（代理感知）

```bash
python scripts/download_models.py \
  --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
  --dest ~/ai-models/ltx23-distilled-int8

# 若网络封锁 HuggingFace 的 Xet/CAS 大文件传输，指定你自己的 HTTP 代理：
python scripts/download_models.py --proxy http://127.0.0.1:1081 \
  --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
  --dest ~/ai-models/ltx23-distilled-int8
```

## 远端后端

在 **Edit ▸ Preferences ▸ Add-ons ▸ Cineloom** 中设置：

* **Remote Backend URL** —— **你自己**后端的地址，例如 `http://your-gpu-host:8879`
  （你自建的 Cineloom 服务器），或任意你运行的 OpenAI 兼容 `/v1` 端点。
* **Remote API Key** —— 可选；以 `Bearer` / `X-API-Key` / `?api_key` 形式发送。

然后在 Cineloom 面板中，选择名字以「**Cineloom Remote · …**」开头的模型：

| 模型 | 端点 | 输出 |
|---|---|---|
| Cineloom Remote · LTX-2.3 | `POST /v1/videos` | 视频条带 |
| Cineloom Remote · Image | `POST /v1/images/generations` | 图像条带 |
| Cineloom Remote · TTS | `POST /v1/audio/speech` | 声音条带 |

生成就在服务器上跑，完成的文件被下载到时间线。（本地模型照常可用 —— Cineloom 只是**新增**远端选项。）

## Cineloom 生成服务器（`server/`）

一个自包含的 FastAPI 服务，包裹经过验证的 LTX-2.3 栈。它对**共享主机友好**：
容器/镜像/端口唯一、GPU 钉选、模型只读挂载，不触碰其它任何东西。

```bash
cp server/.env.example server/.env      # 设置 GPU、模型路径、可选 API Key
docker compose -f server/docker-compose.yml up -d --build
curl http://localhost:8879/health
```

* 用 `CINELOOM_GPU` 钉选某块 GPU。
* `CINELOOM_OFFLOAD=sequential`（峰值约 6–8 GB，对邻居友好）或 `model`（约 10–15 GB，更快）。
* `POST /v1/videos` → `{id}`；轮询 `GET /v1/jobs/{id}`；取回 `GET /v1/files/{id}`。

详见 [`server/README.md`](server/README.md)。

## 项目状态

这是早期 fork（`v0.1.0`）。远端后端的视频路线已在 Linux GPU 服务器上**端到端验证**
（LTX-2.3 int8、sequential offload、异步任务 → 下载 mp4）。

| 阶段 | 状态 |
|---|---|
| P0 Fork + 重命名为 Cineloom | ✅ |
| P1 Linux 依赖安装脚本 | ✅ |
| P2 远端后端（插件 + 服务器） | ✅ 已验证（视频） |
| P3 聚焦 + 画质精修 | 进行中 |
| P4 开源发布 | 本仓库 |

远端 ASR/字幕路由与更多远端模型覆盖在计划中（在此之前，本地 Pallaidium 路线照常可用）。

## 许可证与致谢

Cineloom 采用 **GPL-3.0-or-later**，继承自 Pallaidium（copyleft）：任何分发的衍生作品
都必须在同一许可证下保持开源。详见 [LICENSE](LICENSE)、[NOTICE.md](NOTICE.md)，
以及保留的上游说明 [README.upstream.md](README.upstream.md)。

Cineloom **只分发代码**，从不打包模型权重。每个 AI 模型有各自的许可证（多为非商用 / 研究用途），
由用户自行从其来源下载。

上游：**[tin2tin/Pallaidium](https://github.com/tin2tin/Pallaidium)**（作者 *tintwotin*）
—— 感谢这座连接 AI 与 Blender VSE 的桥梁。
