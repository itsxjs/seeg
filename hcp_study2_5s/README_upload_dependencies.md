# 研究二 5s 窗口 HCP 上传说明

## 运行入口

在 HCP MATLAB 中进入本目录后运行：

```matlab
run_study2_5s_hcp
```

脚本默认参数：

- 时间窗：baseline `[-500, 0] ms`，分析窗 `[0, 5000] ms`
- 置换：`nperm = 1000`
- 并行池：`parpool('local', 16)`
- TF 缓存：`force_recompute_tf = true`，会重算并覆盖旧的 `sub*_valence_BOSC_TF_zpower_5s.mat`
- 输出：杏仁核和海马各一套 `LME_*_5s_nperm1000.mat` 与 PNG 图

脚本默认按你的 HCP 路径设置：

```matlab
project_dir = '/public/home/u0018083/seeg_xjs';
data_dir = project_dir;
eeglab_dir = '/public/home/u0018083/sEEG_Chenglu/EEGLAB';
addpath(genpath(eeglab_dir));
```

数据和脚本放你的 `/public/home/u0018083/seeg_xjs`，EEGLAB 使用老师已有的 `/public/home/u0018083/sEEG_Chenglu/EEGLAB`。若实际路径不同，只需要改 `run_study2_5s_hcp.m` 顶部的 `project_dir`、`data_dir` 或 `eeglab_dir`。

本地验证用脚本是：

```matlab
run_study2_5s_smoke_test
```

## 需要额外上传的文件

### 1. 本目录脚本

```text
hcp_study2_5s/run_study2_5s_hcp.m
hcp_study2_5s/BOSC_tf_power.m
hcp_study2_5s/run_study2_5s_smoke_test.m   # 仅本地验证用，HCP正式跑可不传
```

### 2. EEGLAB

你说 HCP 上可以直接用老师已有的 EEGLAB，因此不需要额外上传 EEGLAB。脚本默认会调用：

```matlab
addpath(genpath('/public/home/u0018083/sEEG_Chenglu/EEGLAB'));
```

脚本使用 EEGLAB 读取 `.set/.fdt` 并重新切 5s epoch，主要函数：

```text
eeglab
pop_loadset
pop_epoch
eeg_checkset
```

### 3. 研究二 2s clean epoch 文件

脚本不会重新做 QC，而是读取已经做好的 2s clean epoch，作为 trial 白名单。这样 subject 和 trial 口径与原 2s 版本保持一致。

需要上传：

```text
sub001_4bin_epoch_clean.set
sub001_4bin_epoch_clean.fdt
sub004_4bin_epoch_clean.set
sub004_4bin_epoch_clean.fdt
sub005_4bin_epoch_clean.set
sub005_4bin_epoch_clean.fdt
sub007_4bin_epoch_clean.set
sub007_4bin_epoch_clean.fdt
sub008_4bin_epoch_clean.set
sub008_4bin_epoch_clean.fdt
sub009_4bin_epoch_clean.set
sub009_4bin_epoch_clean.fdt
```

### 4. 研究二连续数据文件

5s 窗口不能直接从 2s epoch 里延长，因此还需要连续数据来重新切 `[−0.5, 5] s`。优先上传 `_rate_preproc.set/.fdt`；如果某个被试没有 `_rate_preproc`，脚本会回退到 `_rate.set/.fdt`。

本地当前应上传这一组：

```text
sub001_rate_preproc.set
sub001_rate_preproc.fdt
sub004_rate_preproc.set
sub004_rate_preproc.fdt
sub005_rate_preproc.set
sub005_rate_preproc.fdt
sub007_rate_preproc.set
sub007_rate_preproc.fdt
sub008_rate_preproc.set
sub008_rate_preproc.fdt
sub009_rate.set
sub009_rate.fdt
```

建议在 HCP 上传后把上述 `.set/.fdt` 文件放在 `/public/home/u0018083/seeg_xjs`。如果实际目录不同，修改脚本顶部的 `data_dir`。

## 不需要额外上传的 MATLAB toolbox

你给的平台 `installed_toolboxes.txt` 已包含以下脚本会用到的 toolbox：

```text
Parallel Computing Toolbox        parpool/parfor
Statistics and Machine Learning Toolbox   fitlme/anova/findgroups
Image Processing Toolbox          bwconncomp/bwboundaries
Signal Processing Toolbox         基础信号处理函数
MATLAB                            table/categorical/quantile/绘图/save
```

因此这些 MATLAB toolbox 不需要你额外上传。

## 运行后主要输出

每个被试会先生成：

```text
sub*_valence_BOSC_TF_zpower_5s.mat
```

随后生成 ROI 统计结果：

```text
LME_Amydgala_CBPT_2D_like_dislike_FreqTime_5s_nperm1000.mat
LME_Amydgala_CBPT_2D_like_dislike_FreqTime_5s_nperm1000_Fstats.png
LME_Amydgala_CBPT_2D_like_dislike_FreqTime_5s_nperm1000_Averages.png

LME_Hippocampus_CBPT_2D_like_dislike_FreqTime_5s_nperm1000.mat
LME_Hippocampus_CBPT_2D_like_dislike_FreqTime_5s_nperm1000_Fstats.png
LME_Hippocampus_CBPT_2D_like_dislike_FreqTime_5s_nperm1000_Averages.png
```

## 注意

原来的 `sub*_4bin_epoch_clean.set/.fdt` 是 `[-0.5, 2] s` epoch，不足以直接重跑 5s 窗口；本脚本只用它们继承 QC 后的 trial 白名单，再从连续数据重新切 5s。
