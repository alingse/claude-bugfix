#!/usr/bin/env python3
"""Demo script to show interactive mode UI (without actual LLM calls)."""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.rule import Rule
from rich.prompt import Prompt
from rich.text import Text

console = Console()


def demo_interactive_ui():
    """Demonstrate the interactive UI."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🐛 Claude Bugfix[/bold cyan] - [dim]交互式代码修复助手[/dim]\n"
        "[dim]工作目录: /Users/zhihu/output/github/claude-bugfix[/dim]",
        border_style="cyan"
    ))

    # User input
    console.print()
    console.print("[bold]请输入 bug 描述[/bold] (或 '[red]quit[/red]' 退出):")
    console.print("> 用户登录时程序崩溃，提示空指针异常")

    # Agent thinking
    console.print()
    console.print("[bold cyan][第1步/20] 🤔 Agent 正在思考...[/bold cyan]")
    console.print("[yellow]▶ 🔍 搜索代码: 'login'[/yellow]")
    console.print("确认执行? [Y/n/a(全部跳过)]: y")

    # Search result
    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
    console.print("[cyan]Found 3 match(es):[/cyan]")
    console.print("  [green]src/auth.py[/green]:[yellow]45[/yellow]: def login(username, password):")
    console.print("  [green]src/auth.py[/green]:[yellow]67[/yellow]: if user is None:")
    console.print("  [green]src/main.py[/green]:[yellow]12[/yellow]: from auth import login")
    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")

    # Step 2
    console.print()
    console.print("[bold cyan][第2步/20] 🤔 Agent 正在思考...[/bold cyan]")
    console.print("[yellow]▶ 📖 读取文件: src/auth.py[/yellow]")
    console.print("确认执行? [Y/n/a(全部跳过)]: y")

    # File content
    code = '''def login(username, password):
    user = db.get_user(username)
    if user is None:
        return None
    if user.password == hash(password):  # <-- 潜在问题
        return user
    return None
'''
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(syntax)

    # Step 3
    console.print()
    console.print("[bold cyan][第3步/20] 🤔 Agent 正在思考...[/bold cyan]")
    console.print("[yellow]▶ 🔍 搜索代码: 'verify_password'[/yellow]")
    console.print("确认执行? [Y/n/a(全部跳过)]: y")

    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
    console.print("[cyan]Found 1 match:[/cyan]")
    console.print("  [green]src/utils.py[/green]:[yellow]23[/yellow]: def verify_password(pwd, hash):")
    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")

    # Step 4
    console.print()
    console.print("[bold cyan][第4步/20] 🤔 Agent 正在思考...[/bold cyan]")
    console.print("[yellow]▶ 📖 读取文件: src/utils.py[/yellow]")
    console.print("确认执行? [Y/n/a(全部跳过)]: a")  # User chose to auto-skip

    # Utils content
    utils_code = '''def verify_password(password, password_hash):
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode(), password_hash)
'''
    console.print(Syntax(utils_code, "python", theme="monokai", line_numbers=True))

    # Final answer
    console.print()
    console.print(Panel(
        Markdown("""
## 💡 分析结果

### 根因
在 `src/auth.py` 第 6 行，直接比较 `user.password == hash(password)` 存在两个问题：
1. 使用了错误的哈希函数 `hash()` 而不是安全的密码验证
2. 没有使用项目中已有的 `verify_password` 函数

### 建议修复
```python
def login(username, password):
    user = db.get_user(username)
    if user is None:
        return None
    if not verify_password(password, user.password):
        return None
    return user
```

### 需要修改
- `src/auth.py`: 导入 `verify_password` 并替换密码比较逻辑

确认应用此修复吗? [Y/n/e(编辑)]: 
"""),
        title="[bold green]💡 分析完成[/bold green]",
        border_style="green"
    ))

    # Token usage
    console.print()
    console.print(Rule(style="dim"))
    console.print(
        "[dim]迭代次数: 4 | "
        "Token 使用: 1,245 (输入: 856, 输出: 389)[/dim]"
    )
    console.print(Rule(style="dim"))

    console.print()
    console.print("[dim]可以继续输入新的 bug 描述，或输入 'quit' 退出[/dim]")
    console.print()


if __name__ == "__main__":
    demo_interactive_ui()
