#!/bin/bash
# 自动迁移DANDI下载的数据到外接硬盘

LOCAL_DOWNLOAD="/Users/defanive/Desktop/Diploma/seeg分析脚本scene/000623/000623"
EXTERNAL_STORAGE="/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/keles_dandiset_000623"

echo "🔄 开始迁移数据..."
echo "源位置: $LOCAL_DOWNLOAD"
echo "目标位置: $EXTERNAL_STORAGE"
echo ""

# 同步新增的被试数据
cp -R "$LOCAL_DOWNLOAD"/* "$EXTERNAL_STORAGE/" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ 数据同步完成"
    echo ""
    
    # 显示同步后的统计
    echo "📊 当前数据统计:"
    du -sh "$EXTERNAL_STORAGE/"
    echo ""
    echo "被试数量: $(find "$EXTERNAL_STORAGE" -maxdepth 1 -type d -name "sub-*" | wc -l)"
else
    echo "⚠️ 同步过程中出现错误"
fi
