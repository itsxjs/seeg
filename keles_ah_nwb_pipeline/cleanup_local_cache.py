#!/usr/bin/env python3
"""
安全删除本地DANDI下载缓存
确保外接硬盘上有数据后再删除
"""
import shutil
from pathlib import Path
import sys

# 本地缓存位置
LOCAL_CACHE = Path("/Users/defanive/Desktop/Diploma/seeg分析脚本scene/000623/000623")

# 外接硬盘上的数据
EXTERNAL_DATA = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/000623")
EXTERNAL_DATA_BACKUP = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/keles_dandiset_000623")

print("🔍 删除本地DANDI缓存前的安全检查...")
print()

# 检查外接硬盘数据完整性
def count_subjects(path):
    if not path.exists():
        return 0
    return len(list(path.glob("sub-*")))

external_count = count_subjects(EXTERNAL_DATA) + count_subjects(EXTERNAL_DATA_BACKUP)
print(f"✓ 外接硬盘被试数: {external_count}")
print(f"  - {EXTERNAL_DATA.name}: {count_subjects(EXTERNAL_DATA)} 个被试")
print(f"  - {EXTERNAL_DATA_BACKUP.name}: {count_subjects(EXTERNAL_DATA_BACKUP)} 个被试")
print()

# 检查本地缓存
if LOCAL_CACHE.exists():
    local_size = sum(f.stat().st_size for f in LOCAL_CACHE.rglob("*")) / 1e9
    local_count = count_subjects(LOCAL_CACHE)
    print(f"📂 本地缓存: {local_size:.2f} GB ({local_count} 个被试)")
    print(f"   路径: {LOCAL_CACHE}")
else:
    print(f"✓ 本地缓存已不存在")
    sys.exit(0)

print()

# 安全检查
if external_count < 3:
    print(f"⚠️ 错误: 外接硬盘上的被试数 ({external_count}) 少于本地 ({local_count})")
    print("取消删除操作")
    sys.exit(1)

print(f"✅ 安全检查通过 (外接硬盘: {external_count} 个被试 ≥ 本地: {local_count} 个被试)")
print()

# 确认删除
response = input(f"⚠️ 确认删除本地缓存 ({local_size:.2f} GB)? [y/N] ")
if response.lower() != 'y':
    print("已取消删除")
    sys.exit(0)

print()
print("🗑️ 删除中...")
try:
    shutil.rmtree(LOCAL_CACHE)
    print(f"✅ 成功删除 {LOCAL_CACHE}")
    
    # 验证删除结果
    if not LOCAL_CACHE.exists():
        print(f"✓ 验证成功：文件已完全删除")
    
    # 显示本地空间释放
    import subprocess
    result = subprocess.run(["du", "-sh", str(LOCAL_CACHE.parent)], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print()
        print("📊 释放后的本地目录大小:")
        print(result.stdout.strip())
        
except Exception as e:
    print(f"❌ 删除失败: {e}")
    sys.exit(1)
