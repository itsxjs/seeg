#!/usr/bin/env python3
"""
管理外接硬盘上的多个数据源
支持从多个下载目录访问DANDI数据
"""
from pathlib import Path
from typing import Optional

# 数据目录优先级（从高到低）
DATA_SOURCES = [
    Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/000623"),  # 直接下载到外接硬盘的新数据
    Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/keles_dandiset_000623"),  # 迁移的旧数据
]

def find_nwb_file(subject: str, session: str) -> Optional[Path]:
    """
    在多个数据源中查找NWB文件
    优先使用最新的下载位置
    """
    filename_patterns = [
        f"{subject}_ses-{session}_behavior+ecephys.nwb.dandidownload/file",
        f"{subject}_ses-{session}_behavior+ecephys.nwb",
    ]
    
    for source in DATA_SOURCES:
        for pattern in filename_patterns:
            nwb_file = source / subject / pattern
            if nwb_file.exists():
                return nwb_file
    
    raise FileNotFoundError(
        f"找不到 {subject}/{session} 的NWB文件\n"
        f"已搜索的位置: {[str(s) for s in DATA_SOURCES]}"
    )

def get_all_subjects() -> dict:
    """获取所有可用的被试和session"""
    subjects_data = {}
    
    for source in DATA_SOURCES:
        if not source.exists():
            continue
        
        for subdir in sorted(source.glob("sub-*")):
            if not subdir.is_dir():
                continue
            
            subject = subdir.name
            if subject not in subjects_data:
                subjects_data[subject] = []
            
            # 找到所有session
            for nwb_dir in subdir.glob("*_behavior+ecephys.nwb*"):
                session_name = nwb_dir.name.split("_ses-")[1].split("_")[0] if "_ses-" in nwb_dir.name else None
                if session_name and session_name not in subjects_data[subject]:
                    subjects_data[subject].append(session_name)
    
    return subjects_data

if __name__ == "__main__":
    import json
    
    print("📊 可用的数据源:")
    for i, source in enumerate(DATA_SOURCES, 1):
        exists = "✓" if source.exists() else "✗"
        size = f"({(sum(f.stat().st_size for f in source.rglob('*')) / 1e9):.1f} GB)" if source.exists() else ""
        print(f"  {i}. {exists} {source} {size}")
    
    print("\n📋 可用被试:")
    subjects = get_all_subjects()
    for subject in sorted(subjects.keys()):
        sessions = subjects[subject]
        print(f"  {subject}: {', '.join(sorted(sessions))}")
    
    print(f"\n✓ 总计: {len(subjects)} 个被试")
