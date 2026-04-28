#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor, Pt
from docx.text.paragraph import Paragraph


COMMENTS = [
    (
        "短视频偏好加工的探索性颅内电生理证据",
        "已将论文主线从过度使用/成瘾机制收回到短视频偏好加工。若后续要重新讨论过度使用风险，建议补充问题性短视频使用量表、持续观看行为或高低风险组数据。",
    ),
    (
        "研究三作为公开自然视频数据的补充性探索",
        "研究三的刺激、任务、行为指标和统计对象均不同于研究一/二，因此改为补充性探索，不再表述为验证。",
    ),
    (
        "本研究仅将其作为探索性自动标注结果",
        "AI高唤醒标注缺少人工复核和一致性评估，且与随机基线比较未达显著，不能作为强证据。",
    ),
    (
        "该结果应理解为探索性、描述性的发现",
        "n=3 的 LFP 分析不宜作稳定组水平推断；建议后续补充每名被试效应图、cluster-level p值和统计单位说明。",
    ),
    (
        "聚类结果后的条件差异检验存在潜在循环分析风险",
        "如果聚类特征包含条件差异，再在同一数据上检验喜欢/不喜欢可能放大显著性。建议后续用独立时间窗或交叉验证。",
    ),
    (
        "需要谨慎解释不同尺度下的 sGC 数值",
        "场景切割、高唤醒全频和分频段sGC数值尺度不同。若分别为均值、积分值或其他统计量，需在方法中明确。",
    ),
]


def insert_after(paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    run = new_para.add_run("【批注】" + text)
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    run.italic = True
    return new_para


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    doc = Document(args.input)
    inserted = 0
    # Insert in reverse document order to keep anchors stable.
    for needle, comment in COMMENTS:
        hit = None
        for p in doc.paragraphs:
            if needle in p.text:
                hit = p
                break
        if hit is not None:
            insert_after(hit, comment)
            inserted += 1
    doc.save(args.output)
    print(f"inline_comments_inserted={inserted}")


if __name__ == "__main__":
    main()
