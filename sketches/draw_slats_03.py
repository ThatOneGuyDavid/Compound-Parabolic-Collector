"""Current v15 support drawing, using the same row geometry as the CAD."""
from pathlib import Path
import html
import math
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import profile_geometry as p
import slat_geometry as s

out = Path(__file__).parent
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000">',
       '<rect width="1600" height="1000" fill="#faf8f1"/>',
       '<g font-family="Arial,sans-serif" fill="#273740">']
def text(x, y, value, size=20):
    svg.append(f'<text x="{x}" y="{y}" font-size="{size}">{html.escape(value)}</text>')
def line(points, color='#526971', width=2):
    svg.append('<polyline points="' + ' '.join(f'{x:.4f},{y:.4f}' for x,y in points) + f'" fill="none" stroke="{color}" stroke-width="{width}"/>')
def poly(points, fill, color='#315d6b'):
    svg.append('<polygon points="' + ' '.join(f'{x:.4f},{y:.4f}' for x,y in points) + f'" fill="{fill}" stroke="{color}" stroke-width="1.5"/>')
def circle(x,y,r,fill='#faf8f1'):
    svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="#526971" stroke-width="1.5"/>')
text(40,48,'REFLECTOR SUPPORT — current v15 geometry — drawing 03',30)
text(40,82,'12-inch arc per side • Five tangent supports per side per bay • One identical master slat everywhere',20)
text(40,135,'END VIEW — actual support locations',23)
scale=1.6
def end(q): return (345+scale*q[0],535-scale*q[1])
outline=list(s.seat_polygon().exterior.coords)
for side,fill in ((-1,'#dfc4a6'),(1,'#bfd4dc')):
    poly([end((side*x,y)) for x,y in outline],fill)
    for x,y in p.HOLES:
        circle(*end((side*x,y)),p.HOLE_RADIUS*scale)
    for row in s.LAYOUT:
        points=[s.xy(row,u,v) for u,v in [(-s.WIDTH/2,0),(s.WIDTH/2,0),(s.WIDTH/2,s.GAUGE),(-s.WIDTH/2,s.GAUGE)]]
        poly([end((side*x,y)) for x,y in points],'#e9c16e','#936d22')
        x,y=row['hole'];circle(*end((side*x,y)),s.SLAT_CLEARANCE/2*scale)
        if side==1:
            x,y=end(s.xy(row,0,30));text(x,y,str(row['index']),18)
circle(*end((0,0)),p.R*scale,'#d2d4d2')
text(42,680,'Gold = support face; circles = modeled holes',18)
text(42,712,'Lowest support: 45 mm along the arc from A',18)
text(42,744,'Top support edge meets the rib tip',18)

text(755,135,'MASTER SLAT — longitudinal section',23)
text(755,169,'Formed axial span 363 mm; flat blank length pending',19)
# Exact z-v cross section of the source master, including its circular bends.
r=s.OUTER_RADIUS;ri=s.INNER_RADIUS;length=363.;depth=s.TAB_DEPTH;g=s.GAUGE
points=[]
def add(z,v): points.append((z,v))
def arc(c,rad,a,b):
    for i in range(33):
        t=a+(b-a)*i/32;add(c[0]+rad*math.cos(t),c[1]+rad*math.sin(t))
add(r,0);add(length-r,0);arc((length-r,r),r,-math.pi/2,0)
add(length,depth);add(length-g,depth);add(length-g,r)
arc((length-r,r),ri,0,-math.pi/2);add(r,g)
arc((r,r),ri,-math.pi/2,-math.pi);add(g,depth);add(0,depth);add(0,r)
arc((r,r),r,math.pi,3*math.pi/2)
poly([(770+z*2,260+v*2) for z,v in points],'#e9c16e','#936d22')
line([(770,220),(1496,220)])
line([(770,212),(770,228)]);line([(1496,212),(1496,228)])
text(1040,207,'363 mm formed',20)
text(755,350,'Strip: 19.05 mm wide × 1.5875 mm thick',20)
text(755,386,'Bends: 90°; inner radius 1.5875 mm',20)
text(755,422,'Tab depth: 19.05 mm; hole depth: 11.5 mm',20)
text(755,458,'Tab holes: 3/16 inch / 4.7625 mm diameter',20)

text(755,535,'ASSEMBLY OPTIONS',23)
for x,heading in ((755,'Printed prototype'),(1160,'CNC aluminum')):
    text(x,578,heading,22)
for y,left,right in (
    (615,'12 mm halves / 24 mm pair','3.175 mm halves / 6.35 mm pair'),
    (651,'375 mm station pitch','366.175 mm station pitch'),
    (687,'¼-20 × 1½ inch pair bolts','¼-20 × ¾ inch pair bolts'),
    (723,'#8-32 × 1 inch slat screws','#8-32 × ⅝ inch slat screws')):
    text(755,y,left,18);text(1160,y,right,18)
line([(40,794),(1560,794)],'#c7cdcc',1)
text(40,840,'Five paired stations • Four bays • Ten slats per bay • Forty copies of one formed master',22)
text(40,882,'Both rib options retain the same slats, PVC spacer lengths, 12-inch arc and receiver/cradle profile.',20)
text(40,922,'Reference drawing from CAD inputs; CNC profile is supplied separately as a 1:1 mm DXF.',18)
text(40,958,'Physical fit and bend allowance remain untested. Optical reflector attachment is not shown.',18)
svg.append('</g></svg>')
(out/'reflector-slats-03.svg').write_text('\n'.join(svg))
subprocess.run(['rsvg-convert','-o',str(out/'reflector-slats-03.png'),str(out/'reflector-slats-03.svg')],check=True)
print('Created current v15 support drawing 03 from the shared slat geometry.')
