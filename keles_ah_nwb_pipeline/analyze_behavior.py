import scipy.io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import os

# Paths
data_dir = Path('/Users/defanive/Desktop/Diploma/SEEG_behavior')
output_dir = Path('/Volumes/rmhyw/result/behavior_analysis')
output_dir.mkdir(parents=True, exist_ok=True)

mat_files = list(data_dir.glob("*ratingmatrix.mat"))

all_data = []

print(f"Found {len(mat_files)} subjects.")

for mat_path in mat_files:
    sub_id = mat_path.name.split('_')[0]
    if sub_id == 'sub008':
        print(f"  Skipping {sub_id} as requested.")
        continue
    try:
        mat_data = scipy.io.loadmat(str(mat_path))
        # Assuming the matrix name contains 'rating' or is the only large array
        keys = [k for k in mat_data.keys() if not k.startswith('__')]
        
        # Look for the matrix (usually 2D)
        matrix = None
        for k in keys:
            if isinstance(mat_data[k], np.ndarray) and mat_data[k].ndim == 2:
                matrix = mat_data[k]
                break
        
        if matrix is not None:
            # Column 3 is index 2 (like/dislike)
            # We want to check the distribution of ratings
            ratings = matrix[:, 2]
            
            df_sub = pd.DataFrame({
                'subject': sub_id,
                'rating': ratings,
                'is_like': (ratings >= 4).astype(int), # Assuming 1-6 or similar, 4+ is like
                'is_dislike': (ratings <= 2).astype(int)
            })
            all_data.append(df_sub)
            print(f"  Processed {sub_id}: {len(ratings)} trials, mean rating: {ratings.mean():.2f}")
    except Exception as e:
        print(f"  Error processing {mat_path}: {e}")

if not all_data:
    print("No data found!")
    exit()

df_all = pd.concat(all_data, ignore_index=True)

# 1. Subject-level summary
sub_summary = df_all.groupby('subject')['rating'].agg(['mean', 'std', 'count']).reset_index()
print("\nSubject Summary:")
print(sub_summary)

# 2. Global distribution
plt.figure(figsize=(10, 6))
sns.countplot(data=df_all, x='rating', palette='viridis')
plt.title('Global Distribution of Like/Dislike Ratings (Across all Subjects)')
plt.xlabel('Rating (e.g., 1=Strong Dislike, 6=Strong Like)')
plt.ylabel('Count')
plt.savefig(output_dir / 'global_rating_distribution.png')

# 3. Individual Subject Distributions (Comparison)
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_all, x='subject', y='rating', palette='Set3')
plt.title('Rating Distribution by Subject')
plt.savefig(output_dir / 'rating_by_subject_boxplot.png')

# 4. Binary split summary (Like vs Dislike count)
df_binary = df_all.groupby('subject').agg({
    'is_like': 'sum',
    'is_dislike': 'sum'
}).reset_index()

plt.figure(figsize=(10, 6))
df_binary_melt = df_binary.melt(id_vars='subject', value_vars=['is_like', 'is_dislike'], var_name='Category', value_name='Trial Count')
sns.barplot(data=df_binary_melt, x='subject', y='Trial Count', hue='Category', palette=['#ef476f', '#118ab2'])
plt.title('Number of Like vs Dislike Trials per Subject')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(output_dir / 'binary_trial_counts.png')

print(f"\nAnalysis complete. Results saved to {output_dir}")
