#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def fix(in_docx: Path, out_docx: Path) -> int:
    fixed = 0
    with zipfile.ZipFile(in_docx, "r") as zin, zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                root = etree.fromstring(data)
                for p in root.xpath(".//w:p", namespaces=NS):
                    ppr = p.find(q("pPr"))
                    if ppr is None:
                        continue
                    starts = [child for child in list(p) if child.tag == q("commentRangeStart")]
                    for start in starts:
                        idx_start = list(p).index(start)
                        idx_ppr = list(p).index(ppr)
                        if idx_start < idx_ppr:
                            p.remove(start)
                            p.insert(list(p).index(ppr) + 1, start)
                            fixed += 1
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
            zout.writestr(item, data)
    return fixed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    args = ap.parse_args()
    count = fix(Path(args.input), Path(args.output))
    print(f"fixed_comment_range_order={count}")


if __name__ == "__main__":
    main()
