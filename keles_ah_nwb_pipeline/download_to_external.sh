#!/bin/bash
# 直接在外接硬盘下载DANDI数据，避免本地空间不足

EXTERNAL_STORAGE="/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data"
DANDISET="DANDI:000623"

echo "📥 开始从DANDI下载数据到外接硬盘..."
echo "下载位置: $EXTERNAL_STORAGE"
echo ""

# 检查外接硬盘是否可用
if ! [ -d "$EXTERNAL_STORAGE" ]; then
    echo "❌ 错误：外接硬盘目录不存在"
    exit 1
fi

# 显示可用空间
echo "💾 可用空间:"
df -h "$EXTERNAL_STORAGE" | tail -1
echo ""

# 激活虚拟环境（需要从本地）
cd /Users/defanive/Desktop/Diploma/seeg分析脚本scene
source .venv/bin/activate

# 直接下载到外接硬盘
# -o 指定输出目录
# -e skip 跳过已存在的文件
# --jobs 6 并行下载6个文件
cd "$EXTERNAL_STORAGE"
dandi download -o . -e skip --jobs 6 "$DANDISET"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 下载完成"
    echo ""
    echo "📊 下载后的统计:"
    du -sh "$EXTERNAL_STORAGE/000623/"
    echo "被试数: $(find "$EXTERNAL_STORAGE/000623" -maxdepth 1 -type d -name "sub-*" | wc -l)"
else
    echo "❌ 下载过程出错"
    exit 1
fi
