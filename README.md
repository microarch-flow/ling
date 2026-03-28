# ling

中文输入，英文执行，中文输出。让你用母语驾驭 Claude Code。

## 为什么要做这个

我的母语是中文。在使用 Claude Code、Codex 这类 AI 编程工具时，我发现一个规律：**同样的问题，英文提示词的回答质量明显高于中文**。

这不是偶然。大语言模型的训练语料中，技术领域的英文内容（论文、文档、代码注释、技术讨论）占压倒性多数。模型对技术概念的理解本质上是**以英文为锚点**存储的。当你用中文提问时，模型需要先完成一次跨语言对齐，再激活技术知识，这个中间步骤会引入噪声，特别是在中文技术语料稀少的专业领域（如芯片微架构、编译器、底层系统）。

我尝试过用中英混合输入，效果有所提升，但仍有明显差距。根本原因在于：**我用中文没法把问题描述得像用英文那样精确**——不是翻译问题，而是思维习惯和表达精度的问题。

最理想的方案是：我用中文自然表达，由一个高质量的翻译模型将其转化为精确的英文，再交给 Claude Code 处理。Claude Code 的英文输出再翻译回中文呈现给我。整个过程对我透明。

这就是 ling 的由来。

## 工作原理

```
你（中文）→ ling → [翻译为英文] → Claude Code
     你（中文）← ling ← [翻译为中文] ← Claude Code 输出
```

- 你的中文输入被翻译为英文后发送给底层 CLI
- Claude Code 的文本输出实时翻译为中文展示
- 代码块原样透传，不参与翻译
- 会话状态和上下文由底层 CLI 自己管理，ling 是无状态的翻译层

## 安装

```bash
git clone https://github.com/microarch-flow/ling.git
cd ling
pip install -e .
```

## 配置

创建 `~/.ling/config.yaml`：

```yaml
translator:
  provider: openai          # openai | anthropic
  api_key: YOUR_KEY
  base_url: https://...     # 可选，支持第三方兼容接口
  model: gpt-4o
  accumulate_timeout: 2.0   # 输出积累窗口（秒），超时后触发翻译
  request_timeout: 30       # 翻译 API 超时（秒）
  fallback_on_timeout: true # 超时后显示原文，不阻塞流程

cli:
  command: claude           # 或 codex，或任意可执行路径
  args: []                  # 额外启动参数
```

> 直接运行 `ling` 且配置文件不存在时，会打印完整的配置示例。

## 使用

```bash
ling
```

用中文正常输入即可，翻译过程完全透明。

### 内置命令

| 命令 | 效果 |
|------|------|
| `/exit` | 退出 ling 及底层 CLI |
| `/restart` | 重启底层 CLI 进程 |
| `/lang off` | 关闭翻译（原文模式） |
| `/lang on` | 重新开启翻译 |
| `/config` | 显示当前配置 |

### 快捷键

| 按键 | 效果 |
|------|------|
| `Enter` | 提交输入 |
| `Ctrl+C` | 转发中断信号给底层 CLI（不退出 ling） |
| `Ctrl+D` | 退出 ling |

## 支持的翻译服务

兼容 OpenAI 或 Anthropic API 格式的任意服务：

- OpenAI（`provider: openai`）
- Anthropic（`provider: anthropic`）
- 第三方兼容接口（设置 `base_url` 即可）

## 环境要求

- Python 3.10+
- `claude` 或 `codex` CLI 已安装并完成认证

## 开发

```bash
pip install -e ".[dev]"
pytest
```
