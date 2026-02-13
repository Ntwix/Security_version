import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor import IFCExtractor
from utils.geometry_utils import GeometryUtils

e = IFCExtractor("maquettes/Ibn_Sina_ARCHI.ifc", "maquettes/Ibn_Sina_ELEC.ifc")
d = e.extract_all()

print(f"\nScale archi={e.unit_scale_archi} elec={e.unit_scale_elec}")
print(f"Offset ELEC: dx={e.offset_elec[0]:.4f} dy={e.offset_elec[1]:.4f} dz={e.offset_elec[2]:.4f}")

# 3 premiers spaces
print("\n--- 3 premiers Spaces ---")
for s in d['spaces'][:3]:
    print(f"  {s['name']} ({s.get('long_name','')})")
    print(f"    bbox=({s['bbox_min'][0]:.3f}, {s['bbox_min'][1]:.3f}, {s['bbox_min'][2]:.3f}) -> ({s['bbox_max'][0]:.3f}, {s['bbox_max'][1]:.3f}, {s['bbox_max'][2]:.3f})")
    print(f"    centroid=({s['centroid'][0]:.3f}, {s['centroid'][1]:.3f}, {s['centroid'][2]:.3f})")

# 3 premiers equipements
print("\n--- 3 premiers Equipements ---")
for eq in d['equipment'][:3]:
    print(f"  {eq['name'][:50]}")
    print(f"    centroid=({eq['centroid'][0]:.3f}, {eq['centroid'][1]:.3f}, {eq['centroid'][2]:.3f})")

# 3 premieres portes
print("\n--- 3 premieres Portes ---")
for door in d['doors'][:3]:
    print(f"  {door['name'][:50]}")
    print(f"    largeur={door['width_m']:.3f}m, hauteur={door['height_m']:.3f}m")
    print(f"    centroid=({door['centroid'][0]:.3f}, {door['centroid'][1]:.3f}, {door['centroid'][2]:.3f})")

# Test matching
print("\n--- Test matching equipements/spaces ---")
for s in d['spaces'][:5]:
    count = sum(1 for eq in d['equipment'] if GeometryUtils.is_point_in_bbox(eq['centroid'], s['bbox_min'], s['bbox_max']))
    if count > 0:
        print(f"  {s['name']} ({s.get('long_name','')}): {count} equipements")

# Compter total
total_matched = 0
for s in d['spaces']:
    count = sum(1 for eq in d['equipment'] if GeometryUtils.is_point_in_bbox(eq['centroid'], s['bbox_min'], s['bbox_max']))
    total_matched += count
print(f"\n  Total equipements matches: {total_matched}/{len(d['equipment'])}")
