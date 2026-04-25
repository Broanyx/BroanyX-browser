"""
make_icon.py
------------
Converts the generated PNG icon to a proper multi-resolution .ico file.
Run once: python make_icon.py

Requires: Pillow  (pip install Pillow)
"""

import os
import sys
from pathlib import Path


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Installing Pillow...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image

    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Source PNG — copy from wherever it was generated
    # Try common locations
    src_candidates = [
        assets_dir / "icon.png",
        Path(__file__).parent / "icon.png",
        # The generated file path from Antigravity
        Path(r"C:\Users\LENOVO\.gemini\antigravity\brain\20ad449d-82bb-4fe7-b9cd-3de3770f2eda\broanyx_icon_1777098724826.png"),
    ]

    src = None
    for candidate in src_candidates:
        if candidate.exists():
            src = candidate
            break

    if src is None:
        print("ERROR: Could not find source PNG. Please copy it to assets/icon.png and run again.")
        sys.exit(1)

    print(f"Using source: {src}")

    img = Image.open(src).convert("RGBA")

    # Generate all standard icon sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_path = assets_dir / "icon.ico"

    img.save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )

    # Also save a copy of the PNG in assets for use in the app
    png_path = assets_dir / "icon.png"
    if not png_path.exists():
        img.save(png_path, format="PNG")

    print(f"✅ Icon saved: {ico_path}")
    print(f"   Sizes included: {sizes}")


if __name__ == "__main__":
    main()
