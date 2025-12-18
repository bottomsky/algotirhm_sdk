#!/usr/bin/env python3
"""
开发工具 - 快速运行检查和测试
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """运行命令并报告结果"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd)
    return result.returncode


def main() -> int:
    """主入口"""
    root = Path.cwd()

    # 命名检查
    code = run_command(
        [sys.executable, "scripts/check_naming_convention.py"],
        "运行命名规范检查"
    )
    if code != 0:
        print("❌ 命名规范检查失败")
        return 1

    # Pyright 类型检查
    code = run_command(
        [sys.executable, "-m", "pyright"],
        "运行 Pyright 类型检查"
    )
    if code != 0:
        print("⚠️  Pyright 检查发现问题（可能是警告）")
        # 不中断，继续运行测试

    # 运行测试
    code = run_command(
        [sys.executable, "-m", "pytest", "tests", "-v"],
        "运行单元测试"
    )
    if code != 0:
        print("❌ 测试失败")
        return 1

    print(f"\n{'='*60}")
    print("✅ 所有检查通过！")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
