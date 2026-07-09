"""Build a Bambu Studio-ready .3mf project from the two keychain STLs.

Creates one object with two parts (black base + yellow logo), pre-assigned
to extruder/filament slots 1 and 2, centered on a 256 mm plate.
"""

import re
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "PLJ_Carpentry_Keychain.3mf"

STLS = [
    ("keychain_base_black.stl", "base_black", 1),
    ("keychain_logo_yellow.stl", "logo_yellow", 2),
]

VERTEX_RE = re.compile(
    r"vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)"
)


def parse_ascii_stl(path: Path) -> tuple[list[tuple], list[tuple]]:
    """Return (vertices, triangles) with deduplicated vertices."""
    verts: list[tuple] = []
    index: dict[tuple, int] = {}
    tris: list[tuple] = []
    face: list[int] = []
    for m in VERTEX_RE.finditer(path.read_text()):
        v = (round(float(m.group(1)), 6),
             round(float(m.group(2)), 6),
             round(float(m.group(3)), 6))
        i = index.get(v)
        if i is None:
            i = len(verts)
            index[v] = i
            verts.append(v)
        face.append(i)
        if len(face) == 3:
            tris.append(tuple(face))
            face = []
    return verts, tris


def mesh_xml(obj_id: int, verts: list, tris: list) -> str:
    vs = "".join(
        f'<vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts
    )
    ts = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris
    )
    return (
        f'<object id="{obj_id}" type="model">'
        f"<mesh><vertices>{vs}</vertices>"
        f"<triangles>{ts}</triangles></mesh></object>"
    )


def build() -> None:
    objects = []
    for fname, _, _ in STLS:
        verts, tris = parse_ascii_stl(HERE / fname)
        objects.append(mesh_xml(len(objects) + 1, verts, tris))
        print(f"{fname}: {len(verts)} vertices, {len(tris)} triangles")

    identity = "1 0 0 0 1 0 0 0 1 0 0 0"
    assembly_id = len(objects) + 1
    components = "".join(
        f'<component objectid="{i + 1}" transform="{identity}"/>'
        for i in range(len(objects))
    )
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        "<metadata name=\"Title\">PLJ Carpentry Keychain</metadata>"
        "<metadata name=\"Application\">OpenSCAD+script</metadata>"
        f"<resources>{''.join(objects)}"
        f'<object id="{assembly_id}" type="model">'
        f"<components>{components}</components></object>"
        "</resources>"
        f'<build><item objectid="{assembly_id}" '
        'transform="1 0 0 0 1 0 0 0 1 128 128 0" printable="1"/></build>'
        "</model>"
    )

    parts = "".join(
        f'<part id="{i + 1}" subtype="normal_part">'
        f'<metadata key="name" value="{name}"/>'
        f'<metadata key="extruder" value="{extruder}"/>'
        "</part>"
        for i, (_, name, extruder) in enumerate(STLS)
    )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<config>"
        f'<object id="{assembly_id}">'
        '<metadata key="name" value="PLJ_Carpentry_Keychain"/>'
        '<metadata key="extruder" value="1"/>'
        f"{parts}</object>"
        "</config>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
        'content-types">'
        '<Default Extension="rels" ContentType="application/vnd.'
        'openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.'
        'ms-package.3dmanufacturing-3dmodel+xml"/>'
        '<Default Extension="config" ContentType="text/xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
        '2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/'
        '3dmodel"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
