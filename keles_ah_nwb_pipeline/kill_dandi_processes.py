#!/usr/bin/env python3
"""
终止DANDI下载进程
"""
import subprocess
import os
import signal

print("🔍 查找DANDI相关进程...")

# 用pgrep找出进程
result = subprocess.run(
    ["pgrep", "-f", "dandi"],
    capture_output=True,
    text=True
)

pids = result.stdout.strip().split('\n')
pids = [p for p in pids if p]  # 过滤空字符串

if not pids:
    print("✓ 没有运行中的DANDI进程")
else:
    print(f"找到 {len(pids)} 个DANDI相关进程:")
    for pid in pids:
        print(f"  - PID {pid}")
        try:
            os.kill(int(pid), signal.SIGKILL)
            print(f"    ✓ 已终止")
        except Exception as e:
            print(f"    ✗ 错误: {e}")

print("\n✓ 完成")
