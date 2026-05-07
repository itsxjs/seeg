import scipy.io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Publication-style Chinese figure settings
sns.set_theme(style="whitegrid", context="paper")
plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "Heiti TC",
    "Songti SC",
    "PingFang SC",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 12
plt.rcParams["axes.labelsize"] = 14
plt.rcParams["xtick.labelsize"] = 11
plt.rcParams["ytick.labelsize"] = 11
plt.rcParams["legend.fontsize"] = 11

# Paths
data_dir = Path('/Users/defanive/Desktop/Diploma/SEEG_behavior')
output_dir = Path('/Volumes/rmhyw/result/behavior_analysis/scene')
output_dir.mkdir(parents=True, exist_ok=True)

mat_files = list(data_dir.glob("*scene.mat"))
all_data = []

print(f"Found {len(mat_files)} scene behavior files.")

for mat_path in mat_files:
    sub_id = mat_path.name.split('_')[0]
    # Skip sub008 as per previous instruction for general analysis, if you want him back, remove this.
    if sub_id == 'sub008':
        print(f"  Skipping {sub_id} (excluded).")
        continue
        
    try:
        mat_data = scipy.io.loadmat(str(mat_path))
        # Look for the main matrix
        matrix = None
        for k in mat_data.keys():
            if not k.startswith('__') and isinstance(mat_data[k], np.ndarray) and mat_data[k].ndim == 2:
                # Expecting at least 6 columns
                if mat_data[k].shape[1] >= 6:
                    matrix = mat_data[k]
                    break
        
        if matrix is not None:
            # Column 3 (idx 2): Response (0 is no response)
            # Column 4 (idx 3): Reaction Time (RT)
            # Column 5 (idx 4): Expected/Target Category (assumed based on [3,2,1,2,3...])
            # Column 6 (idx 5): Image Label
            resp = matrix[:, 2]
            rt = matrix[:, 3]
            target = matrix[:, 4]  # Column 5
            label = matrix[:, 5]
            
            df_sub = pd.DataFrame({
                'subject': sub_id,
                'response': resp,
                'target': target,
                'rt': rt,
                'label': label,
                'responded': (resp != 0).astype(int),
                'correct': (resp == target).astype(int)
            })
            # Filter out extreme outliers in RT if necessary (optional)
            # df_sub = df_sub[df_sub['rt'] > 0]
            
            all_data.append(df_sub)
            resp_rate = df_sub['responded'].mean() * 100
            mean_rt = df_sub[df_sub['responded'] == 1]['rt'].mean()
            print(f"  Processed {sub_id}: {len(resp)} trials, Response Rate: {resp_rate:.2f}%, Mean RT: {mean_rt:.4f}s")
    except Exception as e:
        print(f"  Error processing {mat_path}: {e}")

if not all_data:
    print("No valid scene data found!")
    exit()

df_all = pd.concat(all_data, ignore_index=True)
# Sort by subject ID numerically
df_all['subject_num'] = df_all['subject'].str.extract(r'(\d+)').astype(float)
df_all = df_all.sort_values(by='subject_num').drop(columns='subject_num')

# 1. Subject-level statistics
summary = df_all.groupby('subject').agg({
    'responded': 'mean',
    'correct': 'mean',
    'rt': lambda x: x[df_all.loc[x.index, 'responded'] == 1].mean()
}).reset_index()
summary.columns = ['subject', 'response_rate', 'accuracy', 'mean_rt']
subject_order = summary['subject'].tolist()
print("\nScene Behavior Summary (Accuracy = Response matches Column 5):")
print(summary)

# Publication preview-layout figure: a accuracy, b RT distribution
fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.6), constrained_layout=True)
palette_acc = sns.color_palette("rocket", n_colors=len(subject_order))

sns.barplot(
    data=summary,
    x='subject',
    y='accuracy',
    order=subject_order,
    palette=palette_acc,
    hue='subject',
    dodge=False,
    ax=axes[0],
)
axes[0].axhline(1 / 3, color='0.55', linestyle='--', linewidth=1.2, alpha=0.7)
axes[0].set_xlabel('被试')
axes[0].set_ylabel('正确率')
axes[0].set_ylim(0, 1.05)
axes[0].legend([], frameon=False)
axes[0].tick_params(axis='x', rotation=0)

df_resp_only = df_all[df_all['responded'] == 1]
sns.violinplot(
    data=df_resp_only,
    x='subject',
    y='rt',
    inner='quart',
    color='#9ecae1',
    linewidth=1.0,
    order=subject_order,
    ax=axes[1],
)
axes[1].set_xlabel('被试')
axes[1].set_ylabel('反应时 (s)')
axes[1].tick_params(axis='x', rotation=0)

for label, ax in zip(['a', 'b'], axes):
    ax.text(
        -0.08,
        1.06,
        label,
        transform=ax.transAxes,
        fontsize=18,
        fontweight='bold',
        va='bottom',
        ha='left',
        fontfamily='DejaVu Serif',
    )
    ax.spines['top'].set_visible(True)
    ax.spines['right'].set_visible(True)
    ax.grid(axis='y', color='0.88', linewidth=0.8)
    ax.grid(axis='x', visible=False)

fig.savefig(output_dir / 'study1_behavior_publication.png', dpi=300, bbox_inches='tight')
fig.savefig(output_dir / 'study1_behavior_publication.pdf', bbox_inches='tight')
plt.close(fig)

# Plot 1: Accuracy by Subject
plt.figure(figsize=(10, 6))
sns.barplot(data=summary, x='subject', y='accuracy', palette='rocket', hue='subject')
plt.title('Scene Experiment: Accuracy by Subject (Response == Target)')
plt.ylabel('Accuracy (0-1)')
plt.axhline(0.33, color='grey', linestyle='--', alpha=0.5, label='Chance (1/3)') # Assuming 3 categories
plt.ylim(0, 1.1)
plt.legend([], frameon=False)
plt.savefig(output_dir / 'scene_accuracy.png')

# Plot 2: Response Rate by Subject
plt.figure(figsize=(10, 6))
sns.barplot(data=summary, x='subject', y='response_rate', palette='viridis', hue='subject')
plt.title('Scene Experiment: Response Rate by Subject')
plt.ylabel('Response Rate (0-1)')
plt.ylim(0, 1.1)
plt.legend([], frameon=False)
plt.savefig(output_dir / 'scene_response_rate.png')

# Plot 2: Reaction Time Distribution (Violin + Swarm)
plt.figure(figsize=(12, 6))
sns.violinplot(data=df_resp_only, x='subject', y='rt', inner='quart', color='#98c1d9', order=subject_order)
plt.title('Scene Experiment: Reaction Time (RT) Distribution per Subject')
plt.ylabel('Reaction Time (s)')
plt.legend([], frameon=False)
plt.savefig(output_dir / 'scene_rt_distribution.png')

# Plot 3: Response Rate by Label (Are some images harder to react to?)
plt.figure(figsize=(14, 6))
label_summary = df_all.groupby('label')['responded'].mean().reset_index()
sns.histplot(data=label_summary, x='responded', bins=20, kde=True, color='#118ab2')
plt.title('Distribution of Response Rates Across Different Image Labels')
plt.xlabel('Response Rate')
plt.savefig(output_dir / 'scene_label_response_distribution.png')

# Plot 4: RT vs Label (Optional, but useful to see consistency)
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_resp_only, x='subject', y='rt', order=subject_order, width=0.6, color='#7aa6c2')
plt.title('Scene Experiment: RT Boxplot (Filtered for Responded Trials)')
plt.ylabel('Reaction Time (s)')
plt.legend([], frameon=False)
plt.savefig(output_dir / 'scene_rt_boxplot.png')

print(f"\nScene analysis complete. Results saved to {output_dir}")
