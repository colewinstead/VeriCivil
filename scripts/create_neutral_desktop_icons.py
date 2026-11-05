"""Regenerate the neutral SE icon using the existing Pillow tooling."""
from pathlib import Path

from PIL import Image, ImageDraw


def create_icons(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, 976, 976), radius=200, fill="#173b32")
    # Geometric letters avoid a platform-dependent font in generated app icons.
    draw.line([(470, 340), (260, 340), (260, 510), (450, 510), (450, 684), (240, 684)], fill="#e9f5f0", width=52, joint="curve")
    draw.line([(780, 340), (580, 340), (580, 684), (780, 684)], fill="#e9f5f0", width=52, joint="curve")
    draw.line([(580, 510), (750, 510)], fill="#e9f5f0", width=52)
    image = image.resize((512, 512), Image.Resampling.LANCZOS)
    image.save(directory / "superelevation.png")
    image.save(directory / "superelevation.ico", sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    image.save(directory / "superelevation.icns")


if __name__ == "__main__":
    create_icons(Path(__file__).resolve().parents[1] / "desktop/icons")
