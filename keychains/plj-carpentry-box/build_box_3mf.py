#!/usr/bin/env python3
"""Build the Bambu Studio PROJECT .3mf for the PLJ Carpentry gift box.

Two objects on one plate, both in print orientation:
  * box base  (1 part,  filament 1 = black)
  * box lid   (2 parts: black body -> filament 1,
               yellow logo inlay  -> filament 2)

Colors are ALSO embedded as 3MF core base materials bound to each
mesh, so they display correctly even on a plain geometry import.
"""
from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

HERE = Path(__file__).parent

BLACK = "#000000"
YELLOW = "#F0A500"


def read_binary_stl(path: Path):
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


def mesh_xml(object_id: int, verts, tris, pindex: int) -> str:
    v_xml = "".join(
        f'<vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts
    )
    t_xml = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris
    )
    return (
        f'<object id="{object_id}" type="model" pid="10" pindex="{pindex}">'
        f"<mesh><vertices>{v_xml}</vertices>"
        f"<triangles>{t_xml}</triangles></mesh></object>"
    )


def build() -> None:
    base_v, base_t = read_binary_stl(HERE / "base_black.stl")
    lidb_v, lidb_t = read_binary_stl(HERE / "lid_black.stl")
    lidy_v, lidy_t = read_binary_stl(HERE / "lid_logo_yellow.stl")

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
        '<metadata name="Application">BambuStudio-01.10.01.50</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        '<metadata name="Title">plj_carpentry_gift_box</metadata>'
        "<resources>"
        '<basematerials id="10">'
        f'<base name="PLA Black" displaycolor="{BLACK}FF"/>'
        f'<base name="PLA Yellow" displaycolor="{YELLOW}FF"/>'
        "</basematerials>"
        + mesh_xml(1, base_v, base_t, 0)
        + mesh_xml(2, lidb_v, lidb_t, 0)
        + mesh_xml(3, lidy_v, lidy_t, 1)
        + '<object id="4" type="model"><components>'
        '<component objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        "</components></object>"
        '<object id="5" type="model"><components>'
        '<component objectid="2" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        '<component objectid="3" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        "</components></object>"
        "</resources>"
        "<build>"
        '<item objectid="4" transform="1 0 0 0 1 0 0 0 1 88 128 0" printable="1"/>'
        '<item objectid="5" transform="1 0 0 0 1 0 0 0 1 168 128 0" printable="1"/>'
        "</build>"
        "</model>"
    )

    model_settings = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="4">
    <metadata key="name" value="box_base"/>
    <metadata key="extruder" value="1"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="base_black"/>
      <metadata key="extruder" value="1"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
    </part>
  </object>
  <object id="5">
    <metadata key="name" value="box_lid"/>
    <metadata key="extruder" value="1"/>
    <part id="2" subtype="normal_part">
      <metadata key="name" value="lid_black"/>
      <metadata key="extruder" value="1"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
    </part>
    <part id="3" subtype="normal_part">
      <metadata key="name" value="logo_yellow"/>
      <metadata key="extruder" value="2"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <model_instance>
      <metadata key="object_id" value="4"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="463"/>
    </model_instance>
    <model_instance>
      <metadata key="object_id" value="5"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="464"/>
    </model_instance>
  </plate>
  <assemble>
   <assemble_item object_id="4" instance_id="0" transform="1 0 0 0 1 0 0 0 1 88 128 0" offset="0 0 0" />
   <assemble_item object_id="5" instance_id="0" transform="1 0 0 0 1 0 0 0 1 168 128 0" offset="0 0 0" />
  </assemble>
</config>
"""

    project_settings = {
        "name": "plj_carpentry_gift_box",
        "from": "project",
        "version": "01.10.01.50",
        "is_custom_defined": "0",
        "printer_settings_id": "Bambu Lab A1 0.4 nozzle",
        "printer_model": "Bambu Lab A1",
        "printer_variant": "0.4",
        "printer_technology": "FFF",
        "gcode_flavor": "marlin",
        "nozzle_diameter": ["0.4"],
        "nozzle_type": "stainless_steel",
        "printable_height": "256",
        "curr_bed_type": "Textured PEI Plate",
        "print_settings_id": "0.20mm Standard @BBL A1",
        "layer_height": "0.2",
        "initial_layer_print_height": "0.2",
        "line_width": "0.42",
        "initial_layer_line_width": "0.5",
        "wall_loops": "3",
        "top_shell_layers": "4",
        "top_shell_thickness": "0.8",
        "bottom_shell_layers": "3",
        "bottom_shell_thickness": "0",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "enable_support": "0",
        "support_type": "normal(auto)",
        "brim_type": "no_brim",
        "brim_width": "5",
        "skirt_loops": "1",
        "seam_position": "back",
        "ironing_type": "topmost",
        "ironing_pattern": "zig-zag",
        "ironing_flow": "10%",
        "ironing_speed": "30",
        "ironing_spacing": "0.15",
        "elefant_foot_compensation": "0.1",
        "only_one_wall_first_layer": "1",
        "wall_sequence": "inner wall/outer wall",
        "detect_thin_wall": "1",
        "gap_infill_speed": "250",
        "outer_wall_speed": "200",
        "inner_wall_speed": "300",
        "top_surface_speed": "200",
        "initial_layer_speed": "50",
        "initial_layer_infill_speed": "105",
        "sparse_infill_speed": "270",
        "internal_solid_infill_speed": "250",
        "travel_speed": "700",
        "resolution": "0.012",
        "slice_closing_radius": "0.049",
        "xy_contour_compensation": "0",
        "xy_hole_compensation": "0",
        "enable_prime_tower": "1",
        "prime_tower_width": "25",
        "prime_tower_brim_width": "3",
        "prime_volume": "45",
        "flush_volumes_matrix": ["0", "280", "280", "0"],
        "flush_volumes_vector": ["140", "140"],
        "flush_multiplier": "1",
        "filament_settings_id": [
            "Bambu PLA Basic @BBL A1",
            "Bambu PLA Basic @BBL A1",
        ],
        "filament_type": ["PLA", "PLA"],
        "filament_vendor": ["Bambu Lab", "Bambu Lab"],
        "filament_colour": [BLACK, YELLOW],
        "filament_diameter": ["1.75", "1.75"],
        "filament_density": ["1.26", "1.26"],
        "filament_flow_ratio": ["0.98", "0.98"],
        "filament_max_volumetric_speed": ["21", "21"],
        "filament_cost": ["24.99", "24.99"],
        "filament_is_support": ["0", "0"],
        "filament_soluble": ["0", "0"],
        "filament_shrink": ["100%", "100%"],
        "temperature_vitrification": ["45", "45"],
        "nozzle_temperature": ["220", "220"],
        "nozzle_temperature_initial_layer": ["220", "220"],
        "nozzle_temperature_range_low": ["190", "190"],
        "nozzle_temperature_range_high": ["240", "240"],
        "fan_min_speed": ["60", "60"],
        "fan_max_speed": ["80", "80"],
        "close_fan_the_first_x_layers": ["1", "1"],
        "slow_down_layer_time": ["4", "4"],
        "slow_down_min_speed": ["20", "20"],
        "reduce_fan_stop_start_freq": ["1", "1"],
        "textured_plate_temp": ["65", "65"],
        "textured_plate_temp_initial_layer": ["65", "65"],
        "hot_plate_temp": ["65", "65"],
        "hot_plate_temp_initial_layer": ["65", "65"],
        "cool_plate_temp": ["65", "65"],
        "cool_plate_temp_initial_layer": ["65", "65"],
        "eng_plate_temp": ["65", "65"],
        "eng_plate_temp_initial_layer": ["65", "65"],
        "supertack_plate_temp": ["65", "65"],
        "supertack_plate_temp_initial_layer": ["65", "65"],
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

    out = HERE / "plj_gift_box.3mf"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr(
            "Metadata/project_settings.config",
            json.dumps(project_settings, indent=4),
        )
        thumb = HERE / "preview_lid.png"
        if thumb.exists():
            z.write(thumb, "Metadata/plate_1.png")
            z.write(thumb, "Metadata/plate_1_small.png")

    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
