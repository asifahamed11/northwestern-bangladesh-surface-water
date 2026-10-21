"""Redraw Figure 1 with verified, unsimplified district boundaries.

This is a presentation-only update. No observations, cohorts, estimates or
conclusions are recalculated. Run from the repository with the existing Python
3.12 requirements and installed Times New Roman. Output must be a new folder.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch,Rectangle
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image
from pyproj import CRS,Geod,Transformer
from shapely.geometry import shape,box,LineString,Point
from shapely.geometry.polygon import orient
from shapely.ops import transform,unary_union

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();OUT=args.output.resolve()
assert not OUT.exists(),'Choose a new output folder; prior figures are preserved.'
assert OUT!=ROOT and not any(OUT.is_relative_to(ROOT/x) for x in ['code','data','figures','manuscript','provenance','.git'])
OUT.mkdir(parents=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
INPUTS=[ROOT/'data/boundaries/study_area.geojson',ROOT/'data/boundaries/national_adm2.geojson.gz']
EXPECTED=['10699eaea184d4c194da746e671feec2a2c715c477f593b0118b17332f736f18','54379ccc77f6f59dab3569ecc5f9b3850dbed2d65a5f43a034bdf92179f5621b']
raw=[INPUTS[0].read_bytes(),gzip.decompress(INPUTS[1].read_bytes())]
assert [hashlib.sha256(s).hexdigest() for s in raw]==EXPECTED
verified,national=[json.loads(s.decode('utf-8')) for s in raw]
assert len(verified['features'])==3 and len(national['features'])==64
CRS_MAP=CRS.from_proj4('+proj=tmerc +lat_0=0 +lon_0=90 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')
forward=Transformer.from_crs(4326,CRS_MAP,always_xy=True)
inverse=Transformer.from_crs(CRS_MAP,4326,always_xy=True)
geod=Geod(ellps='WGS84')
COLORS={'Naogaon':'#BCD0DC','Chapainawabganj':'#D9C5A5','Rajshahi':'#BFD0C0'}
INK,MUTED,LINE='#202020','#555555','#BABABA'
districts={}
for ft in verified['features']:
 name=ft['properties']['district'].replace('Nawabganj','Chapainawabganj')
 districts[name]=transform(forward.transform,shape(ft['geometry']))
assert set(districts)==set(COLORS)
context=[transform(forward.transform,shape(ft['geometry'])) for ft in national['features']]
study_union=unary_union(list(districts.values()))
WIDTH_PX,HEIGHT_PX,DPI=2267,1902,320
font=font_manager.findfont('Times New Roman',fallback_to_default=False)
plt.rcParams.update({'font.family':'Times New Roman','font.size':9,'text.color':INK,
 'axes.edgecolor':LINE,'svg.fonttype':'none','pdf.fonttype':42,
 'path.simplify':False,'savefig.facecolor':'white'})
fig=plt.figure(figsize=(WIDTH_PX/DPI,HEIGHT_PX/DPI),facecolor='white')
all_labels=[]
def text(x,y,value,**kwargs):
 label=fig.text(x,y,value,**kwargs);all_labels.append(label);return label

def add_geometry(ax, geom, **kwargs):
    polygons = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
    for polygon in polygons:
        polygon = orient(polygon, sign=1.0)
        rings = [polygon.exterior] + list(polygon.interiors)
        paths = []
        for ring in rings:
            coords = np.asarray(ring.coords)
            codes = np.full(len(coords), MPath.LINETO, dtype=np.uint8)
            codes[0], codes[-1] = MPath.MOVETO, MPath.CLOSEPOLY
            paths.append(MPath(coords, codes))
        ax.add_patch(PathPatch(MPath.make_compound_path(*paths), **kwargs))


def map_axes(rect, bounds, padding):
    ax = fig.add_axes(rect)
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = (x1 - x0) * (1 + padding), (y1 - y0) * (1 + padding)
    target_ratio = rect[2] * WIDTH_PX / (rect[3] * HEIGHT_PX)
    dx, dy = max(dx, dy * target_ratio), max(dy, dx / target_ratio)
    ax.set(xlim=(cx - dx / 2, cx + dx / 2), ylim=(cy - dy / 2, cy + dy / 2))
    ax.set_aspect('equal', adjustable='box')
    ax.set_facecolor('white')
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_linewidth(.6)
    return ax


def graticules(ax, longitudes, latitudes):
    """Project geographic graticules and place labels at their frame intersections."""
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    frame = box(xmin, ymin, xmax, ymax)
    bottom = LineString([(xmin, ymin), (xmax, ymin)])
    left = LineString([(xmin, ymin), (xmin, ymax)])
    for lon in longitudes:
        lats = np.linspace(19, 29, 300)
        xx, yy = forward.transform(np.full_like(lats, lon), lats)
        segment = LineString(np.column_stack([xx, yy]))
        ax.plot(xx, yy, lw=.35, color='#E1E1E1', ls=(0, (2, 3)), zorder=0)
        hit = segment.intersection(bottom)
        if hit.geom_type == 'Point':
            label = ax.annotate(f'{lon:g}°E', (hit.x, hit.y), xytext=(0, -5),
                                textcoords='offset points', ha='center', va='top',
                                fontsize=8.5, color=MUTED, clip_on=False)
            all_labels.append(label)
    for lat in latitudes:
        lons = np.linspace(86, 95, 300)
        xx, yy = forward.transform(lons, np.full_like(lons, lat))
        segment = LineString(np.column_stack([xx, yy]))
        ax.plot(xx, yy, lw=.35, color='#E1E1E1', ls=(0, (2, 3)), zorder=0)
        hit = segment.intersection(left)
        if hit.geom_type == 'Point':
            label = ax.annotate(f'{lat:g}°N', (hit.x, hit.y), xytext=(-4, 0),
                                textcoords='offset points', ha='right', va='center',
                                fontsize=8.5, color=MUTED, clip_on=False)
            all_labels.append(label)


scale_records = []


def scale_bar(ax, start_fraction, segment_km):
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    start = (xmin + (xmax-xmin)*start_fraction[0], ymin+(ymax-ymin)*start_fraction[1])
    lon, lat = inverse.transform(*start)
    points = [start]
    for distance in [segment_km * 1000, segment_km * 2000]:
        lon1, lat1, _ = geod.fwd(lon, lat, 90, distance)
        points.append(forward.transform(lon1, lat1))
    for i in range(2):
        xs, ys = zip(*points[i:i+2])
        ax.plot(xs, ys, color=INK if i == 0 else '#9D9D9D', lw=2.0,
                solid_capstyle='butt', zorder=8)
    for i, point in enumerate(points):
        label = ax.annotate(f'{i * segment_km:g}' + (' km' if i == 2 else ''),
                            point, xytext=(0, 5), textcoords='offset points',
                            ha='center', va='bottom', fontsize=8.5, zorder=9,
                            bbox={'fc': 'white', 'ec': 'none', 'alpha': .85, 'pad': .2})
        all_labels.append(label)
    scale_records.append({'segment_km': segment_km, 'vertices_projected_m': points,
                          'start_lon_lat': [lon, lat],
                          'geodesic_lengths_m': [geod.inv(lon, lat, *inverse.transform(*pt))[2] for pt in points[1:]]})


def north_arrow(ax, anchor=(.91, .82), length_fraction=.10):
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    base = (xmin + anchor[0] * (xmax-xmin), ymin + anchor[1] * (ymax-ymin))
    lon, lat = inverse.transform(*base)
    tip = forward.transform(*geod.fwd(lon, lat, 0, (ymax-ymin)*length_fraction)[:2])
    ax.annotate('', tip, base, arrowprops={'arrowstyle': '-|>', 'color': INK,
                                         'lw': .8, 'mutation_scale': 7}, zorder=9)
    label = ax.annotate('N', tip, xytext=(0, 3), textcoords='offset points',
                        ha='center', va='bottom', fontsize=8.5, zorder=9)
    all_labels.append(label)


# Panel headings sit outside the geographic content.
text(.050,.958,'A',fontsize=11,fontweight='bold')
text(.081,.958,'Bangladesh',fontsize=11)
text(.449,.958,'B',fontsize=11,fontweight='bold')
text(.480,.958,'Study districts',fontsize=11)
a=map_axes([.063,.395,.293,.532],unary_union(context).bounds,.13)
b=map_axes([.451,.395,.502,.532],study_union.bounds,.21)
graticules(a,[88,90,92],[22,24,26])
graticules(b,[88,88.5,89],[24.25,24.75,25.25])
for ax in [a,b]:
 viewport=box(ax.get_xlim()[0],ax.get_ylim()[0],ax.get_xlim()[1],ax.get_ylim()[1])
 for geom in context:
  if geom.intersects(viewport):add_geometry(ax,geom,facecolor='#F3F3F3',edgecolor='#CACACA',lw=.24,zorder=1)
 for name,geom in districts.items():add_geometry(ax,geom,facecolor=COLORS[name],edgecolor='#626262',lw=.50,zorder=3)
add_geometry(a,unary_union(context),facecolor='none',edgecolor='#909090',lw=.45,zorder=2)
x0,y0,x1,y1=study_union.bounds
a.add_patch(Rectangle((x0-8500,y0-8500),x1-x0+17000,y1-y0+17000,fill=False,lw=.8,edgecolor=INK,ls=(0,(3,2)),zorder=7))
label=a.annotate('B',(x1+8500,y1+8500),xytext=(3,2),textcoords='offset points',fontsize=8.5,fontweight='bold',ha='left',va='bottom')
all_labels.append(label)
label_positions={}
for name,at in [('Naogaon',(88.77,24.94)),('Rajshahi',(88.66,24.43))]:
 xy=forward.transform(*at);assert districts[name].contains(Point(xy))
 label=b.text(*xy,name,ha='center',va='center',fontsize=10,fontstyle='italic',color=INK,zorder=8)
 all_labels.append(label);label_positions[name]=list(at)
target=districts['Chapainawabganj'].representative_point()
label=b.text(target.x,target.y,'Chapainawabganj',ha='center',va='center',rotation=70,rotation_mode='anchor',fontsize=9.0,fontstyle='italic',color=INK,zorder=8)
all_labels.append(label);label_positions['Chapainawabganj']=list(inverse.transform(target.x,target.y))
north_arrow(a,(.88,.80),.065)
north_arrow(b,(.92,.82),.065)
scale_bar(a,(.17,.055),100)
scale_bar(b,(.47,.055),20)

# A compact comparison table replaces the card layout, without causal arrows.
text(.050,.318,'C',fontsize=11,fontweight='bold')
text(.081,.318,'Analysis domains',fontsize=11)
for x,label in [(.050,'Component'),(.303,'Period'),(.467,'Evidence and analytical scope')]:
 text(x,.276,label,fontsize=9,fontweight='bold')
for y in [.263,.190,.117,.044]:
 fig.add_artist(Line2D([.05,.953],[y,y],transform=fig.transFigure,lw=.6,color=LINE))
rows=[
 (.242,'Annual source classes','2000–2021','JRC seasonal and permanent classes\nFixed footprint: 1,276.41 km²; climate and observation controls'),
 (.169,'Radar–optical comparison','2015–2024','Sentinel-1 and Dynamic World; separate retrospective cohorts\nThreshold and recovery-gap sensitivity'),
 (.096,'Dated image comparison','Four selected\nmonths','720 stratified pixel-months; dated Sentinel-2 imagery\nAssisted interpretation; proxy agreement; unknowns retained')]
for y,component,period,basis in rows:
 for x,value in [(.050,component),(.303,period),(.467,basis)]:
  text(x,y,value,fontsize=8.5,va='top',linespacing=1.35)
text(.050,.016,'Separate analysis domains; satellite agreement is not independent accuracy.',fontsize=8.5,color=MUTED)

fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[]
for label in all_labels:
 bounds=label.get_window_extent(renderer)
 if bounds.x0<0 or bounds.y0<0 or bounds.x1>WIDTH_PX or bounds.y1>HEIGHT_PX:outside.append(label.get_text())
assert not outside,('Labels outside figure',outside)
base=OUT/'Figure_01_study_area_and_design'
fig.savefig(base.with_suffix('.png'),dpi=DPI,facecolor='white')
fig.savefig(base.with_suffix('.pdf'),facecolor='white',metadata={'Title':'Study area and analysis domains'})
with Image.open(base.with_suffix('.png')) as im:
 assert im.size==(WIDTH_PX,HEIGHT_PX)
 im.convert('RGB').save(base.with_suffix('.tiff'),dpi=(DPI,DPI),compression='tiff_lzw')
plt.close(fig)
assert hashlib.sha256(INPUTS[0].read_bytes()).hexdigest()==EXPECTED[0]
assert hashlib.sha256(gzip.decompress(INPUTS[1].read_bytes())).hexdigest()==EXPECTED[1]
for rec in scale_records:
 assert all(abs(v-rec['segment_km']*1000*i)<.01 for i,v in enumerate(rec['geodesic_lengths_m'],1))
report={'figure':1,'presentation_only':True,'scientific_results_changed':False,
 'geometry_simplified':False,'projection':CRS_MAP.to_wkt(),'district_label_lon_lat':label_positions,
 'inputs':[{'path':p.relative_to(ROOT).as_posix(),'file_sha256':sha(p),'geometry_bytes_sha256':e} for p,e in zip(INPUTS,EXPECTED)],
 'geodesic_scale_bars':scale_records,'pixels':[WIDTH_PX,HEIGHT_PX],'dpi':DPI,
 'font_family':'Times New Roman','font_file_sha256':sha(font),'minimum_font_size_pt':8.5,
 'caption_unchanged':True,'outside_canvas_labels':outside,'manual_visual_review_required':True,
 'exports':[{'file':p.name,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file()]}
(OUT/'FIGURE1_PROVENANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Figure 1 exported from unchanged verified boundaries to',OUT)
