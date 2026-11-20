#!/usr/bin/env python3
"""Build a self-contained two-material viewer with shared geometry buffers."""
from pathlib import Path
import base64,hashlib,json
import numpy as np
import trimesh as tm
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'models'/'v15'
assets={};variants={};configs={}
for variant in ('printed','aluminum'):
    folder=OUT/variant
    config=json.loads((folder/'validation.json').read_text())
    config['download_dir']=folder.relative_to(ROOT).as_posix()
    configs[variant]=config;definitions=[]
    for part in json.loads((folder/'viewer-parts.json').read_text()):
        vertices=np.array(part['vertices'],dtype=float)[:,[2,1,0]]*np.array([1,1,-1])
        vertices[:,0]-=config['backbone_length_mm']/2
        m=tm.Trimesh(vertices,np.array(part['faces']),process=False)
        offset=m.bounds.mean(axis=0)
        triangles=m.triangles.reshape(-1,3)-offset
        normals=np.repeat(m.face_normals,3,axis=0)
        data=np.concatenate([triangles,normals],axis=1).astype('<f4')
        canonical=np.round(data,5);canonical[canonical==0]=0
        key=hashlib.sha256(canonical.tobytes()).hexdigest()[:24]
        if key not in assets:
            assets[key]=dict(key=key,count=len(data),data=base64.b64encode(data.tobytes()).decode())
        definitions.append(dict(name=part['name'],category=part['category'],station=part['station'],
            bay=part.get('metadata',{}).get('bay'),asset=key,color=part['color'],
            offset=offset.tolist(),bounds=(m.bounds-offset).tolist()))
    variants[variant]=definitions
assert [p['name'] for p in variants['printed']]==[p['name'] for p in variants['aluminum']]
html=(ROOT/'src/viewer-template.html').read_text()
html=html.replace('__DATA__',json.dumps(list(assets.values()),separators=(',',':')))
html=html.replace('__VARIANTS__',json.dumps(variants,separators=(',',':')))
html=html.replace('__CONFIGS__',json.dumps(configs,separators=(',',':')))
html=html.replace('__MODEL_DIR__',configs['aluminum']['download_dir'])
(ROOT/'assembly-viewer.html').write_text(html)
(OUT/'variants.json').write_text(json.dumps({key:{'thickness_mm':c['rib_thickness_mm'],
 'rib_span_mm':c['backbone_length_mm'],'pitch_mm':c['station_pitch_mm'],
 'pipe_length_mm':c['pipe_length_mm'],'pipe_overhang_each_mm':c['pipe_overhang_each_mm'],
 'rod_length_mm':c['hardware']['rod_length_mm'],'slat_length_mm':c['slats']['formed_overall_length_mm'],
 'rib_bolt_length_mm':c['hardware']['bolt_length_mm'],'slat_screw_length_mm':c['slats']['slat_screw_length_mm']}
 for key,c in configs.items()},indent=2)+'\n')
print(f'Built two fixed variants, {len(variants["aluminum"])} parts each, {len(assets)} shared geometry buffers ({len(html)/1e6:.2f} MB).')
