from __future__ import annotations

from typing import List

from PIL import Image, ImageDraw, ImageFont


def draw_simple_table(
    data: List[List[str]],
    output_path: str = "table.png",
) -> str:
    """
    Generate a simple table image from a 2D list of strings.
    Used by the currency feature.
    """
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_size = 20
    padding_x = 20
    padding_y = 10
    row_height = font_size + 2 * padding_y
    col_padding = 30

    font = ImageFont.truetype(font_path, font_size)
    col_widths: list[int] = []
    for col in zip(*data):
        col_width = max(font.getlength(str(cell)) for cell in col) + col_padding
        col_widths.append(int(col_width))

    width = sum(col_widths)
    height = row_height * len(data)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    y = 0
    for row in data:
        x = 0
        for i, cell in enumerate(row):
            draw.text(
                (x + padding_x, y + padding_y),
                str(cell),
                font=font,
                fill="black",
            )
            x += col_widths[i]
        y += row_height

    # grid
    y = 0
    for _ in data:
        draw.line([(0, y), (width, y)], fill="gray", width=1)
        y += row_height
    x = 0
    for w in col_widths:
        draw.line([(x, 0), (x, height)], fill="gray", width=1)
        x += w
    draw.line([(0, height - 1), (width, height - 1)], fill="gray", width=1)
    draw.line([(width - 1, 0), (width - 1, height)], fill="gray", width=1)

    img.save(output_path)
    return output_path

