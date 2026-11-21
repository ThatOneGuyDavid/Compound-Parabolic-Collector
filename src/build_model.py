#!/usr/bin/env python3
"""Build one reusable half-rib and a layout of five paired sections."""
from pathlib import Path
import argparse
import copy
import json
import math
import os

os.environ.setdefault('XDG_CACHE_HOME', '/tmp/cpc-cad-cache')
import numpy as np
import trimesh as tm
from build123d import (
    Axis, Color, Compound, Edge, Face, Plane, Solid, Wire,
    export_step, export_stl, import_step,
)
import profile_geometry as p
from hardware_geometry import make_hardware
import slat_geometry as slats

ROOT = Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description='Build one fixed rib material variant')
parser.add_argument('--variant',choices=('printed','aluminum'),default='printed')
VARIANT=parser.parse_args().variant
OUT=ROOT/'models'/'v16'/VARIANT
OUT.mkdir(parents=True,exist_ok=True)
STATIONS=5
THICKNESS=12.0 if VARIANT=='printed' else 3.175
PAIR_THICKNESS=2*THICKNESS
SLAT_LENGTH=363.0
PITCH=SLAT_LENGTH+THICKNESS
LENGTH=(STATIONS-1)*PITCH+PAIR_THICKNESS
PIPE_LENGTH=72*25.4
OVERHANG=(PIPE_LENGTH-LENGTH)/2
PIPE_INNER_RADIUS=13.30
RIGHT_COLOR=(.20,.46,.55) if VARIANT=='printed' else (.76,.79,.82)
LEFT_COLOR=(.73,.45,.24) if VARIANT=='printed' else (.38,.46,.53)


def xyz(q):
    return (float(q[0]),float(q[1]),0)


def spline(points):
    return Edge.make_spline([xyz(q) for q in points],tol=1e-7)


def resample(points,n=100):
    return [points[round(i*(len(points)-1)/n)] for i in range(n+1)]


def profile_face():
    edges=[]
    for segment in p.segments:
        kind=segment['kind']
        if kind=='line':
            edges.append(Edge.make_line(*[xyz(q) for q in segment['points']]))
        elif kind=='arc':
            center,r,a,b=segment['center'],segment['radius'],segment['start'],segment['end']
            edges.append(Edge.make_three_point_arc(xyz(p.arc_point(center,r,a)),
                xyz(p.arc_point(center,r,(a+b)/2)),xyz(p.arc_point(center,r,b))))
        elif kind=='bezier':
            edges.append(Edge.make_bezier(*[xyz(q) for q in segment['points']]))
        elif kind=='spline':
            edges.append(spline(resample(segment['points'],min(len(segment['points'])-1,120))))
        else:raise ValueError(kind)
    holes=[Wire.make_circle(p.HOLE_RADIUS,Plane(origin=(x,y,0))) for x,y in p.HOLES]
    face=Face(Wire(edges),holes)
    assert face.is_valid
    return face


def mesh(shape,tolerance=.035,angular=.06):
    vertices,triangles=shape.tessellate(tolerance,angular)
    result=tm.Trimesh(np.array([tuple(v) for v in vertices]),np.array(triangles),process=True)
    result.merge_vertices()
    result.fix_normals()
    assert result.is_watertight and result.volume>0
    return result


def cylinder(radius,length,x=0,y=0,z=0):
    return Solid.make_cylinder(radius,length,Plane(origin=(x,y,z)))


print('Building the reusable half-rib...',flush=True)
face=profile_face()
base=Solid.extrude(face,(0,0,THICKNESS))
# Round only nonfunctional front/back perimeter edges. Pipe bore, bolt
# holes and the reflective support curves keep their nominal geometry.
cosmetic_segments=[p.segments[i] for i in [7,8,9,10,11,12]]
guide=np.array([q for segment in cosmetic_segments for q in p.segment_points(segment,400)])
round_edges=[]
for e in base.edges():
    b=e.bounding_box()
    if b.size.Z>1e-6:continue
    v=e.position_at(.5)
    if np.min(np.linalg.norm(guide-np.array([v.X,v.Y]),axis=1))<.5:
        round_edges.append(e)
assert round_edges
print(f'Rounding {len(round_edges)} exposed perimeter edges...',flush=True)
half=base.fillet(p.EDGE_ROUNDOVER,round_edges)
print('Cutting tangent seats and slat attachment holes...',flush=True)
for cutter in slats.rib_cutters(THICKNESS):
    half=half.cut(cutter).clean()
assert half.is_valid and len(half.solids())==1
# Rotation flips the reusable part in X and Z. Translation puts the
# flipped full-thickness half immediately behind its partner along the pipe.
left=half.rotate(Axis.Y,180).translate((0,0,PAIR_THICKNESS))
assert abs(half.bounding_box().min.Z)<1e-6
assert abs(half.bounding_box().max.Z-THICKNESS)<1e-6
assert abs(left.bounding_box().min.Z-THICKNESS)<1e-6
assert abs(left.bounding_box().max.Z-PAIR_THICKNESS)<1e-6
pair_intersection=half & left
pair_overlap=0 if pair_intersection is None else pair_intersection.volume
assert pair_overlap<1e-5, pair_overlap
assert abs(half.bounding_box().size.Z-THICKNESS)<1e-5

half.label='rib-half'
half.color=Color(*RIGHT_COLOR)
export_step(half,OUT/'rib-half.step')
bounds=half.bounding_box()
print_half=half.translate((-bounds.min.X,-bounds.min.Y,-bounds.min.Z))
export_stl(print_half,OUT/'rib-half.stl',tolerance=.025,angular_tolerance=.08)


# The approved connector concept uses two outer all-thread rods and PVC sleeves.
pipe=cylinder(p.R,LENGTH+2*OVERHANG,z=-OVERHANG).cut(
    cylinder(PIPE_INNER_RADIUS,LENGTH+2*OVERHANG,z=-OVERHANG))
assert pipe.is_valid
pair_pipe=Compound([half,left]) & pipe
assert pair_pipe is None or pair_pipe.volume<1e-5
parts=[]
scene=tm.Scene()
export_parts=[]
section_assemblies=[]
paired_hardware,connecting_hardware,hardware_report=make_hardware(
    LENGTH,PITCH,STATIONS,THICKNESS,PAIR_THICKNESS,p.HOLE_Y)
print('Building folded slats and attachment hardware...',flush=True)
slat_bays,slat_hardware,slat_master=slats.make_slats(PITCH,STATIONS,THICKNESS,PAIR_THICKNESS)
slat_report=slats.report(THICKNESS)


def add(name,shape,category,color,station=None,metadata=None):
    shape=copy.copy(shape)
    shape.label=name
    shape.color=Color(*color)
    assert shape.is_valid
    m=mesh(shape,.12,.2) if category=='pair-hardware' and name.endswith('-screw') else mesh(shape)
    m.visual.vertex_colors=np.tile([round(c*255) for c in color]+[255],(len(m.vertices),1))
    parent=f'rib-section-{station+1:02d}' if station is not None else (f'slat-bay-{metadata["bay"]+1:02d}' if category=='slats' else ('connecting-hardware' if category=='connecting' else scene.graph.base_frame))
    scene.add_geometry(m,node_name=name,geom_name=name,parent_node_name=parent)
    export_parts.append(shape)
    parts.append(dict(name=name,category=category,color=color,station=station,
                      vertices=m.vertices.tolist(),faces=m.faces.tolist(),
                      metadata=metadata or {}))


# A section is a persistent pair in STEP, GLB and the browser layer tree.
pair_right=copy.copy(half); pair_right.label='half-A';pair_right.color=Color(*RIGHT_COLOR)
pair_left=copy.copy(left); pair_left.label='half-A-flipped';pair_left.color=Color(*LEFT_COLOR)
export_step(Compound(label='bolted-rib-section',children=[pair_right,pair_left]+
    [copy.copy(item['shape']) for item in paired_hardware[0]+slat_hardware[0]]),OUT/'rib-section.step')
for i in range(STATIONS):
    z=i*PITCH
    scene.graph.update(frame_to=f'rib-section-{i+1:02d}',frame_from=scene.graph.base_frame,matrix=np.eye(4))
    start=len(export_parts)
    add(f'rib-{i+1:02d}-right',half.translate((0,0,z)),'ribs',RIGHT_COLOR,i)
    add(f'rib-{i+1:02d}-left',left.translate((0,0,z)),'ribs',LEFT_COLOR,i)
    for item in paired_hardware[i]+slat_hardware[i]:
        add(item['name'],item['shape'],'pair-hardware',item['color'],i)
    section_assemblies.append(Compound(label=f'bolted-rib-section-{i+1:02d}',children=export_parts[start:]))
scene.graph.update(frame_to='connecting-hardware',frame_from=scene.graph.base_frame,matrix=np.eye(4))
connection_start=len(export_parts)
for item in connecting_hardware:
    import re
    match=re.search(r'spacer-(\d+)',item['name'])
    meta={'bay':int(match.group(1))-1} if match else {}
    add(item['name'],item['shape'],'connecting',item['color'],metadata=meta)
connector_assembly=Compound(label='all-thread-PVC-spacers-and-locknuts',children=export_parts[connection_start:])
slat_start=len(export_parts)
slat_bay_assemblies=[]
for bay,items in enumerate(slat_bays):
    scene.graph.update(frame_to=f'slat-bay-{bay+1:02d}',frame_from=scene.graph.base_frame,matrix=np.eye(4))
    start=len(export_parts)
    for item in items:add(item['name'],item['shape'],'slats',item['color'],metadata={'bay':bay})
    slat_bay_assemblies.append(Compound(label=f'reflector-slat-bay-{bay+1:02d}',children=export_parts[start:]))
slat_assembly=Compound(label='reflector-support-slats',children=slat_bay_assemblies)
export_step(Compound(label='reflector-slat-bay',children=[copy.copy(item['shape']) for item in slat_bays[0]]),OUT/'slat-bay.step')
export_step(slat_master,OUT/'reflector-slat.step')
export_stl(slat_master,OUT/'reflector-slat.stl',tolerance=.03,angular_tolerance=.1)
add('receiver-pipe',pipe,'pipe',(.19,.20,.22))
assembly=Compound(label='CPC backbone with prototype PVC spacers',children=section_assemblies+[connector_assembly,slat_assembly,export_parts[-1]])
print('Exporting assembly STEP and GLB...',flush=True)
export_step(assembly,OUT/'backbone.step')
glb_scene=scene.copy()
glb_scene.apply_scale(.001)  # glTF uses meters; native CAD and viewer input use mm.
glb_scene.units='m'
glb_scene.export(OUT/'backbone.glb')
(OUT/'viewer-parts.json').write_text(json.dumps(parts,separators=(',',':')))

# STEP reimport checks the delivered solids rather than only in-memory objects.
reimported=import_step(OUT/'rib-half.step')
assert reimported.is_valid and len(reimported.solids())==1
stl=tm.load_mesh(OUT/'rib-half.stl')
assert stl.is_watertight and stl.volume>0
assert stl.euler_number==2-2*(len(p.HOLES)+len(slats.LAYOUT))
assert np.max(stl.extents[:2])<420
assert abs(stl.bounds[0,2])<1e-5
assert np.min(stl.bounds[0,:2])>=-1e-5
rib_min=min(s.bounding_box().min.Z for s in export_parts if s.label.startswith('rib-'))
rib_max=max(s.bounding_box().max.Z for s in export_parts if s.label.startswith('rib-'))
assert abs(rib_min)<1e-6 and abs(rib_max-LENGTH)<1e-6
assert abs(pipe.bounding_box().min.Z+OVERHANG)<1e-6
assert abs(pipe.bounding_box().max.Z-(LENGTH+OVERHANG))<1e-6
delivered=import_step(OUT/'backbone.step')
assert delivered.is_valid and len(delivered.solids())==len(parts)
assert len(delivered.children)==STATIONS+3
assert sorted(len(s.solids()) for s in delivered.children)==sorted([1,len(connecting_hardware),40]+[50]*STATIONS)
delivered_section=import_step(OUT/'rib-section.step')
assert delivered_section.is_valid and len(delivered_section.solids())==50
assert abs(delivered.bounding_box().min.Z+OVERHANG)<1e-6
assert abs(delivered.bounding_box().max.Z-(LENGTH+OVERHANG))<1e-6

# Check axial hardware sections against a conservatively buffered rib envelope.
from check_hardware_geometry import check_clearances
print('Checking hardware clearances...',flush=True)
clearance_checks=check_clearances(p,paired_hardware,connecting_hardware,PITCH,THICKNESS,PAIR_THICKNESS)
hardware_report['rib_and_receiver_interference_checks']=clearance_checks
hardware_report['clearance_method']='Axial slices against unfilleted rib material buffered 0.02 mm; nominal fastener envelopes'
(OUT/'hardware.json').write_text(json.dumps(hardware_report,indent=2)+'\n')
(OUT/'slats.json').write_text(json.dumps(slat_report,indent=2)+'\n')
report=dict(
    revision='model-v16',variant=VARIANT,material='Printed prototype' if VARIANT=='printed' else 'CNC aluminum, fixed 1/8 inch plate',units='mm',glb_units='m',rib_stations=STATIONS,identical_half_quantity=2*STATIONS,
    backbone_length_mm=LENGTH,pipe_length_mm=LENGTH+2*OVERHANG,pipe_overhang_each_mm=OVERHANG,
    station_starts_mm=[i*PITCH for i in range(STATIONS)],station_pitch_mm=PITCH,
    rib_thickness_mm=THICKNESS,pair_thickness_mm=PAIR_THICKNESS,half_offset_mm=THICKNESS,
    station_half_intervals_mm=[[[i*PITCH,i*PITCH+THICKNESS],
                                [i*PITCH+THICKNESS,i*PITCH+PAIR_THICKNESS]] for i in range(STATIONS)],
    reflector_arc_per_side_mm=p.REFLECTOR_ARC_MM,reflector_arc_start='R6 fillet tangency B on reflector',
    reflector_arc_start_mm=p.FILLET_REFLECTOR_TANGENCY,previous_B_to_top_arc_mm=p.ARC_TO_OLD_TOP_MM,
    removed_lower_arc_mm=p.REMOVED_LOWER_ARC_MM,
    cradle_reflector_radius_mm=p.CRADLE_FILLET_RADIUS,acceptance_half_angle_deg=math.degrees(p.ANGLE),
    pipe_od_mm=2*p.R,pipe_id_mm=2*PIPE_INNER_RADIUS,cradle_bore_mm=2*p.CRADLE,
    cradle_wall_mm=p.CRADLE_WALL,part_bounds_mm=list(stl.extents),
    mounting_hole_diameter_mm=2*p.HOLE_RADIUS,mounting_hole_spacing_mm=30,
    hole_centers_per_half_mm=p.HOLES,gusset_hole_center_mm=p.GUSSET_HOLE,
    gusset_hole_outer_edge_margin_mm=p.GUSSET_BOSS_RADIUS-p.HOLE_RADIUS,
    reflection_relief=p.REFLECTION_RELIEF,rib_side_radius_mm=p.GUSSET_BOSS_RADIUS,pad_end_radius_mm=p.PAD_END_RADIUS,pad_end_center_mm=p.PAD_END_CENTER,
    outside_tip_radius_mm=p.TIP_RADIUS,exposed_edge_roundover_mm=p.EDGE_ROUNDOVER,rounded_edges=len(round_edges),
    paired_subassembly_count=STATIONS,connecting_structure='Two 1/4-20 all-thread rods with 1/2 inch nominal PVC spacers',
    bolting_hardware=f"Two 1/4-20 x {hardware_report['bolt_length_label']} inch bolts per section, washers and nuts",hardware=hardware_report,slats=slat_report,
    parts=len(parts),half_pair_overlap_mm3=pair_overlap,
    checks=['All native solids valid','Rib-half STEP reimports as one solid',
            'Print STL watertight, positive volume and on Z0','STL topology confirms three pad holes and five slat holes per half',
            'Print footprint fits 420 mm bed',
            'Full-thickness halves occupy adjacent axial intervals; no volumetric interference','Pipe clears assembled paired ribs',
            'Rib layout span and pipe overhangs match requested lengths',
            'Assembly STEP reimports with five bolted sections, grouped connectors and pipe',
            'Paired-section STEP reimports as two ribs plus 48 fastening components'],
    provisional=[f'{THICKNESS:g} mm fixed rib thickness','8 mm cradle wall','3/4 x 1/16 inch aluminum slats, 1/16 inch inner bend radius',
                 'Pipe ID is illustrative',
                 'Hardware envelopes and PVC dimensions provisional; no helical threads, physical fit or load test; end supports and pipe retention remain undecided'])
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('rib_stations','identical_half_quantity',
    'backbone_length_mm','pipe_length_mm','pipe_overhang_each_mm','part_bounds_mm','parts')},indent=2))
