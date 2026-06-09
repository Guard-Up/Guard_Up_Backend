"""
sample_contract.txt → sample_contract.png 렌더링.
CLOVA OCR 입력용 테스트 계약서 이미지를 생성한다.

실행:
    .venv/bin/python tests/fixtures/make_contract_image.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
TXT_PATH = HERE / "sample_contract.txt"
PNG_PATH = HERE / "sample_contract.png"

# macOS 한글 폰트 후보 (먼저 발견되는 것 사용)
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
]

FONT_SIZE = 26
LINE_HEIGHT = 40
MARGIN = 50
WIDTH = 900


def _load_font() -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    raise RuntimeError("한글 폰트를 찾을 수 없습니다. FONT_CANDIDATES를 확인하세요.")


def main() -> None:
    lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    font = _load_font()

    height = MARGIN * 2 + LINE_HEIGHT * len(lines)
    img = Image.new("RGB", (WIDTH, height), "white")
    draw = ImageDraw.Draw(img)

    y = MARGIN
    for line in lines:
        draw.text((MARGIN, y), line, fill="black", font=font)
        y += LINE_HEIGHT

    img.save(PNG_PATH, "PNG")
    print(f"생성 완료: {PNG_PATH} ({WIDTH}x{height})")


if __name__ == "__main__":
    main()
