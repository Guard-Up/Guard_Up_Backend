"""
표 양식 계약서 렌더링 — 실제 주택임대차표준계약서처럼 칸이 나뉜 A4 페이지로 그린다.
{이름}.json → {이름}_p1.png, {이름}_p2.png … (A4 한 장을 넘으면 다음 장으로 넘어감)

실행:
    .venv/bin/python tests/fixtures/make_contract_table_image.py sample_contract_table

json 형식:
    {"title": "...", "blocks": [
        {"type": "para", "text": "...", "size": 19},
        {"type": "heading", "text": "[임차주택의 표시]"},
        {"type": "table", "group": "임대인",            # 생략 가능. 왼쪽 세로 병합 칸
         "rows": [[["소재지", 0.18, true], ["서울특별시 …", 0.82]], …]}   # [글자, 폭 비율, 라벨칸 여부]
    ]}
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
_BASE = sys.argv[1] if len(sys.argv) > 1 else "sample_contract_table"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
]

PAGE_W, PAGE_H = 1240, 1754  # A4, 150dpi
MARGIN = 80
CONTENT_W = PAGE_W - MARGIN * 2
PAD = 10
LINE_GAP = 8
GROUP_W = 0.11  # 세로 병합 칸 폭 비율
LABEL_FILL = (238, 238, 238)


def _font_path() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError("한글 폰트를 찾을 수 없습니다.")


_FONT_PATH = _font_path()
_fonts: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(_FONT_PATH, size)
    return _fonts[size]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """폭을 넘는 줄을 글자 단위로 줄바꿈 (한글은 단어 경계가 불분명하므로)."""
    out = []
    for raw in text.split("\n"):
        line = ""
        for ch in raw:
            if draw.textlength(line + ch, font=font) > width and line:
                out.append(line)
                line = ch.lstrip()
            else:
                line += ch
        out.append(line)
    return out


class Document:
    def __init__(self):
        self.pages: list[Image.Image] = []
        self._new_page()

    def _new_page(self):
        img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.pages.append(img)
        self.draw = ImageDraw.Draw(img)
        self.y = MARGIN

    def _ensure(self, height: int):
        if self.y + height > PAGE_H - MARGIN:
            self._new_page()

    def title(self, text: str):
        f = _font(40)
        w = self.draw.textlength(text, font=f)
        self.draw.text(((PAGE_W - w) / 2, self.y), text, font=f, fill="black")
        self.y += 40 + 30

    def para(self, text: str, size: int = 19):
        f = _font(size)
        lh = size + LINE_GAP
        for line in _wrap(self.draw, text, f, CONTENT_W):
            self._ensure(lh)
            self.draw.text((MARGIN, self.y), line, font=f, fill="black")
            self.y += lh
        self.y += 6

    def heading(self, text: str):
        self._ensure(60)
        self.y += 10
        self.draw.text((MARGIN, self.y), text, font=_font(23), fill="black")
        self.y += 23 + 14

    def table(self, rows: list, group: str | None = None, size: int = 18):
        f = _font(size)
        lh = size + LINE_GAP
        left = MARGIN + (int(CONTENT_W * GROUP_W) if group else 0)
        width = MARGIN + CONTENT_W - left

        # 행 높이 미리 계산 (행은 페이지에서 쪼개지 않음, 병합 칸이 있으면 표 전체를 한 장에)
        layout = []
        for row in rows:
            cells = []
            for text, ratio, *flag in row:
                cw = int(width * ratio)
                lines = _wrap(self.draw, text, f, cw - PAD * 2)
                cells.append((lines, cw, bool(flag and flag[0])))
            row_h = max(len(c[0]) for c in cells) * lh + PAD * 2
            layout.append((cells, row_h))

        total = sum(h for _, h in layout)
        self._ensure(total if group else layout[0][1])
        top = self.y

        for cells, row_h in layout:
            self._ensure(row_h)
            x = left
            for i, (lines, cw, is_label) in enumerate(cells):
                # 마지막 칸은 반올림 오차를 오른쪽 끝에 맞춤
                right = MARGIN + CONTENT_W if i == len(cells) - 1 else x + cw
                self.draw.rectangle([x, self.y, right, self.y + row_h],
                                    outline="black", width=2, fill=LABEL_FILL if is_label else "white")
                ty = self.y + PAD
                for line in lines:
                    if is_label:  # 라벨 칸은 가운데 정렬
                        tw = self.draw.textlength(line, font=f)
                        self.draw.text((x + (right - x - tw) / 2, ty), line, font=f, fill="black")
                    else:
                        self.draw.text((x + PAD, ty), line, font=f, fill="black")
                    ty += lh
                x = right
            self.y += row_h

        if group:
            self.draw.rectangle([MARGIN, top, left, self.y], outline="black", width=2, fill=LABEL_FILL)
            gy = top + (self.y - top - len(group) * lh) / 2
            for ch in group:  # 세로쓰기
                cw = self.draw.textlength(ch, font=f)
                self.draw.text((MARGIN + (left - MARGIN - cw) / 2, gy), ch, font=f, fill="black")
                gy += lh
        self.y += 14


def render(spec: dict) -> list[Image.Image]:
    doc = Document()
    doc.title(spec["title"])
    for b in spec["blocks"]:
        if b["type"] == "para":
            doc.para(b["text"], b.get("size", 19))
        elif b["type"] == "heading":
            doc.heading(b["text"])
        elif b["type"] == "table":
            doc.table(b["rows"], b.get("group"))
        else:
            raise ValueError(f"알 수 없는 블록: {b['type']}")
    return doc.pages


def main():
    spec = json.loads((HERE / f"{_BASE}.json").read_text(encoding="utf-8"))
    for old in HERE.glob(f"{_BASE}_p*.png"):
        old.unlink()
    pages = render(spec)
    for i, page in enumerate(pages, start=1):
        path = HERE / f"{_BASE}_p{i}.png"
        page.save(path)
        print(f"생성 완료: {path} ({PAGE_W}x{PAGE_H})")


if __name__ == "__main__":
    main()
