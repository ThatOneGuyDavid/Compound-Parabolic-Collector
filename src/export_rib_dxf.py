#!/usr/bin/env python3
"""Export and round-trip check a nominal CNC profile from each delivered rib STEP."""
from pathlib import Path
import json
import ezdxf
from build123d import Compound, ExportDXF, Face, Plane, Vertex, Wire, import_dxf, import_step, section

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'models/v14'
reports = {}
for variant in ('printed', 'aluminum'):
    folder = OUT / variant
    config = json.loads((folder / 'validation.json').read_text())
    mid = config['rib_thickness_mm'] / 2
    solid = import_step(folder / 'rib-half.step')
    profile = section(solid, section_by=Plane.XY.offset(mid)).translate((0, 0, -mid))
    assert len(profile.faces()) == 1
    assert len(profile.faces()[0].inner_wires()) == 8
    exporter = ExportDXF()
    exporter.add_shape(profile)
    target = folder / 'rib-half.dxf'
    exporter.write(target)
    document = ezdxf.readfile(target)
    assert document.units == 4  # millimeters
    assert not document.audit().errors
    assert len(document.modelspace().query('CIRCLE')) == 8
    edges = import_dxf(target)
    wires = sorted(Wire.combine(edges), key=lambda w: w.length, reverse=True)
    assert len(wires) == 9 and all(w.is_closed for w in wires)
    recovered = Face(wires[0], wires[1:])
    assert recovered.is_valid
    area_error = abs(recovered.area - profile.area)
    assert area_error < .05
    original_edges = Compound(profile.edges())
    imported_edges = Compound(edges)
    error = max(target_edges.distance_to(Vertex(*edge.position_at(i / 32)))
                for source_edges, target_edges in ((profile.edges(), imported_edges), (edges, original_edges))
                for edge in source_edges for i in range(33))
    assert error < .01, error
    circles = sorted(entity.dxf.radius for entity in document.modelspace().query('CIRCLE'))
    expected = sorted([7.14375 / 2] * 3 + [4.7625 / 2] * 5)
    assert all(abs(a - b) < 1e-7 for a, b in zip(circles, expected))
    reports[variant] = dict(units='mm', closed_contours=9, holes=8,
        structural_hole_diameter_mm=7.14375, slat_hole_diameter_mm=4.7625,
        area_error_mm2=area_error, sampled_boundary_error_mm=error,
        method='Mid-thickness STEP section, translated to XY; DXF round-trip, 33 boundary samples per edge in both directions',
        cnc_notes='Nominal finished outline; no kerf/tool compensation or face edge-roundover machining instructions')
    print(f'PASS: {variant} DXF: 9 closed contours, 8 holes, sampled error {error:.6f} mm', flush=True)
(OUT / 'dxf-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
