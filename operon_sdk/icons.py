"""Portable display assets, resolved during discovery rather than by the GUI."""
from __future__ import annotations

import base64
import inspect
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}


class _StaticSVGBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("icon SVG must not contain a DTD or entities")


def is_image_icon(value):
    return isinstance(value, str) and ("/" in value or "\\" in value or
                                      Path(value).suffix.lower() in IMAGE_TYPES)


def icon_path(directory, value):
    """Only module-relative, contained files; never a developer-machine path."""
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or ":" in value:
        raise ValueError("icon must be a relative image path inside the operator module directory")
    if relative.suffix.lower() not in IMAGE_TYPES:
        raise ValueError("icon image must be PNG, JPEG, WebP, GIF or SVG")
    path = (Path(directory) / relative).resolve()
    if not path.is_relative_to(Path(directory).resolve()):
        raise ValueError("icon image must stay inside the operator module directory")
    if not path.is_file():
        raise ValueError(f"icon image not found: {value}")
    return path


def image_data(path):
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".svg":
        # SVG is used as an image, never injected as HTML. Also reject active or
        # external content so author assets are self-contained and work offline.
        if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.I):
            raise ValueError("icon SVG must not contain a DTD or entities")
        try:
            root = ET.fromstring(data, parser=ET.XMLParser(target=_StaticSVGBuilder()))
        except ET.ParseError as exc:
            raise ValueError("icon SVG is not valid XML") from exc
        allowed = {"svg", "g", "defs", "path", "circle", "ellipse", "rect", "line", "polyline",
                   "polygon", "title", "desc", "text", "tspan", "use", "symbol", "linearGradient",
                   "radialGradient", "stop", "clipPath", "mask", "pattern"}
        if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
            raise ValueError("icon SVG requires an svg root")
        for element in root.iter():
            tag = element.tag.removeprefix("{http://www.w3.org/2000/svg}")
            if tag not in allowed:
                raise ValueError(f"icon SVG element is not supported: {tag}")
            for name, value in element.attrib.items():
                name = name.rsplit("}", 1)[-1].lower()
                urls = re.findall(r"url\s*\((.*?)\)", value, re.I)
                if (name.startswith("on") or name == "base" or
                    name == "href" and not value.startswith("#") or
                    any(not url.strip(" \t\r\n\"'").startswith("#") for url in urls) or
                    re.search(r"@import|javascript:|\\", value, re.I)):
                    raise ValueError("icon SVG must contain only static, local artwork")
    else:
        valid = ((suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                 (suffix in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff")) or
                 (suffix == ".gif" and data[:6] in {b"GIF87a", b"GIF89a"}) or
                 (suffix == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
        if not valid:
            raise ValueError(f"icon image content does not match {suffix}")
    return f"data:{IMAGE_TYPES[suffix]};base64," + base64.b64encode(data).decode("ascii")


def resolve_icon(cls, descriptor):
    """Freeze bytes into the descriptor; saved generations need no source paths."""
    value = descriptor.get("icon")
    descriptor.pop("icon_image", None)
    if is_image_icon(value):
        path = icon_path(Path(inspect.getfile(cls)).parent, value)
        descriptor["icon_image"] = image_data(path)
