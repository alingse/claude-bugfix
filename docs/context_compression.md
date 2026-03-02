# 上下文压缩 (Context Compression)

当 Agent Loop 运行时间过长或 token 使用量过高时，上下文压缩机制会自动触发，保留关键信息的同时丢弃或摘要化次要信息，让 agent 能够继续工作而不被强制终止。

## 问题背景

在复杂的代码分析任务中，agent 可能会：
- 达到最大迭代次数（默认 20 次）而未完成
- 消耗过多 token（接近 64K 限制）
- 积累大量历史消息导致上下文窗口溢出

## 解决方案

### 三层压缩策略

1. **轻量压缩 (Light)** - Token > 48K
   - 保留系统提示和用户原始请求
   - 保留最近 4 轮完整对话
   - 将早期工具调用结果摘要化

2. **中度压缩 (Medium)** - Token > 60K 或迭代 > 12
   - 创建探索摘要（Exploration Summary）
   - 记录已查看的文件、执行的搜索、遇到的错误
   - 保留最近对话上下文

3. **深度压缩 (Aggressive)** - Token > 64K 或迭代 > 17
   - 仅保留关键发现（Key Findings）
   - 记录已修改的文件
   - 保留最少的上下文继续工作

### 当达到最大迭代次数时

如果达到 20 次迭代且从未压缩过，系统会：
1. 自动应用深度压缩
2. 延长 5 次额外迭代
3. 让 agent 基于压缩后的上下文继续工作

## 使用方法

### 默认启用

压缩功能默认启用，无需额外配置：

```python
from claude_bugfix.agent.agent_loop import AgentLoop

# 压缩自动启用
agent = AgentLoop(
    llm_client=llm_client,
    tool_registry=tool_registry,
    system_prompt=system_prompt,
)
```

### 自定义配置

```python
from claude_bugfix.agent.context_compressor import CompressionConfig
from claude_bugfix.agent.agent_loop import AgentLoop

config = CompressionConfig(
    token_warning_threshold=40000,      # 40K 开始轻量压缩
    token_critical_threshold=55000,     # 55K 开始中度压缩
    token_max_limit=60000,              # 60K 上限
    keep_recent_messages=6,             # 保留最近 6 轮
)

agent = AgentLoop(
    llm_client=llm_client,
    tool_registry=tool_registry,
    system_prompt=system_prompt,
    enable_compression=True,
    compression_config=config,
)
```

### 禁用压缩

```python
agent = AgentLoop(
    llm_client=llm_client,
    tool_registry=tool_registry,
    system_prompt=system_prompt,
    enable_compression=False,  # 禁用
)
```

## 监控和统计

运行结果包含压缩统计信息：

```python
result = await agent.run("Fix the bug in calculator.py")

print(result["iterations"])           # 实际迭代次数
print(result["token_usage"])          # Token 使用统计
print(result["compression_stats"])    # 压缩统计
print(result["final_token_estimate"]) # 最终预估 token 数
```

压缩统计示例：

```python
{
    "total_compressions": 2,
    "current_level": "medium",
    "total_messages_removed": 28,
    "average_compression_ratio": 0.65,
    "compression_history": [
        {
            "level": "light",
            "original_tokens": 48500,
            "compressed_tokens": 35200,
            "ratio": 0.73
        },
        {
            "level": "medium", 
            "original_tokens": 61200,
            "compressed_tokens": 28500,
            "ratio": 0.47
        }
    ]
}
```

## 手动控制

在 `ConversationState` 上可以手动触发压缩：

```python
from claude_bugfix.agent.state_manager import ConversationState

state = ConversationState(max_iterations=20)
# ... 添加消息 ...

# 检查 token 使用量
estimate = state.get_token_estimate()
print(f"Estimated tokens: {estimate}")

# 强制压缩
result = state.force_compression(level='medium')
print(f"Compressed {result.messages_removed} messages")
print(f"Compression ratio: {result.compression_ratio}")
```

## 设计原理

### 保留优先级

从高到低：
1. **系统提示** - 定义 agent 行为，永不删除
2. **用户原始请求** - 任务定义，永不删除
3. **关键发现** - 包含 "root cause", "found" 等的分析
4. **错误信息** - 帮助避免重复错误
5. **文件修改** - write_file/replace_in_file 的结果
6. **文件读取** - 可摘要为已查看文件列表
7. **搜索操作** - 可摘要为执行次数

### 智能摘要

压缩器会提取关键信息：
- **文件探索**：记录查看了哪些文件，修改了哪些
- **关键发现**：保留包含 "root cause", "identified", "found" 的分析
- **错误历史**：保留遇到的错误类型

## 最佳实践

1. **观察压缩触发频率**：如果经常触发深度压缩，考虑增加 `max_iterations`
2. **调整阈值**：对于复杂任务，降低阈值让压缩更早发生
3. **监控压缩率**：如果平均压缩率 < 0.5，说明上下文增长过快
4. **保留足够的 recent_messages**：确保 agent 有短期记忆继续工作

## 示例输出

当压缩触发时，agent 会收到类似这样的提示：

```
[Context Compression Applied]

Due to conversation length, earlier exploration has been summarized:

• 📄 Explored 15 files
• ✏️ Modified: src/calculator.py
• 🔍 Performed 3 searches
• ⚠️ Encountered 2 errors/warnings

I will continue from the current state shown in the recent messages below.
```

这让 agent 知道发生了什么，并可以基于摘要继续工作。
