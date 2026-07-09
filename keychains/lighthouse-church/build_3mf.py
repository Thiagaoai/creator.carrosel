#!/usr/bin/env python3
"""Build a Bambu Studio PROJECT .3mf from the two exported STLs.

Produces lighthouse_keychain.3mf with:
  * one object made of two parts (blue base + white relief)
  * part -> filament (extruder) assignment: 1 = blue, 2 = white
  * embedded model_settings.config and project_settings.config
    (Bambu Lab A1, 0.4 nozzle, Textured PEI, 0.20 mm, 3 walls,
    15% gyroid, no supports, no brim, back seam, topmost ironing,
    65 C bed, 0.1 mm elephant-foot compensation)
"""
from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

HERE = Path(__file__).parent

BLUE = "#0F4C9C"
WHITE = "#FFFFFF"


def read_binary_stl(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Read a binary STL and return deduplicated vertices + triangles."""
    data = path.read_bytes()
    (n_tri,) = struct.unpack_from("<I", data, 80)
    verts: list[tuple[float, float, float]] = []
    index: dict[tuple[float, float, float], int] = {}
    tris: list[tuple[int, int, int]] = []
    off = 84
    for _ in range(n_tri):
        vals = struct.unpack_from("<12f", data, off)
        tri = []
        for k in range(3):
            v = (
                round(vals[3 + 3 * k], 6),
                round(vals[4 + 3 * k], 6),
                round(vals[5 + 3 * k], 6),
            )
            i = index.get(v)
            if i is None:
                i = len(verts)
                index[v] = i
                verts.append(v)
            tri.append(i)
        tris.append(tuple(tri))
        off += 50
    return verts, tris


def mesh_xml(object_id: int, name: str, verts, tris) -> str:
    v_xml = "".join(
        f'<vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts
    )
    t_xml = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris
    )
    return (
        f'<object id="{object_id}" type="model">'
        f"<mesh><vertices>{v_xml}</vertices>"
        f"<triangles>{t_xml}</triangles></mesh></object>"
    )


def build() -> None:
    base_v, base_t = read_binary_stl(HERE / "base_blue.stl")
    rel_v, rel_t = read_binary_stl(HERE / "relief_white.stl")

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
        '<metadata name="Application">BambuStudio-01.10.01.50</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        '<metadata name="Title">lighthouse_church_keychain</metadata>'
        "<resources>"
        + mesh_xml(1, "base_blue", base_v, base_t)
        + mesh_xml(2, "relief_white", rel_v, rel_t)
        + '<object id="3" type="model"><components>'
        '<component objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        '<component objectid="2" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        "</components></object>"
        "</resources>"
        "<build>"
        '<item objectid="3" transform="1 0 0 0 1 0 0 0 1 128 128 0" printable="1"/>'
        "</build>"
        "</model>"
    )

    model_settings = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="3">
    <metadata key="name" value="lighthouse_church_keychain"/>
    <metadata key="extruder" value="1"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="base_blue"/>
      <metadata key="extruder" value="1"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
    </part>
    <part id="2" subtype="normal_part">
      <metadata key="name" value="relief_white"/>
      <metadata key="extruder" value="2"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <model_instance>
      <metadata key="object_id" value="3"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="463"/>
    </model_instance>
  </plate>
  <assemble>
   <assemble_item object_id="3" instance_id="0" transform="1 0 0 0 1 0 0 0 1 128 128 0" offset="0 0 0" />
  </assemble>
</config>
"""

    project_settings = {
        "printer_settings_id": "Bambu Lab A1 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL A1",
        "filament_settings_id": [
            "Bambu PLA Basic @BBL A1",
            "Bambu PLA Basic @BBL A1",
        ],
        "printer_model": "Bambu Lab A1",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "curr_bed_type": "Textured PEI Plate",
        "layer_height": "0.2",
        "initial_layer_print_height": "0.2",
        "wall_loops": "3",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "enable_support": "0",
        "brim_type": "no_brim",
        "seam_position": "back",
        "ironing_type": "topmost",
        "ironing_flow": "10%",
        "ironing_speed": "30",
        "ironing_spacing": "0.15",
        "elefant_foot_compensation": "0.1",
        "top_shell_layers": "4",
        "bottom_shell_layers": "3",
        "textured_plate_temp": ["65", "65"],
        "textured_plate_temp_initial_layer": ["65", "65"],
        "hot_plate_temp": ["65", "65"],
        "hot_plate_temp_initial_layer": ["65", "65"],
        "cool_plate_temp": ["65", "65"],
        "cool_plate_temp_initial_layer": ["65", "65"],
        "nozzle_temperature": ["220", "220"],
        "nozzle_temperature_initial_layer": ["220", "220"],
        "filament_type": ["PLA", "PLA"],
        "filament_colour": [BLUE, WHITE],
        "flush_volumes_matrix": ["0", "280", "280", "0"],
        "version": "01.10.01.50",
        "name": "lighthouse_church_keychain",
        "from": "project",
    }

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType='
        '"application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        "</Types>"
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1"'
        ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        "</Relationships>"
    )

    out = HERE / "lighthouse_keychain.3mf"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr(
            "Metadata/project_settings.config",
            json.dumps(project_settings, indent=4),
        )
        plate_png = HERE / "preview_top.png"
        if plate_png.exists():
            z.write(plate_png, "Metadata/plate_1.png")
            z.write(plate_png, "Metadata/plate_1_small.png")

    print(f"wrote {out} ({out.stat().st_size} bytes)")
    print(f"base: {len(base_v)} verts / {len(base_t)} tris")
    print(f"relief: {len(rel_v)} verts / {len(rel_t)} tris")


if __name__ == "__main__":
    build()
