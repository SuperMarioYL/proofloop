[English](./README.en.md) · [Website](https://proofloop.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/proofloop)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# ProofLoop

**把证明尝试与生成代码一起保留。**

ProofLoop 向配置的模型请求 Python 与 Lean 草稿，将检查器错误反馈用于修订，最后保存源文件及每次尝试记录。

## 为什么需要它

最终回答容易隐藏证明如何得到、被哪个检查器接受。把草稿、错误与修订保存在一起，便于检查过程，也能拿 Lean 源文件独立验证。

- **追踪修订** — 每次尝试保留草稿与检查器错误。
- **保留证明源** — 可对 out.lean 独立检查。
- **区分示例与真实检查** — 证书保留模型与检查器标签。

## 架构

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

CLI 解析模型与检查器配置；co_iterate 从代码块读取 Python/Lean 草稿，调用检查器并请求修订，直至通过或达到次数上限。emit 写入 out.py、out.lean 与 certificate.json；--stub 将模型和检查器均替换为随仓模拟实现。

| 组件 | 职责 |
| --- | --- |
| `Claim + configuration` | src/proofloop/cli.py |
| `Draft / repair loop` | src/proofloop/agent.py |
| `Lean checker` | src/proofloop/lean.py |
| `Certificate files` | src/proofloop/certificate.py |

## 安装与快速上手

零配置先看一眼完整的 co-iteration 循环（无需 API key、无需 Lean、无需克隆仓库）：

```bash
uvx --from git+https://github.com/SuperMarioYL/proofloop proofloop prove "sum of the first n naturals = n(n+1)/2" --trace --stub
```

> 注意：PyPI 上的 `proofloop` 名字属于另一个无关项目（没有 CLI），必须用上面的 `--from git+...` 形式安装本产品。

使用仓库清单声明的运行时版本。以下源码安装步骤可复现随仓示例。

```bash
git clone https://github.com/SuperMarioYL/proofloop.git
cd proofloop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

需要 Python 3.12+；随仓驱动在临时目录完成一次 stub 运行，并回读三个产物。

```bash
python3 examples/presentation_demo.py
```

## 实际运行示例

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

The stub records a rejected attempt followed by simulated acceptance, and writes out.py, out.lean and certificate.json.

```text
{
  "model": "demo (stub)",
  "checker": "lean 4 (stub)",
  "simulated_proof_passed": true,
  "iteration_results": [
    false,
    true
  ],
  "files": [
    "certificate.json",
    "out.lean",
    "out.py"
  ]
}
```

完整命令与输出保存在 [docs/demo-results.json](./docs/demo-results.json). 输入和复现代码均随仓提供。

## 用法

安装后在仓库根目录运行以下命令；处理自己的数据时替换相应路径。

```bash
proofloop prove "sum of the first n natural numbers" --stub --trace --out-dir demo-output
# 对内置定理库跑收敛基准（--stub 为离线 harness 演示）：
proofloop bench --stub --out-dir bench-output
# With a configured API key and Lean executable:
proofloop prove "sum of the first n natural numbers" --trace --max-iter 8 --out-dir proof-output
```

## 配置

真实路径设置 PROOFLOOP_API_KEY（或 OPENAI_API_KEY）、PROOFLOOP_BASE_URL、PROOFLOOP_MODEL、PROOFLOOP_LEAN、PROOFLOOP_MAX_ITER 与 PROOFLOOP_OUT_DIR；命令行 --base-url、--model、--lean、--max-iter、--out-dir 可覆盖对应环境配置。真实检查器先拒绝 sorry/admit 文本，再调用带超时的 Lean 子进程；--stub 无需密钥或 Lean。

## 集成与职责分工

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

根据工作流选择输入与输出路径。本文本地示例验证其中明确说明的子流程。

| 路径 | 已实现职责 |
| --- | --- |
| OpenAI-compatible API | Configured draft generation |
| Lean 4 executable | Real type-checking path |
| Stub backends | Offline workflow demonstration |
| Python / Lean files | Final generated sources |
| JSON certificate | Claim, checker and iteration record |

## 限制与后续方向

- 示例检查器会放行不含 sorry/admit 的草稿，其 proof_passed 是模拟结果，不代表形式化验证。
- 即使真实 Lean 接受，也只检查 Lean 命题，不证明 Python 程序等价或自然语言需求被忠实表达；须检查定理假设与生成代码。
- 迭代耗尽后 CLI 仍写证书，未证明的命题不一定导致非零退出；应检查 proof_passed、model 与 lean_version。

更强的代码与定理关联、跨模型 live 收敛数据与独立验证的 Lean 环境是后续方向。v0.2 起随仓提供 10 条经典定理的 claims 库（[examples/library.jsonl](./examples/library.jsonl)，参考证明在构建时经 Lean 4.10.0 机器检查）与 `proofloop bench` 收敛基准（每次运行生成 leaderboard.json，不在仓库内维护 LLM 跑分数据）。

## 许可与贡献

许可见 [LICENSE](./LICENSE). 反馈问题时请提供最小输入、执行命令和实际输出。
