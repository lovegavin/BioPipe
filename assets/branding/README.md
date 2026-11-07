# Operon application icon

The editable source is `operon.svg`: a white DNA mark on a dark rounded tile
with restrained indigo accents. It extends the existing Operon DNA favicon.

`operon.ico` contains 16, 20, 24, 32, 40, 48, 64, 128 and 256 pixel images with
transparent corners. The desktop host and Setup embed this file as their Windows
application icon. Their windows, shortcuts and uninstall entry use the same mark.
`operon.png` is a 256-pixel preview. The browser favicon is generated from the
same SVG; operator-category icons are independent of application branding.

To regenerate, install the build-only `resvg-py==0.5.0` and `Pillow>=10` packages
in a development environment, then run `python scripts/build_brand_assets.py`.
These tools are not needed to install or run Operon. All assets are included
under the repository's license.
