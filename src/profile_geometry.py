"""Shared CPC cross-section, gusset and reflection relief, in millimeters."""
import math

R=1.315*25.4/2
CRADLE=R+.5
CRADLE_WALL=8.0
COLLAR=CRADLE+CRADLE_WALL
WEB=22.0
JOIN=math.sqrt((COLLAR/R)**2-1)
REFLECTOR_ARC_MM=12*25.4


def reflector_arc_for_angle(angle,n=2000):
    """Exact involute arc plus Simpson integration of the upper CPC branch."""
    start=math.pi/2+angle;end=1.5*math.pi-angle
    def speed(t):
        denominator=1+math.sin(t-angle)
        rho=R*(t+angle+math.pi/2-math.cos(t-angle))/denominator
        return rho*math.sqrt(2/denominator)
    step=(end-start)/n
    total=speed(start)+speed(end)
    for i in range(1,n):total+=(4 if i%2 else 2)*speed(start+i*step)
    return .5*R*(start*start-JOIN*JOIN)+total*step/3


def acceptance_for_arc(target):
    lo,hi=math.radians(5),math.radians(85)
    assert reflector_arc_for_angle(hi)<target<reflector_arc_for_angle(lo)
    for _ in range(44):
        mid=(lo+hi)/2
        if reflector_arc_for_angle(mid)>target:lo=mid
        else:hi=mid
    return (lo+hi)/2


ANGLE=acceptance_for_arc(REFLECTOR_ARC_MM)
END=1.5*math.pi-ANGLE
PAD_HALF=30.0
PAD_BOTTOM=-62.0
PAD_TOP=-28.0
PAD_END_RADIUS=(PAD_TOP-PAD_BOTTOM)/2
PAD_END_CENTER=(-14.0,(PAD_TOP+PAD_BOTTOM)/2)
HOLE_Y=PAD_END_CENTER[1]
HOLES=[(-15.0,HOLE_Y),(15.0,HOLE_Y),(45.0,HOLE_Y)]
HOLE_RADIUS=(9/32*25.4)/2
GUSSET_HOLE=(45.0,HOLE_Y)
GUSSET_BOSS_RADIUS=PAD_END_RADIUS
GUSSET_ANCHOR_Y=-8.0
REFLECTION_RELIEF=True
EDGE_ROUNDOVER=0.8


def point(t):
    rho=R*t if t<=math.pi/2+ANGLE else R*(t+ANGLE+math.pi/2-math.cos(t-ANGLE))/(1+math.sin(t-ANGLE))
    return R*math.sin(t)-rho*math.cos(t),-R*math.cos(t)-rho*math.sin(t)


def curve(start,end,n=700):
    return [point(start+(end-start)*i/n) for i in range(n+1)]


def arc_point(center,radius,angle):
    return center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle)


def arc_segment(center,radius,start,end):
    return dict(kind='arc',center=center,radius=radius,start=start,end=end)


def segment_points(segment,n=80):
    kind=segment['kind']
    if kind in ('line','spline'):return segment['points']
    if kind=='arc':
        return [arc_point(segment['center'],segment['radius'],
                segment['start']+(segment['end']-segment['start'])*i/n) for i in range(n+1)]
    if kind=='bezier':
        a,b,c,d=segment['points'];result=[]
        for i in range(n+1):
            t=i/n;u=1-t
            result.append(tuple(u**3*a[j]+3*u*u*t*b[j]+3*u*t*t*c[j]+t**3*d[j] for j in (0,1)))
        return result
    raise ValueError(kind)


edge=curve(JOIN,END)
lower=curve(0,JOIN,250)
back=[]
for i,(x,y) in enumerate(edge):
    a,b=edge[max(0,i-1)],edge[min(len(edge)-1,i+1)]
    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    back.append((x+WEB*dy/length,y-WEB*dx/length))
kept=[]
for a,b in zip(reversed(back),list(reversed(back))[1:]):
    kept.append(a)
    if a[1]>=GUSSET_ANCHOR_Y and b[1]<GUSSET_ANCHOR_Y:
        t=(GUSSET_ANCHOR_Y-a[1])/(b[1]-a[1])
        kept.append((a[0]+t*(b[0]-a[0]),GUSSET_ANCHOR_Y));break
assert len(kept)>2
anchor=kept[-1]
foot=(GUSSET_HOLE[0],PAD_BOTTOM)
# Match the opposite R17 pad end around the outer mounting hole.
beta=math.atan2(anchor[1]-GUSSET_HOLE[1],anchor[0]-GUSSET_HOLE[0])
boss_start=beta-math.acos(GUSSET_BOSS_RADIUS/math.dist(anchor,GUSSET_HOLE))
boss_end=-math.pi/2
boss_p1=arc_point(GUSSET_HOLE,GUSSET_BOSS_RADIUS,boss_start)
boss_p2=arc_point(GUSSET_HOLE,GUSSET_BOSS_RADIUS,boss_end)
join_angle=math.atan2(edge[0][1],edge[0][0])
relief_arc_start=(-14.0,-math.sqrt(COLLAR**2-14**2))
relief_angle=math.atan2(relief_arc_start[1],relief_arc_start[0])
transition=math.pi/2+ANGLE
# Tangent-aligned blends remove the visible kinks at the gusset shoulder
# and where its rounded toe meets the mounting-pad bottom.
dx,dy=anchor[0]-kept[-2][0],anchor[1]-kept[-2][1]
l=math.hypot(dx,dy)
shoulder_c1=(anchor[0]+15*dx/l,anchor[1]+15*dy/l)
shoulder_tangent=(math.sin(boss_start),-math.cos(boss_start))
shoulder_c2=(boss_p1[0]-12*shoulder_tangent[0],boss_p1[1]-12*shoulder_tangent[1])
# One semicircular pad end joins the straight bottom to the relief.
# Its centerline also locates every mounting hole.
relief_tip=(PAD_END_CENTER[0],PAD_TOP)
relief_tip_tangent=(1.0,0.0)
relief_ring_tangent=(math.sin(relief_angle),-math.cos(relief_angle))
segments=[
    arc_segment((0,0),CRADLE,math.pi,2*math.pi),
    dict(kind='line',points=[(CRADLE,0),(COLLAR,0)]),
    arc_segment((0,0),COLLAR,0,join_angle),
    dict(kind='spline',points=curve(JOIN,transition,80)),
    dict(kind='spline',points=curve(transition,END,120)),
    dict(kind='line',points=[edge[-1],kept[0]]),
    dict(kind='spline',points=kept),
    dict(kind='bezier',points=[anchor,shoulder_c1,shoulder_c2,boss_p1]),
    arc_segment(GUSSET_HOLE,GUSSET_BOSS_RADIUS,boss_start,boss_end),
    dict(kind='line',points=[foot,(PAD_END_CENTER[0],PAD_BOTTOM)]),
    arc_segment(PAD_END_CENTER,PAD_END_RADIUS,-math.pi/2,-3*math.pi/2),
    dict(kind='bezier',points=[relief_tip,
        (relief_tip[0]+3*relief_tip_tangent[0],relief_tip[1]+3*relief_tip_tangent[1]),
        (relief_arc_start[0]-4*relief_ring_tangent[0],relief_arc_start[1]-4*relief_ring_tangent[1]),relief_arc_start]),
    arc_segment((0,0),COLLAR,relief_angle,-math.pi),
    dict(kind='line',points=[(-COLLAR,0),(-CRADLE,0)]),
]
outline=[]
for segment in segments:
    points=segment_points(segment)
    if outline:
        assert math.dist(outline[-1],points[0])<1e-6,(outline[-1],points[0])
        points=points[1:]
    outline.extend(points)
assert math.dist(outline[0],outline[-1])<1e-6
inner=segment_points(segments[0])
outer=segment_points(segments[2])
width=max(x for x,y in outline)-min(x for x,y in outline)
height=max(y for x,y in outline)-min(y for x,y in outline)
assert width<420 and height<420
