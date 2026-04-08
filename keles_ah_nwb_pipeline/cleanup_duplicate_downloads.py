#!/usr/bin/env python3
"""
清理冗余的下载目录，只保留最新的000623
"""
import shutil
import sys
from pathlib import Path

# 定义路径
DATA_ROOT = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data")
KEEP = DATA_ROOT / "000623"
DELETE = [
    DATA_ROOT / "keles_dandiset_000623",
    DATA_ROOT / "raw"
]

print("=" * 60)
print("🧹 清理冗余下载目录")
print("=" * 60)

# 检查保留目录
print(f"\n✓ 保留: 000623")
if KEEP.exists():
    subjects_keep = sorted([d.name for d in KEEP.glob("sub-*")])
    print(f"  - {len(subjects_keep)} 个被试: {', '.join(subjects_keep)}")
else:
    print("  ✗ 不存在！")
    sys.exit(1)

# 删除其他目录
print(f"\n❌ 删除冗余目录:")
for delete_dir in DELETE:
    if delete_dir.exists():
        print(f"  {delete_dir.name}...", end=" ")
        try:
            # 备份信息
            items = list(delete_dir.glob("*"))
            shutil.rmtree(delete_dir)
            print("✓ 已删除")
        except Exception as e:
            print(f"✗ 错误: {e}")
    else:
        print(f"  {delete_dir.name}: 不存在")

print("\n" + "=" * 60)
print("✅ 清理完成")
print("=" * 60)

# 验证
remaining = sorted([d.name for d in DATA_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")])
print(f"\nDATA目录现在包含: {', '.join(remaining)}")
