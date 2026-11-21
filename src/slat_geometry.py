"""Tangent reflector support strips with round 90-degree end bends.

Dimensions in mm. u follows the rib tangent, v points into the rib material,
and z follows the pipe. The reflector support surface is v=0.
"""
import math
from functools import lru_cache
from build123d import Solid, Edge, Wire, Face, Plane
from shapely.geometry import Polygon, Point, LineString
import profile_geometry as p
import hardware_geometry as h

WIDTH=19.05
GAUGE=1.5875
INNER_RADIUS=1.5875
OUTER_RADIUS=INNER_RADIUS+GAUGE
TAB_DEPTH=19.05
HOLE_DEPTH=11.5
LOWER_ARC_DISTANCE=45.0
COLOR=(.78,.78,.70)
# Small slat hardware; original 1/4-20 pair bolts and rods are in hardware_geometry.
SLAT_DIAMETER=.164*25.4  # #8 nominal major diameter
SLAT_PITCH=25.4/32
SLAT_CLEARANCE=3/16*25.4
SLAT_SCREW_LENGTH=25.4
SLAT_HEAD_OD=.312*25.4
SLAT_HEAD_HEIGHT=.116*25.4
SLAT_NUT_AF=11/32*25.4
SLAT_NUT_HEIGHT=.130*25.4
SLAT_WASHER_OD=3/8*25.4
SLAT_WASHER_T=.032*25.4


def locations():
    lengths=[0.]
    for a,b in zip(p.edge,p.edge[1:]):lengths.append(lengths[-1]+math.dist(a,b))
    result=[]
    for j in range(5):
        distance=LOWER_ARC_DISTANCE+(lengths[-1]-WIDTH/2-LOWER_ARC_DISTANCE)*j/4
        i=min(range(len(lengths)),key=lambda k:abs(lengths[k]-distance))
        q=p.edge[i];a=p.edge[max(0,i-1)];b=p.edge[min(len(p.edge)-1,i+1)]
        dx,dy=b[0]-a[0],b[1]-a[1];ll=math.hypot(dx,dy)
        tangent=(dx/ll,dy/ll)
        if j==4:
            # Exact top edge at the lip; use its endpoint tangent.
            a,b=p.edge[-2:];dx,dy=b[0]-a[0],b[1]-a[1];ll=math.hypot(dx,dy)
            tangent=(dx/ll,dy/ll)
            q=(b[0]-WIDTH/2*tangent[0],b[1]-WIDTH/2*tangent[1])
        normal=(tangent[1],-tangent[0])
        hole=(q[0]+HOLE_DEPTH*normal[0],q[1]+HOLE_DEPTH*normal[1])
        result.append(dict(index=j+1,point=q,tangent=tangent,normal=normal,hole=hole,arc_distance=distance))
    return result


LAYOUT=locations()


def xy(row,u,v):
    q,t,n=row['point'],row['tangent'],row['normal']
    return (q[0]+u*t[0]+v*n[0],q[1]+u*t[1]+v*n[1])


def rib_cutters(thickness):
    cutters=[]
    for row in LAYOUT:
        corners=[(*xy(row,u,v),-.1) for u,v in
                 [(-WIDTH/2,-8),(WIDTH/2,-8),(WIDTH/2,0),(-WIDTH/2,0)]]
        cutters.append(Solid.extrude(Face(Wire.make_polygon(corners,close=True)),(0,0,thickness+.2)))
        x,y=row['hole']
        cutters.append(h.cylinder(SLAT_CLEARANCE/2,thickness+.2,x,y,-.1))
    return cutters


def strip(row,start,end):
    """Tab outer planes meet rib faces at start and end; material is in the bay."""
    r,ri=OUTER_RADIUS,INNER_RADIUS
    def point(z,v):return (*xy(row,-WIDTH/2,v),z)
    def line(a,b):return Edge.make_line(point(*a),point(*b))
    def arc(c,rad,a,b):
        return Edge.make_three_point_arc(*[point(c[0]+rad*math.cos(t),c[1]+rad*math.sin(t)) for t in (a,(a+b)/2,b)])
    edges=[line((start+r,0),(end-r,0)),
        arc((end-r,r),r,-math.pi/2,0),
        line((end,r),(end,TAB_DEPTH)),line((end,TAB_DEPTH),(end-GAUGE,TAB_DEPTH)),
        line((end-GAUGE,TAB_DEPTH),(end-GAUGE,r)),
        arc((end-r,r),ri,0,-math.pi/2),
        line((end-r,GAUGE),(start+r,GAUGE)),
        arc((start+r,r),ri,-math.pi/2,-math.pi),
        line((start+GAUGE,r),(start+GAUGE,TAB_DEPTH)),
        line((start+GAUGE,TAB_DEPTH),(start,TAB_DEPTH)),
        line((start,TAB_DEPTH),(start,r)),arc((start+r,r),r,math.pi,3*math.pi/2)]
    t=row['tangent']
    solid=Solid.extrude(Face(Wire(edges)),(WIDTH*t[0],WIDTH*t[1],0))
    x,y=row['hole']
    for z in [start-.01,end-GAUGE-.01]:
        solid=solid.cut(h.cylinder(SLAT_CLEARANCE/2,GAUGE+.02,x,y,z))
    assert solid.is_valid and len(solid.solids())==1
    assert abs(solid.bounding_box().min.Z-start)<1e-5
    assert abs(solid.bounding_box().max.Z-end)<1e-5
    return solid


def screw_length(thickness):
    return 25.4*5/8 if thickness==3.175 else SLAT_SCREW_LENGTH


@lru_cache(maxsize=2)
def small_screw(length=SLAT_SCREW_LENGTH):
    head=h.cylinder(SLAT_HEAD_OD/2,SLAT_HEAD_HEIGHT,z=-SLAT_HEAD_HEIGHT)
    top=[edge for edge in head.edges() if abs(edge.bounding_box().min.Z+SLAT_HEAD_HEIGHT)<1e-6
         and abs(edge.bounding_box().max.Z+SLAT_HEAD_HEIGHT)<1e-6]
    head=head.fillet(.5,top)
    # Cross recess in the outward-facing head, represented without helical threads.
    for slot_length,width in [(3.6,.75),(.75,3.6)]:
        recess=Solid.make_box(slot_length,width,.71,Plane(origin=(-slot_length/2,-width/2,-SLAT_HEAD_HEIGHT-.01)))
        head=head.cut(recess).clean()
    screw=head.fuse(h.cylinder(SLAT_DIAMETER/2,length)).clean()
    assert screw.is_valid and len(screw.solids())==1
    return screw


def small_nut(x,y,z):
    radius=SLAT_NUT_AF/math.sqrt(3)
    points=[(x+radius*math.cos(i*math.pi/3),y+radius*math.sin(i*math.pi/3),z) for i in range(6)]
    body=Solid.extrude(Face(Wire.make_polygon(points,close=True)),(0,0,SLAT_NUT_HEIGHT))
    return body.cut(h.cylinder((SLAT_DIAMETER+.25)/2,SLAT_NUT_HEIGHT,x,y,z))


def fastener(row,station,side,pitch,thickness,pair_thickness,stations):
    x,y=row['hole']
    if side=='left':x=-x
    base=station*pitch+(thickness if side=='left' else 0)
    front=base-(GAUGE if station>0 else 0)
    rear=base+thickness+(GAUGE if station<stations-1 else 0)
    bearing=front-SLAT_WASHER_T
    length=screw_length(thickness)
    screw=small_screw(length).translate((x,y,bearing))
    parts=[('screw',screw),
           ('front-washer',h.ring(SLAT_WASHER_OD,SLAT_CLEARANCE,SLAT_WASHER_T,x,y,front-SLAT_WASHER_T)),
           ('rear-washer',h.ring(SLAT_WASHER_OD,SLAT_CLEARANCE,SLAT_WASHER_T,x,y,rear)),
           ('nut',small_nut(x,y,rear+SLAT_WASHER_T))]
    assert bearing+length-(rear+SLAT_WASHER_T+SLAT_NUT_HEIGHT)>2*SLAT_PITCH
    return [dict(name=f'section-{station+1:02d}-{side}-slat-{row["index"]}-{name}',shape=shape,color=h.METAL) for name,shape in parts]


def make_slats(pitch,stations,thickness,pair_thickness):
    from build123d import Axis
    master_row=dict(point=(0.,0.),tangent=(1.,0.),normal=(0.,-1.),hole=(0.,-HOLE_DEPTH))
    master=strip(master_row,0.,pitch-thickness)
    master.label='reflector-slat-master'
    bays=[];paired={i:[] for i in range(stations)}
    for bay in range(stations-1):
        group=[]
        for row in LAYOUT:
            # Every occurrence is a rigid placement of this one master solid.
            angle=math.degrees(math.atan2(row['tangent'][1],row['tangent'][0]))
            right=master.rotate(Axis.Z,angle).translate((*row['point'],thickness))
            left=right.rotate(Axis.Y,180).translate((0,0,pitch+pair_thickness))
            # Rotation reverses Z, then translation restores the opposite bay.
            for side,shape in [('right',right),('left',left)]:
                assert abs(shape.volume-master.volume)<1e-4
                assert abs(shape.area-master.area)<1e-4
                group.append(dict(name=f'bay-{bay+1:02d}-{side}-slat-{row["index"]}',
                    shape=shape.translate((0,0,bay*pitch)),color=COLOR))
        bays.append(group)
    for station in range(stations):
        for side in ['right','left']:
            for row in LAYOUT:paired[station].extend(fastener(row,station,side,pitch,thickness,pair_thickness,stations))
    return bays,paired,master


def report(thickness=12.0):
    top=LAYOUT[-1];upper=xy(top,WIDTH/2,0)
    assert math.dist(upper,p.edge[-1])<1e-7
    normal_error=max(abs(sum(a*b for a,b in zip(row['tangent'],row['normal']))) for row in LAYOUT)
    return dict(unique_slat_designs=1,slat_instance_quantity=40,formed_overall_length_mm=363.0,slat_quantity=40,slats_per_side_per_bay=5,width_mm=WIDTH,thickness_mm=GAUGE,
        inner_bend_radius_mm=INNER_RADIUS,tab_depth_mm=TAB_DEPTH,hole_depth_mm=HOLE_DEPTH,
        lowest_arc_distance_mm=LOWER_ARC_DISTANCE,layout=LAYOUT,
        top_edge_error_mm=math.dist(upper,p.edge[-1]),tangent_normal_dot_error=normal_error,
        flat_support_plane='v=0, flush with tangent seats cut in rib edges',
        slat_fastener=f'#8-32 x {"5/8" if thickness==3.175 else "1"} inch pan-head machine screw, two small washers and nut; shared through-fastener at interior stations',
        fastener_thread='#8-32 UNC',slat_fastener_quantity=50,slat_washer_quantity=100,slat_nut_quantity=50,slat_hole_diameter_mm=SLAT_CLEARANCE,
        slat_washer_OD_mm=SLAT_WASHER_OD,slat_washer_thickness_mm=SLAT_WASHER_T,
        slat_screw_head_OD_mm=SLAT_HEAD_OD,slat_screw_length_mm=screw_length(thickness),slat_screw_length_label='5/8' if thickness==3.175 else '1',
        slat_joint_stacks=[dict(station=i+1,stack_mm=thickness+(GAUGE if i>0 else 0)+(GAUGE if i<4 else 0)+2*SLAT_WASHER_T+SLAT_NUT_HEIGHT,
            protrusion_mm=screw_length(thickness)-(thickness+(GAUGE if i>0 else 0)+(GAUGE if i<4 else 0)+2*SLAT_WASHER_T+SLAT_NUT_HEIGHT)) for i in range(5)],
        reflector_arc_per_side_mm=p.REFLECTOR_ARC_MM,acceptance_half_angle_deg=math.degrees(p.ANGLE),
        rib_back_envelope=back_envelope_report(),
        provisional='3/4 x 1/16 inch aluminum strip; dimensions for review, not final fabrication')


def seat_polygon():
    material=Polygon(p.outline)
    for row in LAYOUT:
        cutter=Polygon([xy(row,u,v) for u,v in [(-WIDTH/2,-8),(WIDTH/2,-8),(WIDTH/2,0),(-WIDTH/2,0)]])
        material=material.difference(cutter)
    if material.geom_type=='MultiPolygon':material=max(material.geoms,key=lambda g:g.area)
    assert material.is_valid
    return material


def back_envelope_report():
    material=seat_polygon()
    back=LineString([point for segment in p.segments[7:11] for point in p.segment_points(segment,240)])
    records=[]
    for row in LAYOUT:
        footprint=Polygon([xy(row,u,v) for u,v in [(-WIDTH/2,0),(WIDTH/2,0),(WIDTH/2,TAB_DEPTH),(-WIDTH/2,TAB_DEPTH)]])
        outside=footprint.difference(material).area
        assert outside<1e-5,(row['index'],outside)
        tail=LineString([xy(row,u,TAB_DEPTH) for u in (-WIDTH/2,WIDTH/2)])
        clearance=tail.distance(back)
        margin=clearance-p.EDGE_ROUNDOVER
        assert margin>(.1 if row['index']==5 else 1.8),(row['index'],margin)
        records.append(dict(row=row['index'],footprint_outside_rib_mm2=outside,
            tail_to_back_curve_mm=clearance,minimum_after_edge_roundover_mm=margin))
    return dict(rib_web_mm=p.WEB,slat_tail_depth_mm=TAB_DEPTH,rows=records,
        minimum_proud_mm=min(record['minimum_after_edge_roundover_mm'] for record in records),
        method='Entire slat/bend/tail projected footprint contained in seated rib; tail-to-smooth-back distance minus edge radius')
