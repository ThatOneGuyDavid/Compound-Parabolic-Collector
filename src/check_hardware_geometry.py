"""Conservative axial/cross-section checks against the unfilleted rib.

All hardware axes are Z. Rounded rib edges remove material from this
unfilleted envelope. A 0.02 mm material buffer covers sampling tolerance.
"""
import math
from shapely.geometry import Polygon, Point
from shapely.affinity import scale
import hardware_geometry as h


def check_clearances(profile,paired,connecting,pitch,thickness,pair_thickness):
    material=Polygon(profile.outline)
    for x,y in profile.HOLES:
        material=material.difference(Point(x,y).buffer(profile.HOLE_RADIUS,quad_segs=128))
    material=material.buffer(.02)
    assert material.is_valid
    mirrored=scale(material,xfact=-1,yfact=1,origin=(0,0))
    ribs=[]
    for i in paired:
        ribs.extend([(material,i*pitch,i*pitch+thickness),
                     (mirrored,i*pitch+thickness,i*pitch+pair_thickness)])
    receiver=Point(0,0).buffer(profile.R,quad_segs=128)
    checks=0
    def disk(x,y,r):return Point(x,y).buffer(r,quad_segs=128)
    for item in [item for group in paired.values() for item in group]+connecting:
        name=item['name'];b=item['shape'].bounding_box()
        x=(b.min.X+b.max.X)/2;y=profile.HOLE_Y
        lo,hi=b.min.Z,b.max.Z
        if name.startswith('section-'):
            # Hexagon X bounds are symmetric about the bolt axis.
            if name.endswith('washer'):
                area=disk(x,y,h.WASHER_OD/2).difference(disk(x,y,h.CLEARANCE/2))
                slices=[(area,lo,hi)]
            elif name.endswith('-nut'):
                area=disk(x,y,h.AF/math.sqrt(3)).difference(disk(x,y,(h.DIAMETER+.2)/2))
                slices=[(area,lo,hi)]
            else:
                slices=[(disk(x,y,h.AF/math.sqrt(3)),lo,lo+h.HEAD_HEIGHT),
                        (disk(x,y,h.DIAMETER/2),lo+h.HEAD_HEIGHT,hi)]
        elif 'all-thread' in name:
            slices=[(disk(x,y,h.DIAMETER/2),lo,hi)]
        else:
            od,id=(h.PVC_OD,h.PVC_ID) if 'PVC-spacer' in name else (
                (h.WIDE_OD,h.CLEARANCE) if 'washer' in name else
                (h.AF/math.sqrt(3)*2,h.DIAMETER+.2))
            slices=[(disk(x,y,od/2).difference(disk(x,y,id/2)),lo,hi)]
        for area,a,z in slices:
            assert area.intersection(receiver).area<1e-6,(name,'receiver')
            for rib,start,end in ribs:
                overlap=min(z,end)-max(a,start)
                if overlap<=1e-5:continue
                assert area.intersection(rib).area<1e-6,(name,start,'rib')
                checks+=1
    return checks
