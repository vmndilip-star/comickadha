"""Offline providers so the whole app runs with no API keys."""

import io

from PIL import Image, ImageDraw, ImageFont

from app.providers.image import ImageRequest

# Sheets are drawn on flat magenta so the slicer can key the background out (decision 8).
KEY_COLOR = "#FF00FF"
INK = "#1A1A1A"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _label(draw: ImageDraw.ImageDraw, center: tuple[float, float], text: str, size: int) -> None:
    font = _font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top
    x, y = center[0] - w / 2, center[1] - h / 2
    pad = size // 3
    draw.rounded_rectangle(
        (x - pad, y - pad, x + w + pad, y + h + pad), radius=pad, fill="white", outline=INK, width=2
    )
    draw.text((x - left, y - top), text, fill=INK, font=font)


class MockImageProvider:
    """Placeholder PNGs: labelled grid cells for sheets, a labelled colour card otherwise."""

    name = "mock"

    def generate(self, request: ImageRequest) -> bytes:
        if request.grid:
            return self._grid(request)
        image = Image.new(
            "RGB", (request.width, request.height), request.hints.get("tint", "#FFF8EC")
        )
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, request.width - 1, request.height - 1), outline=INK, width=6)
        _label(
            draw,
            (request.width / 2, request.height / 2),
            request.hints.get("label", request.prompt)[:40],
            40,
        )
        _label(draw, (request.width - 70, 34), "MOCK", 18)
        return _png(image)

    def _grid(self, request: ImageRequest) -> bytes:
        assert request.grid is not None
        rows, cols = request.grid
        cw, ch = request.width // cols, request.height // rows
        image = Image.new("RGB", (cw * cols, ch * rows), KEY_COLOR)
        draw = ImageDraw.Draw(image)
        skin = request.hints.get("skin", "#F2C29B")
        body = request.hints.get("tint", "#9AD0F5")
        hair = request.hints.get("hair", INK)
        face_only = request.hints.get("sheet") == "face"

        for i in range(rows * cols):
            r, c = divmod(i, cols)
            x0, y0 = c * cw, r * ch
            cx = x0 + cw / 2
            if face_only:
                rad = cw * 0.32
                cy = y0 + ch * 0.42
                draw.ellipse(
                    (cx - rad, cy - rad, cx + rad, cy + rad), fill=skin, outline=INK, width=5
                )
                draw.chord(
                    (cx - rad, cy - rad, cx + rad, cy + rad * 0.1),
                    180,
                    360,
                    fill=hair,
                    outline=INK,
                    width=5,
                )
            else:
                rad = cw * 0.14
                cy = y0 + ch * 0.26
                draw.rounded_rectangle(
                    (cx - cw * 0.17, cy + rad - 4, cx + cw * 0.17, y0 + ch * 0.74),
                    radius=12,
                    fill=body,
                    outline=INK,
                    width=5,
                )
                draw.ellipse(
                    (cx - rad, cy - rad, cx + rad, cy + rad), fill=skin, outline=INK, width=5
                )
            if i < len(request.labels):
                _label(
                    draw,
                    (cx, y0 + ch * 0.88),
                    request.labels[i].replace("_", " "),
                    max(12, cw // 14),
                )
        return _png(image)
