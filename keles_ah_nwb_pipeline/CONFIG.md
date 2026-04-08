# Keles et al. NWB Pipeline Configuration

## 📍 **外接硬盘数据存储**

### ✅ **直接下载到外接硬盘** (推荐)
```
📂 /Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/
├── 000623/                          ← 直接下载的最新数据 (0.0 GB - 仍在下载中)
│   ├── sub-CS41, CS42, CS43
│   ├── sub-CS44, CS47, CS48, CS49   ← 新增被试
│   └── ... (继续下载)
└── keles_dandiset_000623/           ← 迁移的初始数据 (2.1 GB)
    ├── sub-CS41, CS42, CS43
    └── dandiset.yaml
```

### 📊 **下载统计**
- **已完成**: 7 个被试 (2.1 GB)
- **被试列表**:
  - sub-CS41: P41CSR1, P41CSR2 ✓
  - sub-CS42: P42CSR1, P42CSR2 ✓
  - sub-CS43: P43CSR1, P43CSR2 ✓
  - sub-CS44: P44CSR1 ✓
  - sub-CS47: P47CSR1, P47CSR2 ✓
  - sub-CS48: P48CSR1, P48CSR2 ✓
  - sub-CS49: P49CSR2 ✓
- **下载状态**: 🔄 进行中 (新被试持续加入)
- **本地空间**: 节省 ✅ (直接下载到外接硬盘，无占用本地24GB)

## 🔧 **项目代码位置**
```
📂 /Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/
├── ah_pipeline/                 ← Python管道模块
│   ├── nwb_io.py
│   ├── preprocessing.py
│   ├── time_frequency.py
│   ├── spikes.py
│   ├── connectivity_stats.py
│   ├── statistics.py
│   └── export.py
├── data_manager.py              ← 多数据源管理工具
├── run_pipeline.py              ← 主管道脚本
├── run_one_subject_full.py      ← 单被试测试脚本
├── download_to_external.sh      ← 下载脚本
├── results/                     ← 输出结果目录
└── data/                        ← 所有数据存储
    ├── 000623/                  ← 直接下载
    └── keles_dandiset_000623/   ← 初始数据
```

## 🚀 **查看可用的被试和数据**

```bash
cd /Volumes/人盘含鱼纹/keles_ah_nwb_pipeline
python data_manager.py
```

## 📝 **好处**
1. ✅ 本地硬盘节省（24GB剩余空间）
2. ✅ 外接硬盘充足空间（926GB可用）
3. ✅ 下载不受中断（后台进程）
4. ✅ 支持多数据源（自动查找）

