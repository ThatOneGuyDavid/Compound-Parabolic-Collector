"""Provisional imperial hardware envelopes; millimeters, axes along CAD Z.

Threads are represented by nominal cylinders and clearance bores, not helices.
Dimensions are review envelopes, to be checked against purchased hardware.
"""
import math
from build123d import Solid, Wire, Face, Plane

INCH=25.4
DIAMETER=INCH/4
PITCH=INCH/20
CLEARANCE=INCH*9/32
AF=INCH*7/16
HEAD_HEIGHT=INCH*5/32
NUT_HEIGHT=INCH*7/32
LOCK_HEIGHT=INCH*5/16
BOLT_LENGTH=INCH*1.5
WASHER_OD=INCH*5/8
WIDE_OD=INCH
WASHER_T=INCH/16
PVC_OD=21.336
PVC_ID=15.7988
ROD_LENGTH=INCH*61
METAL=(.62,.65,.68)
PVC=(.90,.90,.85)
NYLON=(.15,.35,.65)


def cylinder(r,h,x=0,y=0,z=0):
    return Solid.make_cylinder(r,h,Plane(origin=(x,y,z)))


def ring(od,id,h,x,y,z):
    return cylinder(od/2,h,x,y,z).cut(cylinder(id/2,h,x,y,z))


def hexagon(h,x,y,z):
    r=AF/math.sqrt(3)
    points=[(x+r*math.cos(i*math.pi/3),y+r*math.sin(i*math.pi/3),z) for i in range(6)]
    return Solid.extrude(Face(Wire.make_polygon(points,close=True)),(0,0,h))


def bolt(x,y,bearing,length=BOLT_LENGTH):
    return hexagon(HEAD_HEIGHT,x,y,bearing-HEAD_HEIGHT).fuse(
        cylinder(DIAMETER/2,length,x,y,bearing))


def nut(x,y,z):
    return hexagon(NUT_HEIGHT,x,y,z).cut(cylinder((DIAMETER+.2)/2,NUT_HEIGHT,x,y,z))


def locknut(x,y,z,reverse=False):
    # Hexagonal metal base, raised locking collar, and separately colored insert.
    collar_h=3.0
    body=hexagon(LOCK_HEIGHT-collar_h,x,y,z).fuse(
        cylinder(AF*.46,collar_h,x,y,z+LOCK_HEIGHT-collar_h))
    body=body.cut(cylinder((DIAMETER+.2)/2,LOCK_HEIGHT,x,y,z))
    body=body.cut(cylinder(AF*.38,1.2,x,y,z+LOCK_HEIGHT-1.2))
    insert=ring(AF*.76,DIAMETER+.2,1.2,x,y,z+LOCK_HEIGHT-1.2)
    if reverse:
        from build123d import Axis
        axis=Axis((x,y,z+LOCK_HEIGHT/2),(1,0,0))
        body=body.rotate(axis,180);insert=insert.rotate(axis,180)
    return body,insert


def make_hardware(length,pitch,stations,thickness,pair_thickness,hole_y):
    bolt_length=INCH*.75 if thickness==3.175 else BOLT_LENGTH
    bolt_label='3/4' if thickness==3.175 else '1-1/2'
    stack=pair_thickness+2*WASHER_T+NUT_HEIGHT
    protrusion=bolt_length-stack
    assert protrusion>=2*PITCH
    paired={i:[] for i in range(stations)}
    connecting=[]
    def item(name,shape,color=METAL):
        assert shape.is_valid and len(shape.solids())==1,name
        return dict(name=name,shape=shape,color=color)
    for i in range(stations):
        z=i*pitch
        for j,x in enumerate((-15.,15.)):
            tag=f'section-{i+1:02d}-bolt-{j+1}'
            paired[i].extend([
                item(tag,bolt(x,hole_y,z-WASHER_T,bolt_length)),
                item(tag+'-front-washer',ring(WASHER_OD,CLEARANCE,WASHER_T,x,hole_y,z-WASHER_T)),
                item(tag+'-rear-washer',ring(WASHER_OD,CLEARANCE,WASHER_T,x,hole_y,z+pair_thickness)),
                item(tag+'-nut',nut(x,hole_y,z+pair_thickness+WASHER_T)),
            ])
    spacer_length=pitch-thickness-2*WASHER_T
    rod_start=(length-ROD_LENGTH)/2
    spacer_records=[]
    for row,x,offset in [('right',45.,0.),('left',-45.,thickness)]:
        connecting.append(item(row+'-all-thread-1-4-20',cylinder(DIAMETER/2,ROD_LENGTH,x,hole_y,rod_start)))
        for i in range(stations-1):
            a=i*pitch+offset+thickness
            b=(i+1)*pitch+offset
            tube=ring(PVC_OD,PVC_ID,spacer_length,x,hole_y,a+WASHER_T)
            connecting.extend([
                item(f'{row}-spacer-{i+1}-front-washer',ring(WIDE_OD,CLEARANCE,WASHER_T,x,hole_y,a)),
                item(f'{row}-PVC-spacer-{i+1}',tube,PVC),
                item(f'{row}-spacer-{i+1}-rear-washer',ring(WIDE_OD,CLEARANCE,WASHER_T,x,hole_y,b-WASHER_T)),
            ])
            assert abs(a+2*WASHER_T+spacer_length-b)<1e-8
            spacer_records.append(dict(row=row,bay=i+1,start=a+WASHER_T,end=b-WASHER_T,length=spacer_length))
        first=offset
        last=(stations-1)*pitch+offset+thickness
        for end,washer_z,nut_z,reverse in [
            ('front',first-WASHER_T,first-WASHER_T-LOCK_HEIGHT,True),
            ('rear',last,last+WASHER_T,False),
        ]:
            connecting.append(item(f'{row}-{end}-end-washer',ring(WIDE_OD,CLEARANCE,WASHER_T,x,hole_y,washer_z)))
            body,insert=locknut(x,hole_y,nut_z,reverse)
            connecting.append(item(f'{row}-{end}-lock-nut',body))
            connecting.append(item(f'{row}-{end}-nylon-insert',insert,NYLON))
            assert nut_z-rod_start>=2*PITCH-1e-7
            assert rod_start+ROD_LENGTH-(nut_z+LOCK_HEIGHT)>=2*PITCH-1e-7
    data=dict(thread='1/4-20 UNC',thread_diameter_mm=DIAMETER,thread_pitch_mm=PITCH,
        clearance_hole_mm=CLEARANCE,bolt_length_mm=bolt_length,bolt_length_label=bolt_label,bolt_stack_mm=stack,bolt_protrusion_mm=protrusion,bolt_exposed_threads=protrusion/PITCH,rod_length_mm=ROD_LENGTH,
        rod_start_mm=rod_start,spacer_length_mm=spacer_length,spacer_OD_mm=PVC_OD,spacer_ID_mm=PVC_ID,
        washer_thickness_mm=WASHER_T,spacer_washer_OD_mm=WIDE_OD,spacers=spacer_records,
        bom=[dict(item=f'1/4-20 x {bolt_label} inch hex bolt',quantity=10),
             dict(item='1/4-20 hex nut',quantity=10),
             dict(item='1/4 inch flat washer, 5/8 inch OD',quantity=20),
             dict(item='1/4-20 all-thread, 61 inch length',quantity=2),
             dict(item='1/2 inch nominal Schedule 40 PVC spacer',quantity=8,cut_length_mm=spacer_length),
             dict(item='1/4 inch fender washer, 1 inch OD',quantity=20),
             dict(item='1/4-20 nylon-insert lock nut',quantity=4)],
        thread_representation='Nominal envelopes; helical threads omitted',
        dimensions='Provisional envelopes; measure purchased washers and PVC before cutting spacers')
    return paired,connecting,data
