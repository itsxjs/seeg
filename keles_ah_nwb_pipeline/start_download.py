#!/usr/bin/env python3
"""
启动DANDI下载到外接硬盘，避免本地空间不足
"""
import subprocess
import sys
from pathlib import Path

EXTERNAL_STORAGE = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data")

print("📥 启动DANDI下载到外接硬盘...")
print(f"下载位置: {EXTERNAL_STORAGE}")
print()

# 检查外接硬盘可用性
if not EXTERNAL_STORAGE.exists():
    print(f"❌ 错误：{EXTERNAL_STORAGE} 不存在")
    sys.exit(1)

# 改到外接硬盘目录
import os
os.chdir(EXTERNAL_STORAGE)

# 启动下载进程
print("🔄 启动下载进程...")
try:
    proc = subprocess.Popen(
        ["dandi", "download", "-o", ".", "-e", "skip", "--jobs", "6", "DANDI:000623"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    print(f"✓ 下载进程已启动 (PID: {proc.pid})")
    print()
    print("📊 实时输出:")
    print("-" * 60)
    
    # 显示前100行输出后退出，让进程继续后台运行
    for i, line in enumerate(proc.stdout):
        print(line.rstrip())
        if i >= 100:
            print("\n... (下载继续在后台进行) ...\n")
            break
    
except Exception as e:
    print(f"❌ 错误: {e}")
    sys.exit(1)
