<div align="right"><sub><b>中文</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">EN</a></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="ProofLoop — 数学编程 agent，附机器可检查的 Lean 证明证书">
</picture>

<p align="center"><sub>面向数学家的数学编程 agent——生成代码的同时附上机器可检查的 Lean 证明证书。</sub></p>

<p align="center"><b>当模型说「已证明」时，谁来检查？ProofLoop 把 Lean 当编译器，证明不过就把类型错误喂回去迭代修复，直到类型检查通过——附机器可检查的证明证书，而非可信不可验的散文。</b></p>

<p align="center">
  <a href="./LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="release" src="https://img.shields.io/github/v/release/SuperMarioYL/proofloop?label=release">
  <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/proofloop/ci.yml?branch=main&label=CI">
  <img alt="python" src="https://img.shields.io/badge/python-3.12-blue.svg">
</p>

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：User CLI → Agent 起草 code+Lean proof → Lean oracle 类型检查 → 失败则把错误喂回迭代 → 通过则签发证书">
</picture>

一个 Python 进程，两个外部依赖：一个 OpenAI 兼容 LLM 端点，一个 Lean 工具链子进程。没有服务、没有守护进程。`proofloop prove "<claim>"` 让 agent 在一次调用里同时起草 **Python 实现 + Lean 4 证明**，把证明交给 `lean` 做类型检查——通过就签发证书，不过就把 Lean 的 `stderr` 喂回模型重新起草，循环到通过或达上限。`proof_passed: true` 只在 `lean` 退出码为 0 时才置位。

<h2><img src="https://api.iconify.design/tabler:bulb.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 为什么存在</h2>

数学家和科学计算工程师让通用 coding agent 写数值/符号算法，得到的是看起来合理的代码加一段散文式「证明」——没有任何机制能区分这是正确推导还是幻觉。通用 agent 优化的是广度与自然语言可信度，加一个 Lean co-iteration 循环对它 95% 的非数学用户无价值，而失败模式（似是而非的错误数学）对非专家用户不可见，它收不到信号去优先级化。

ProofLoop 把这段信任题变成机械可判定的事实：agent 起草 Lean 证明，Lean 类型检查器当 ground-truth oracle，证明不通过就迭代修复。`certificate.json` 里的 `proof_passed` 由 `lean` 的退出码决定，不由模型自评——你可以随时自己 `lean out.lean` 复查，2 秒。

> 目录：[架构](#架构) · [为什么存在](#为什么存在) · [快速开始](#快速开始) · [用法](#用法) · [Demo](#demo) · [配置](#配置) · [路线图](#路线图) · [许可证](#许可证)

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 快速开始</h2>

零配置先看一眼完整的 co-iteration 循环（无需 API key、无需 Lean）：

```bash
uvx proofloop prove "sum of first n naturals = n(n+1)/2" --trace --stub
```

要跑真实证明，装一次 Lean 4 并提供任意 OpenAI 兼容 key（DeepSeek / GLM / Qwen / OpenAI 均可）：

```bash
elan default 4.10                # 一次性安装 Lean 4 工具链（已装可跳过）
export PROOFLOOP_API_KEY=sk-...  # 任一 OpenAI 兼容 key
proofloop prove "sum of first n naturals = n(n+1)/2" --trace
```

两种路径都会在当前目录写出 `out.lean`（Lean 通过）、`out.py`、`certificate.json`。

<details>
<summary>样例输出（<code>--trace --stub</code>，2 次迭代收敛）</summary>

```json
{
  "claim": "sum of first n naturals = n(n+1)/2",
  "proof_passed": true,
  "lean_version": "lean 4 (stub)",
  "checked_at": "2026-08-21T20:04:01+00:00",
  "iterations": [
    { "lean_ok": false, "lean_stderr": "error: 'sorry' is not allowed — admitted goals are not proofs" },
    { "lean_ok": true,  "lean_stderr": "" }
  ]
}
```
</details>

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

```bash
# 真实路径：真实 LLM + 真实 Lean，--trace 渲染每一步草拟→报错→修复
proofloop prove "the sum of the first n naturals is n(n+1)/2" --trace

# 离线体验循环形态（内置样例，无 key / 无 Lean）
proofloop prove "the sum of the first n naturals is n(n+1)/2" --trace --stub

# 指定输出目录与迭代上限
proofloop prove "for all n, 2 * sumTo n = n*(n+1)" --out-dir proofs/ --max-iter 12

# 换 DeepSeek：把端点和模型改掉即可
PROOFLOOP_BASE_URL=https://api.deepseek.com/v1 \
PROOFLOOP_MODEL=deepseek-chat \
proofloop prove "sum of first n naturals = n(n+1)/2" --trace
```

完整样例见 [`examples/`](./examples)（`sum_naturals.lean` + `sum_naturals.py`：同一个 claim 的 Lean 证明与 Python 实现）。

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

![demo](./assets/demo-trace.gif)

上图为 `--stub` 路径：草拟（带 `sorry`）→ Lean 拒绝 → 把 `stderr` 喂回 agent 重新起草 → 类型检查通过 → `certificate.json` 里 `proof_passed: true`。`docs/demo.tape` 是该会话的 [vhs](https://github.com/charmbracelet/vhs) 脚本；`.github/workflows/demo.yml` 按需用 vhs 重渲染真实二进制。

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 配置</h2>

全部通过环境变量配置（命令行 `--model` / `--base-url` / `--lean` 可覆盖）：

| 变量 | 类型 | 默认 | 含义 |
| --- | --- | --- | --- |
| `PROOFLOOP_API_KEY` | str | — | OpenAI 兼容 API key（回退到 `OPENAI_API_KEY`） |
| `PROOFLOOP_BASE_URL` | str | `https://api.openai.com/v1` | LLM 端点（用 DeepSeek/GLM/Qwen 改这里） |
| `PROOFLOOP_MODEL` | str | `gpt-4o-mini` | 模型名 |
| `PROOFLOOP_LEAN` | str | `lean` | `lean` 二进制路径（不在 PATH 时显式指定） |
| `PROOFLOOP_MAX_ITER` | int | `8` | co-iteration 上限次数 |
| `PROOFLOOP_OUT_DIR` | str | `.` | `out.lean` / `out.py` / `certificate.json` 输出目录 |

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 — CLI**：`proofloop prove` 把 Lean 当 oracle co-iterate 到类型检查通过，emit `out.lean` / `out.py` / `certificate.json`；`--trace` 渲染每一步。
- [ ] **m2 — 托管 playground**：浏览器内 WASM Lean（lean4web），10 分钟免安装 demo，可分享内嵌 trace + 证书的 URL。
- [ ] **m3 — 样例库 + 收敛基准**：精选 10-20 个经典定理（归纳基础、整除、小分析）的已知好证明 + 收敛率/迭代数排行榜。

v0.1 仅单线性重试循环；不做证明搜索树、不做任意自然语言定理的自动形式化、不做 code↔proof 的已验证桥接（仅以 claim 为共享桥）。完整范围见仓库 issue。

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 许可证</h2>

MIT，见 [LICENSE](./LICENSE)。欢迎在 Issues 提 bug 或想试的 claim；PR 请对准 m1 范围。

> 推送后建议设置仓库 topics：`gh repo edit --add-topic lean --add-topic proof --add-topic formal-methods --add-topic agent`

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
