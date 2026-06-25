"""
계약서 텍스트 → PNG 렌더링 (CLOVA OCR 입력용).
긴 줄은 이미지 폭에 맞춰 자동 줄바꿈한다.

실행:
    .venv/bin/python tests/fixtures/make_contract_image.py sample_contract_standard
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
_BASE = sys.argv[1] if len(sys.argv) > 1 else "sample_contract"
TXT_PATH = HERE / f"{_BASE}.txt"
PNG_PATH = HERE / f"{_BASE}.png"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
]

FONT_SIZE = 24
LINE_HEIGHT = 36
MARGIN = 50
WIDTH = 1000
MAX_TEXT_WIDTH = WIDTH - MARGIN * 2


def _load_font() -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    raise RuntimeError("한글 폰트를 찾을 수 없습니다.")


def _wrap(draw, text, font) -> list[str]:
    """폭을 넘는 줄을 글자 단위로 줄바꿈 (한글은 단어 경계가 불분명하므로)."""
    if not text:
        return [""]
    # 들여쓰기 보존
    indent = len(text) - len(text.lstrip(" "))
    prefix = " " * indent
    out, line = [], text[:indent]
    for ch in text[indent:]:
        if draw.textlength(line + ch, font=font) <= MAX_TEXT_WIDTH:
            line += ch
        else:
            out.append(line)
            line = prefix + "  " + ch  # 이어지는 줄은 살짝 들여씀
    out.append(line)
    return out


def main() -> None:
    src_lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    font = _load_font()

    # 줄바꿈 적용해 최종 렌더 라인 계산
    dummy = ImageDraw.Draw(Image.new("RGB", (WIDTH, 10)))
    render_lines = []
    for line in src_lines:
        render_lines.extend(_wrap(dummy, line, font))

    height = MARGIN * 2 + LINE_HEIGHT * len(render_lines)
    img = Image.new("RGB", (WIDTH, height), "white")
    draw = ImageDraw.Draw(img)

    y = MARGIN
    for line in render_lines:
        draw.text((MARGIN, y), line, fill="black", font=font)
        y += LINE_HEIGHT

    img.save(PNG_PATH, "PNG")
    print(f"생성 완료: {PNG_PATH} ({WIDTH}x{height}, {len(render_lines)}줄)")


if __name__ == "__main__":
    main()
