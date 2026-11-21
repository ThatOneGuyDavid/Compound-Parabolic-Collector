#!/usr/bin/env python3
"""Draw the current CPC concept; creates only rib.svg and its PNG preview."""
from pathlib import Path
import math
import subprocess
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
from profile_geometry import (
    R, ANGLE, CRADLE, CRADLE_WALL, COLLAR, WEB, END, JOIN, REFLECTOR_START,
    point, curve, edge, lower, back, inner, outer, outline, kept,
    PAD_HALF, PAD_BOTTOM, HOLE_Y, HOLES, HOLE_RADIUS, width, height,
)

# Model v9 adds tangent seats and slat attachment holes to the rib only.
import slat_geometry as slats
outline=list(slats.seat_polygon().exterior.coords)
HOLES=HOLES+[row['hole'] for row in slats.LAYOUT]

# Trace the complete reflective skin between rib stations. The mounting
# pad and local cradle are projected into this view but are not reflectors.
def cross(a,b):
    return a[0]*b[1]-a[1]*b[0]

SOURCE=(0.0,point(END)[1]+5)  # Fixed source shown at the start of the user's red line.
optical=curve(REFLECTOR_START,END,6000)
walls=[]
for sign in (-1,1):
    for p,q in zip(optical,optical[1:]):
        a=(sign*p[0],p[1]); b=(sign*q[0],q[1])
        walls.append((a,(b[0]-a[0],b[1]-a[1])))

def circle_distance(origin,direction):
    od=sum(a*b for a,b in zip(origin,direction))
    disc=od*od-(sum(a*a for a in origin)-R*R)
    if disc < 0:
        return math.inf
    roots=[t for t in (-od-math.sqrt(disc),-od+math.sqrt(disc)) if t>1e-7]
    return min(roots,default=math.inf)

def wall_before(origin,direction,limit):
    for a,v in walls:
        denominator=cross(direction,v)
        if abs(denominator)<1e-12:continue
        offset=(a[0]-origin[0],a[1]-origin[1])
        t=cross(offset,v)/denominator
        u=cross(offset,direction)/denominator
        if 1e-4<t<limit-1e-4 and 0<=u<=1:
            return True
    return False

def single_bounce(degrees):
    theta=math.radians(degrees)
    direction=(math.sin(theta),-math.cos(theta))
    origin=SOURCE
    distance=math.inf
    tangent=None
    for a,v in walls:
        denominator=cross(direction,v)
        if abs(denominator)<1e-12:continue
        offset=(a[0]-origin[0],a[1]-origin[1])
        t=cross(offset,v)/denominator
        u=cross(offset,direction)/denominator
        if 1e-7<t<distance and 0<=u<=1:
            distance,tangent=t,v
    if tangent is None or circle_distance(origin,direction)<distance:
        return None  # Direct pipe hit is not a reflection point.
    hit=(origin[0]+distance*direction[0],origin[1]+distance*direction[1])
    if hit[0]<0:return None
    length=math.hypot(*tangent)
    normal=(-tangent[1]/length,tangent[0]/length)
    dot=sum(a*b for a,b in zip(direction,normal))
    reflected=(direction[0]-2*dot*normal[0],direction[1]-2*dot*normal[1])
    target=circle_distance(hit,reflected)
    if not math.isfinite(target) or wall_before(hit,reflected,target):
        return None  # No second reflection allowed.
    end=(hit[0]+target*reflected[0],hit[1]+target*reflected[1])
    assert abs(math.hypot(*end)-R)<1e-6
    assert abs(sum(v*v for v in reflected)-1)<1e-10
    return [origin,hit,end]

# Start with the lower reflection indicated by the red sketch, then spread
# five rays evenly to a near-top trace inside the current acceptance range.
RED_REFLECTION=point(2.3)
LOW_RAY_ANGLE=math.degrees(math.atan2(RED_REFLECTION[0],SOURCE[1]-RED_REFLECTION[1]))
HIGH_RAY_ANGLE=math.degrees(ANGLE)-1.0
RAY_ANGLES=[LOW_RAY_ANGLE+(HIGH_RAY_ANGLE-LOW_RAY_ANGLE)*i/4 for i in range(5)]
RAYS=[single_bounce(a) for a in RAY_ANGLES]
assert all(path is not None and len(path)==3 for path in RAYS)
assert all(path[0]==SOURCE for path in RAYS)
assert len(set(path[1] for path in RAYS))==5

items = ['<svg xmlns="http://www.w3.org/2000/svg" width="760mm" height="480mm" viewBox="0 0 760 480">',
'<rect width="760" height="480" fill="white"/>',
'<defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e4ebee" stroke-width=".25"/></pattern></defs>',
'<g font-family="sans-serif" fill="#263740">']

def text(x,y,label,size=5,color='#263740',anchor='start'):
    items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{escape(label)}</text>')

def line(points,color='#627783',width=.5,dash=''):
    d='M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y in points)
    items.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')

def drawing(ox,oy,scale):
    def xy(p):return ox+scale*p[0],oy-scale*p[1]
    for sign,fill,stroke in [(1,'#74b0c4','#216e89'),(-1,'#dda778','#aa6835')]:
        def transform(p):return xy((sign*p[0],p[1]))
        def coords(p):
            x,y=transform(p);return f'{x:.3f},{y:.3f}'
        shape='M '+' L '.join(coords(p) for p in outline)
        shape+=' Z'
        items.append(f'<path d="{shape}" fill="{fill}" fill-opacity=".42" stroke="{stroke}" stroke-width=".65"/>')
        line([transform(p) for p in edge],stroke,.4,'1 .8')
        line([transform(p) for p in lower],stroke,.65,'2 1.5')
    items.append(f'<circle cx="{ox}" cy="{oy}" r="{R*scale}" fill="white" fill-opacity=".8" stroke="#36574d" stroke-width=".5" stroke-dasharray="2 1.5"/>')
    line([(ox-4,oy),(ox+4,oy)],'#36574d')
    line([(ox,oy-4),(ox,oy+4)],'#36574d')
    pad_holes=HOLES[:3]
    hole_specs=[(point,HOLE_RADIUS) for point in pad_holes]+[(row['hole'],slats.SLAT_CLEARANCE/2) for row in slats.LAYOUT]
    all_holes=set((sign*point[0],point[1],radius) for point,radius in hole_specs for sign in (-1,1))
    for hx,hy,radius in sorted(all_holes):
        x,y=xy((hx,hy))
        items.append(f'<circle cx="{x}" cy="{y}" r="{radius*scale}" fill="white" stroke="#263740" stroke-width=".6"/>')
        line([(x-2,y),(x+2,y)],'#627783',.3)
        line([(x,y-2),(x,y+2)],'#627783',.3)
    return xy

RAY_COLORS=['#25804f','#91456f','#a07312','#405da7','#b44c3b']
def ray_overlay(xy,labels=False):
    for index,(degrees,path,color) in enumerate(zip(RAY_ANGLES,RAYS,RAY_COLORS),1):
        line([xy(p) for p in path],color,.75)
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            length=math.hypot(dx,dy)
            if length<.2:continue
            ux,uy=dx/length,dy/length
            q=(a[0]+.6*dx,a[1]+.6*dy)
            arrow=min(2.3,length*.17)
            line([xy((q[0]-arrow*ux+.5*arrow*uy,q[1]-arrow*uy-.5*arrow*ux)),xy(q),
                  xy((q[0]-arrow*ux-.5*arrow*uy,q[1]-arrow*uy+.5*arrow*ux))],color,.65)
        x,y=xy(path[1])
        items.append(f'<circle cx="{x}" cy="{y}" r=".8" fill="white" stroke="{color}" stroke-width=".6"/>')
        x,y=xy(path[-1])
        items.append(f'<circle cx="{x}" cy="{y}" r=".8" fill="{color}"/>')
    x,y=xy(SOURCE)
    items.append(f'<circle cx="{x}" cy="{y}" r="1.3" fill="#263740"/>')
    if labels:
        text(x-5,y-6,'ONE SOURCE',4.5,'#263740','end')

text(22,18,'CPC RIB / MIRRORED OVERLAY',8)
text(22,29,'Flush tangent slat seats and five attachment holes; dashed curve is the ideal reflector.',5)
items.append('<rect x="22" y="40" width="420" height="420" fill="url(#grid)" stroke="#9eafb7" stroke-width=".6" stroke-dasharray="4 3"/>')
xy=drawing(232,310,1)
ray_overlay(xy,labels=True)
text(35,450,'420 x 420 mm printer bed',5.5)
text(35,413,f'Each rib: {width:.1f} x {height:.1f} mm; overlay width: {2*max(x for x,y in back):.1f} mm',4.7)
text(35,425,'Blue = rib A; orange = mirrored rib B; translucent fill shows overlap.',4.5)
text(35,437,'Five colored paths: original source above the pipe, five right-side reflection points.',4.5)
text(474,68,'PIPE AND MOUNTING AREA / ENLARGED',6)
items.append('<defs><clipPath id="detail"><rect x="468" y="82" width="280" height="240"/></clipPath></defs>')
items.append('<g clip-path="url(#detail)">')
detail=drawing(608,145,2.5)
ray_overlay(detail)
items.append('</g>')
text(608,326,'33.4 mm OD pipe / 34.4 mm cradle bore',4.5,anchor='middle')
text(475,339,'60 mm mounting pad plus curved gusset',5)
text(475,352,'Per half: 3 pad holes 9/32 inch; 5 slat holes 3/16 inch',4.8)
text(475,365,'8 mm cradle wall; inner bore remains 34.4 mm',4.8)
text(475,378,'Smooth 22 mm rib back stands proud of slat tails',4.8)
for i,(degrees,color,path) in enumerate(zip(RAY_ANGLES,RAY_COLORS,RAYS)):
    y=402+12*i
    line([(475,y-1.5),(487,y-1.5)],color,1)
    text(492,y,f'Ray {i+1}: {degrees:.2f} deg / one reflection',4.8)
text(22,475,'Concept 25 - 12 inch reflector arc per side, R6 tangent B to rib tip. Dimensions in mm.',4.5)
items.append('</g></svg>')
(ROOT/'rib.svg').write_text('\n'.join(items)+'\n')
subprocess.run(['rsvg-convert','--width=1900','--output',str(ROOT/'rib.png'),str(ROOT/'rib.svg')],check=True)
print(f'Created mirrored overlay: each rib {width:.1f} x {height:.1f} mm.')
print('Incoming sun angles (degrees):',RAY_ANGLES)
print('Common source (mm):',SOURCE)
print('Receiver hit angles (degrees):',[round(math.degrees(math.atan2(path[-1][1],path[-1][0])),3) for path in RAYS])
print('Reflections before receiver hit:', [len(path)-2 for path in RAYS])
