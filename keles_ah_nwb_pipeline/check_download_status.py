#!/usr/bin/env python3
"""
检查本地和外接硬盘的下载状态
"""
from pathlib import Path
import shutil

# 路径定义
LOCAL_CACHE = Path("/Users/defanive/Desktop/Diploma/seeg分析脚本scene/000623/000623")
EXTERNAL_NEW = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/000623")
EXTERNAL_OLD = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/keles_dandiset_000623")

print("=" * 60)
print("📊 数据状态检查")
print("=" * 60)

# 检查本地
print("\n📂 本地缓存目录:")
if LOCAL_CACHE.exists():
    local_subjects = sorted([d.name for d in LOCAL_CACHE.glob("sub-*")])
    if local_subjects:
        local_size = sum(f.stat().st_size for f in LOCAL_CACHE.rglob("*") if f.is_file()) / 1e9
        print(f"  ✓ 存在，{local_size:.2f} GB")
        print(f"  被试: {', '.join(local_subjects)}")
        print(f"\n  ⚠️ 建议: 本地还有数据! 已验证外接硬盘有备份后再删除")
    else:
        print(f"  ✓ 目录为空")
else:
    print(f"  ✗ 目录不存在")

# 检查外接硬盘新下载位置
print("\n💾 外接硬盘-新下载位置 (000623):")
if EXTERNAL_NEW.exists():
    ext_new_subjects = sorted([d.name for d in EXTERNAL_NEW.glob("sub-*")])
    if ext_new_subjects:
        ext_new_size = sum(f.stat().st_size for f in EXTERNAL_NEW.rglob("*") if f.is_file()) / 1e9
        print(f"  ✓ {ext_new_size:.2f} GB")
        print(f"  被试: {', '.join(ext_new_subjects)}")
    else:
        print(f"  ✓ 目录存在但为空")
else:
    print(f"  ✗ 目录不存在")

# 检查外接硬盘初始位置
print("\n💾 外接硬盘-初始备份 (keles_dandiset_000623):")
if EXTERNAL_OLD.exists():
    ext_old_subjects = sorted([d.name for d in EXTERNAL_OLD.glob("sub-*")])
    if ext_old_subjects:
        ext_old_size = sum(f.stat().st_size for f in EXTERNAL_OLD.rglob("*") if f.is_file()) / 1e9
        print(f"  ✓ {ext_old_size:.2f} GB")
        print(f"  被试: {', '.join(ext_old_subjects)}")
    else:
        print(f"  ✓ 目录存在但为空")
else:
    print(f"  ✗ 目录不存在")

# 安全检查
print("\n" + "=" * 60)
print("🔍 安全性检查:")
print("=" * 60)

total_external = len(sorted([d.name for d in EXTERNAL_NEW.glob("sub-*")] + [d.name for d in EXTERNAL_OLD.glob("sub-*")]))
local_count = len(local_subjects) if LOCAL_CACHE.exists() else 0

if local_count > 0:
    if total_external >= local_count:
        print(f"✅ 外接硬盘数据充分（外{total_external}个 >= 本地{local_count}个）")
        print(f"⏭️ 可以安全删除本地数据")
    else:
        print(f"⚠️ 本地数据尚未完全转移（外{total_external}个 < 本地{local_count}个）")
        print(f"❌ 不建议删除本地数据")
else:
    print(f"✅ 本地已清空")

print("\n" + "=" * 60)
