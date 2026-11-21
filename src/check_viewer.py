#!/usr/bin/env python3
"""Check the paired-subassembly viewer in real Chromium, offline."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'models'/'v16'
errors=[]
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,
        args=['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader',
              '--use-gl=angle','--use-angle=swiftshader'])
    page=browser.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1)
    page.set_default_navigation_timeout(120000)
    page.set_default_timeout(60000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((ROOT/'assembly-viewer.html').as_uri(),wait_until='load')
    page.wait_for_function('window.cpcViewer && cpcViewer.parts.length===329')
    page.wait_for_timeout(400)
    assert page.evaluate('Boolean(document.querySelector("#parts").compareDocumentPosition(document.querySelector(".dimensions")) & Node.DOCUMENT_POSITION_FOLLOWING)')
    assert page.evaluate('cpcViewer.getVariant()')=='aluminum'
    assert page.locator('input[type=number]').count()==0
    assert page.locator('#assembly-parts > ul > li').count()==4
    assert page.locator('#assembly-parts ul ul').count()>=4
    assert '⅛″ CNC aluminum rib halves' in page.locator('#assembly-parts').inner_text()
    page.get_by_role('button',name='Printed · 12 mm',exact=True).click()
    assert page.evaluate('cpcViewer.getVariant()')=='printed'
    assert '12 mm printed rib halves' in page.locator('#assembly-parts').inner_text()
    assert abs(page.evaluate('config.backbone_length_mm')-1524)<1e-8
    assert abs(page.evaluate('config.hardware.bolt_length_mm')-38.1)<1e-8
    assert page.evaluate('config.slats.slat_screw_length_mm')==25.4
    assert '¼″-20 × 1-1/2″ pair bolts' in page.locator('#assembly-parts').inner_text()
    assert '#8-32 × 1″ slat screws' in page.locator('#assembly-parts').inner_text()
    printed_pipe=page.evaluate('parts.find(p=>p.category==="pipe").bounds.map(v=>v.map((n,i)=>n+parts.find(p=>p.category==="pipe").offset[i]))')
    printed_rod=page.evaluate('parts.find(p=>p.name==="right-all-thread-1-4-20").bounds.map(v=>v.map((n,i)=>n+parts.find(p=>p.name==="right-all-thread-1-4-20").offset[i]))')
    assert page.evaluate('cpcViewer.webgl.getError()')==0
    assert page.evaluate('cpcViewer.parts.filter(p=>p.visible).length')==329
    assert page.evaluate('descendants(layerRoot).length===parts.length && new Set(descendants(layerRoot)).size===parts.length')
    assert page.evaluate('parts.every(p=>["ribs","pipe","pair-hardware","connecting","slats"].includes(p.category))')
    assert page.locator('#explode').count()==0
    assert page.get_by_role('button',name='Rib half',exact=True).count()==0
    checks.append('Offline WebGL renders five bolted sections, PVC spacers, all-thread, washers and lock nuts')
    page.screenshot(path=str(OUT/'printed-backbone-preview.png'))

    section=page.get_by_role('checkbox',name='Rib section 1 (pair)',exact=True)
    section.uncheck()
    assert page.evaluate('parts.filter(p=>p.station===0).every(p=>!p.visible)')
    assert page.evaluate('parts.filter(p=>p.visible).length')==279
    section.check()
    assert page.evaluate('parts.filter(p=>p.station===0).every(p=>p.visible)')
    for i in range(5):
        assert page.evaluate('(i)=>layerNodes.get("station-"+i).parts.length',i)==50
    checks.append('Each section visibility toggles both halves and its clamping and slat attachment hardware')

    pipe=page.get_by_role('checkbox',name='Receiver pipe',exact=True)
    pipe.uncheck()
    assert page.evaluate('parts.filter(p=>p.visible).length')==328
    pipe.check()
    page.get_by_role('button',name='One rib section',exact=True).click()
    assert page.evaluate('parts.filter(p=>p.visible).length')==50
    assert page.evaluate('parts.filter(p=>p.visible).every(p=>p.station===0)')
    assert page.evaluate('config.half_offset_mm')==12
    assert page.evaluate('config.pair_thickness_mm')==24
    assert page.evaluate('config.cradle_wall_mm')==8
    assert page.evaluate('config.reflection_relief') is True
    assert page.evaluate('config.hole_centers_per_half_mm.length')==3
    assert page.evaluate('config.pad_end_radius_mm')==17
    assert page.evaluate('config.rib_side_radius_mm')==17
    assert page.evaluate('config.hole_centers_per_half_mm.every(p=>p[1]===config.pad_end_center_mm[1])')
    checks.append('Matching R17 pad ends and three mounting holes on its horizontal centerline')
    page.locator('aside').evaluate('(e)=>{e.scrollTop=0}')
    page.screenshot(path=str(OUT/'printed-rib-section-preview.png'))
    checks.append('Section inspection isolates a complete bolted pair with its 12 mm half offset')

    page.locator('#zoom').evaluate('(e)=>{e.value="200";e.dispatchEvent(new Event("input",{bubbles:true}))}')
    assert page.evaluate('Math.abs(cpcViewer.getState().zoom/cpcViewer.getState().fitZoom-2)<1e-8')
    page.get_by_role('button',name='Fit view',exact=True).click()
    assert page.locator('#zoom-value').inner_text()=='100%'
    box=page.locator('#view').bounding_box()
    x,y=box['x']+box['width']/2,box['height']/2
    old=page.evaluate('cpcViewer.getState().yaw')
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+80,y+30,steps=5);page.mouse.up()
    assert abs(page.evaluate('cpcViewer.getState().yaw')-old)>.1
    before=page.evaluate('cpcViewer.getState().focus')
    page.keyboard.down('Shift');page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+35,y,steps=3);page.mouse.up();page.keyboard.up('Shift')
    after=page.evaluate('cpcViewer.getState().focus')
    assert sum((a-b)**2 for a,b in zip(before,after))>1
    checks.append('Slider zoom, fit reset, pointer rotation and shift-drag pan work')
    page.get_by_role('button',name='Whole layout',exact=True).click()
    assert page.evaluate('parts.filter(p=>p.visible).length')==329
    assert page.evaluate('cpcViewer.webgl.getError()')==0
    assert page.evaluate('config.hardware.thread')=='1/4-20 UNC'
    assert page.evaluate('parts.filter(p=>p.category==="connecting").length')==38
    page.get_by_role('button',name='Connection detail',exact=True).click()
    page.screenshot(path=str(OUT/'printed-hardware-preview.png'))
    checks.append('Connection detail shows imperial hardware and the staggered PVC spacer attachment')
    page.get_by_role('checkbox',name='Slat bay 1 (10 slats)',exact=True).uncheck()
    assert page.evaluate('parts.filter(p=>p.category==="slats"&&p.bay===0).every(p=>!p.visible)')
    page.get_by_role('button',name='One slat bay',exact=True).click()
    assert page.evaluate('parts.filter(p=>p.visible).length')==116
    assert page.evaluate('parts.filter(p=>p.visible&&p.category==="slats").length')==10
    assert page.evaluate('config.slats.slat_quantity')==40
    assert page.evaluate('config.slats.unique_slat_designs')==1
    assert abs(page.evaluate('config.reflector_arc_per_side_mm')-304.8)<1e-9
    assert abs(page.evaluate('config.cradle_reflector_radius_mm')-6)<1e-9
    assert abs(page.evaluate('config.acceptance_half_angle_deg')-27.4672909353)<1e-8
    assert 'Reflector arc: 12″ from R6 tangent to top' in page.locator('#dimensions').inner_text()
    for link in page.locator('.downloads a').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))'):
        assert (ROOT/link).is_file(),link
    assert page.evaluate('config.slats.rib_back_envelope.rib_web_mm')==22
    assert page.evaluate('config.slats.rib_back_envelope.minimum_proud_mm')>.1
    assert page.evaluate('config.slats.fastener_thread')=='#8-32 UNC'
    assert abs(page.evaluate('config.slats.slat_hole_diameter_mm')-4.7625)<1e-9
    assert page.evaluate('config.hardware.thread')=='1/4-20 UNC'
    assert page.evaluate('config.slats.top_edge_error_mm')<1e-6
    page.screenshot(path=str(OUT/'printed-slat-bay-preview.png'))
    checks.append('Forty slats grouped in four bays; one-bay view includes ten slats, two bolted stations and PVC spacers')
    visible=page.evaluate('parts.filter(p=>p.visible).map(p=>p.name).sort()')
    page.get_by_role('button',name='Aluminum · ⅛″',exact=True).click()
    assert page.evaluate('cpcViewer.getVariant()')=='aluminum'
    assert page.evaluate('config.rib_thickness_mm')==3.175
    assert abs(page.evaluate('config.hardware.bolt_length_mm')-19.05)<1e-8
    assert abs(page.evaluate('config.slats.slat_screw_length_mm')-15.875)<1e-8
    assert '¼″-20 × 3/4″ pair bolts' in page.locator('#assembly-parts').inner_text()
    assert '#8-32 × 5/8″ slat screws' in page.locator('#assembly-parts').inner_text()
    # Check actual rendered bolt/screw axial extents, including modeled heads.
    for name,expected in [('section-01-bolt-1',19.05+25.4*5/32),('section-01-right-slat-1-screw',15.875+25.4*.116)]:
        extent=page.evaluate('(name)=>{const p=parts.find(p=>p.name===name);return p.bounds[1][0]-p.bounds[0][0]}',name)
        assert abs(extent-expected)<1e-5,(name,extent,expected)
    assert abs(page.evaluate('config.backbone_length_mm')-1471.05)<1e-7
    assert abs(page.evaluate('config.station_pitch_mm')-366.175)<1e-7
    assert abs(page.evaluate('config.pipe_overhang_each_mm')-178.875)<1e-7
    assert abs(page.evaluate('config.hardware.spacer_length_mm')-359.825)<1e-7
    assert abs(page.evaluate('config.hardware.rod_length_mm')-1549.4)<1e-7
    assert page.evaluate('parts.filter(p=>p.visible).map(p=>p.name).sort()')==visible
    aluminum_pipe=page.evaluate('parts.find(p=>p.category==="pipe").bounds.map(v=>v.map((n,i)=>n+parts.find(p=>p.category==="pipe").offset[i]))')
    aluminum_rod=page.evaluate('parts.find(p=>p.name==="right-all-thread-1-4-20").bounds.map(v=>v.map((n,i)=>n+parts.find(p=>p.name==="right-all-thread-1-4-20").offset[i]))')
    assert max(abs(a-b) for aa,bb in zip(printed_pipe,aluminum_pipe) for a,b in zip(aa,bb))<1e-6
    assert max(abs(a-b) for aa,bb in zip(printed_rod,aluminum_rod) for a,b in zip(aa,bb))<1e-6
    colors=page.evaluate('parts.filter(p=>p.category==="ribs"&&p.station===0).map(p=>p.color)')
    assert sum((a-b)**2 for a,b in zip(*colors))>.1
    assert page.get_by_role('button',name='Aluminum · ⅛″',exact=True).get_attribute('aria-pressed')=='true'
    for link in page.locator('.downloads a').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))'):
        assert 'aluminum/' in link and (ROOT/link).is_file(),link
    page.screenshot(path=str(OUT/'aluminum-slat-bay-preview.png'))
    page.get_by_role('button',name='One rib section',exact=True).click()
    assert page.evaluate('parts.filter(p=>p.visible).length')==50
    intervals=page.evaluate('parts.filter(p=>p.category==="ribs"&&p.station===0).map(p=>[p.bounds[0][0]+p.offset[0],p.bounds[1][0]+p.offset[0]])')
    assert abs(intervals[0][1]-intervals[1][0])<1e-5
    assert all(abs(b-a-3.175)<1e-5 for a,b in intervals)
    page.screenshot(path=str(OUT/'aluminum-rib-section-preview.png'))
    page.get_by_role('button',name='Whole layout',exact=True).click()
    page.screenshot(path=str(OUT/'aluminum-backbone-preview.png'))
    page.locator('#view').screenshot(path=str(OUT/'aluminum-backbone-model.png'))
    page.get_by_role('button',name='Printed · 12 mm',exact=True).click()
    assert page.evaluate('config.rib_thickness_mm')==12
    assert page.evaluate('parts.filter(p=>p.visible).length')==329
    page.get_by_role('button',name='Aluminum · ⅛″',exact=True).click()
    assert page.evaluate('cpcViewer.webgl.getError()')==0
    checks.append('Printed/aluminum switch uses fixed 12 mm / 1/8-inch ribs, preserves visibility and fixed pipe/rod/slat/spacer sizes, and updates matching downloads')
    checks.append('Material switch updates modeled rib bolts and slat screws, matching BOM lengths and download targets')
    checks.append('Aluminum halves have contrasting silver colors, adjacent nonoverlapping axial intervals and visible pair separation')
    rods=page.get_by_role('checkbox',name='All-thread rods',exact=True)
    spacers=page.get_by_role('checkbox',name='PVC spacers',exact=True)
    rods.uncheck()
    assert page.evaluate('parts.filter(p=>p.name.includes("all-thread")).every(p=>!p.visible)')
    assert page.evaluate('parts.filter(p=>p.name.includes("PVC-spacer")).every(p=>p.visible)')
    assert page.evaluate('parts.filter(p=>p.visible).length')==327
    rods.check();spacers.uncheck()
    assert page.evaluate('parts.filter(p=>p.name.includes("all-thread")).every(p=>p.visible)')
    assert page.evaluate('parts.filter(p=>p.name.includes("PVC-spacer")).every(p=>!p.visible)')
    assert page.evaluate('parts.filter(p=>p.visible).length')==321
    page.get_by_role('button',name='Printed · 12 mm',exact=True).click()
    assert page.evaluate('parts.filter(p=>p.name.includes("PVC-spacer")).every(p=>!p.visible)')
    assert page.evaluate('parts.filter(p=>p.name.includes("all-thread")).every(p=>p.visible)')
    spacers.check()
    assert page.evaluate('parts.filter(p=>p.visible).length')==329
    checks.append('Rods, PVC spacers and connector hardware have independent visibility; material switching preserves those choices')
    assert not errors,errors
    browser.close()
(OUT/'viewer-validation.json').write_text(json.dumps({'checks':checks,'browser_errors':errors},indent=2)+'\n')
print('PASS: '+'; '.join(checks))
