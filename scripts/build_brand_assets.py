"""Render the editable brand SVG into desktop icons and the browser favicon.

Build-only requirements: resvg-py==0.5.0 and Pillow>=10. These packages are
not application/runtime dependencies. Generated assets are committed so normal
desktop builds do not require an SVG renderer.
"""
from io import BytesIO
from pathlib import Path
import shutil

from PIL import Image
import resvg_py


def main():
    root = Path(__file__).resolve().parents[1]
    assets = root / 'assets/branding'
    source = assets / 'operon.svg'
    png = resvg_py.svg_to_bytes(svg_string=source.read_text(encoding='utf-8'),
                               width=1024, height=1024)
    master = Image.open(BytesIO(png)).convert('RGBA')
    master.resize((256, 256), Image.Resampling.LANCZOS).save(assets / 'operon.png')
    master.save(assets / 'operon.ico', format='ICO',
                sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    shutil.copyfile(source, root / 'frontend/public/favicon.svg')
    print('Updated SVG favicon, 256px PNG, and 9-size Windows ICO.')


if __name__ == '__main__':
    main()
