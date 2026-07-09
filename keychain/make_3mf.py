"""Build a Bambu Studio project (.3mf) from the two keychain STLs.

Produces a native-style Bambu project: one object with two parts
(black base + yellow relief logo), filament colors, plate choice and
print settings pre-configured, so Bambu Studio opens it print-ready.
"""

import json
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "PLJ_Carpentry_Keychain.3mf"

STLS = [
    ("keychain_base_black.stl", "base_black", 1, "#1A1A1A"),
    ("keychain_logo_yellow.stl", "logo_yellow", 2, "#F2A900"),
]

PLATE_XY = 128  # object centered on a 256 mm plate

# Print setup applied when the user opens the project WITH settings.
# Values follow Bambu Studio's project_settings.config key names.
PROJECT_SETTINGS = {
    "curr_bed_type": "Textured PEI Plate",
    "filament_colour": ["#1A1A1A", "#F2A900"],
    "filament_type": ["PLA", "PLA"],
    "filament_diameter": ["1.75", "1.75"],
    "layer_height": "0.2",
    "initial_layer_print_height": "0.2",
    "wall_loops": "3",
    "top_shell_layers": "4",
    "bottom_shell_layers": "3",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "enable_support": "0",
    "brim_type": "no_brim",
    "seam_position": "rear",
    "ironing_type": "topmost",
    "ironing_flow": "10%",
    "ironing_speed": "30",
    "ironing_spacing": "0.1",
    "nozzle_temperature": ["220", "220"],
    "nozzle_temperature_initial_layer": ["220", "220"],
    "textured_plate_temp": ["65", "65"],
    "textured_plate_temp_initial_layer": ["65", "65"],
    "elefant_foot_compensation": "0.1",
}

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


def mesh_xml(obj_id: int, verts: list, tris: list, mat_id: int,
             mat_index: int) -> str:
    vs = "".join(
        f'<vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts
    )
    ts = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris
    )
    return (
        f'<object id="{obj_id}" type="model" '
        f'pid="{mat_id}" pindex="{mat_index}">'
        f"<mesh><vertices>{vs}</vertices>"
        f"<triangles>{ts}</triangles></mesh></object>"
    )


def build() -> None:
    mat_id = len(STLS) + 2
    objects = []
    for i, (fname, _, _, _) in enumerate(STLS):
        verts, tris = parse_ascii_stl(HERE / fname)
        objects.append(mesh_xml(len(objects) + 1, verts, tris, mat_id, i))
        print(f"{fname}: {len(verts)} vertices, {len(tris)} triangles")

    materials = (
        f'<basematerials id="{mat_id}">'
        + "".join(
            f'<base name="{name}" displaycolor="{color}FF"/>'
            for _, name, _, color in STLS
        )
        + "</basematerials>"
    )
    identity = "1 0 0 0 1 0 0 0 1 0 0 0"
    assembly_id = len(objects) + 1
    components = "".join(
        f'<component objectid="{i + 1}" transform="{identity}"/>'
        for i in range(len(objects))
    )
    build_tf = f"1 0 0 0 1 0 0 0 1 {PLATE_XY} {PLATE_XY} 0"
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
        '<metadata name="Application">BambuStudio-02.00.03.54</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        '<metadata name="Title">PLJ Carpentry Keychain</metadata>'
        f"<resources>{materials}{''.join(objects)}"
        f'<object id="{assembly_id}" type="model">'
        f"<components>{components}</components></object>"
        "</resources>"
        f'<build><item objectid="{assembly_id}" '
        f'transform="{build_tf}" printable="1"/></build>'
        "</model>"
    )

    parts = "".join(
        f'<part id="{i + 1}" subtype="normal_part">'
        f'<metadata key="name" value="{name}"/>'
        f'<metadata key="extruder" value="{extruder}"/>'
        f'<metadata key="matrix" value="{identity}"/>'
        "</part>"
        for i, (_, name, extruder, _) in enumerate(STLS)
    )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<config>"
        f'<object id="{assembly_id}">'
        '<metadata key="name" value="PLJ_Carpentry_Keychain"/>'
        '<metadata key="extruder" value="1"/>'
        f"{parts}</object>"
        "<plate>"
        '<metadata key="plater_id" value="1"/>'
        '<metadata key="plater_name" value=""/>'
        '<metadata key="locked" value="false"/>'
        '<metadata key="thumbnail_file" value="Metadata/plate_1.png"/>'
        "<model_instance>"
        f'<metadata key="object_id" value="{assembly_id}"/>'
        '<metadata key="instance_id" value="0"/>'
        '<metadata key="identify_id" value="84"/>'
        "</model_instance>"
        "</plate>"
        "<assemble>"
        f'<assemble_item object_id="{assembly_id}" instance_id="0" '
        f'transform="{build_tf}" offset="0 0 0"/>'
        "</assemble>"
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
        '<Default Extension="png" ContentType="image/png"/>'
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
        '<Relationship Target="/Metadata/plate_1.png" Id="rel-2" '
        'Type="http://schemas.openxmlformats.org/package/2006/'
        'relationships/metadata/thumbnail"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr(
            "Metadata/project_settings.config",
            json.dumps(PROJECT_SETTINGS, indent=4),
        )
        thumb = HERE / "preview_top.png"
        if thumb.exists():
            z.write(thumb, "Metadata/plate_1.png")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
