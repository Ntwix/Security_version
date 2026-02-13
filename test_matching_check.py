"""Quick check: equipment matching after geometry fix"""
import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor import IFCExtractor
from utils.geometry_utils import GeometryUtils

e = IFCExtractor("maquettes/Ibn_Sina_ARCHI.ifc", "maquettes/Ibn_Sina_ELEC.ifc")
d = e.extract_all()

# Count matching
total_matched = 0
for s in d['spaces']:
    count = sum(1 for eq in d['equipment']
                if GeometryUtils.is_point_in_bbox(eq['centroid'], s['bbox_min'], s['bbox_max']))
    total_matched += count

print(f"\nTotal equipements matches: {total_matched}/{len(d['equipment'])}")
print(f"Pourcentage: {100*total_matched/len(d['equipment']):.1f}%")

# Show matching for technical rooms
print("\n--- Locaux techniques ---")
for s in d['spaces']:
    if 'ITEC' in s['name']:
        count = sum(1 for eq in d['equipment']
                    if GeometryUtils.is_point_in_bbox(eq['centroid'], s['bbox_min'], s['bbox_max']))
        if count > 0:
            print(f"  {s['name']}: {count} equip, vol={s['volume_m3']}m3, area={s['floor_area_m2']}m2")

# Show first few doors
print("\n--- Portes (5 premieres) ---")
for door in d['doors'][:5]:
    print(f"  {door['name'][:50]}: largeur={door['width_m']:.3f}m, hauteur={door['height_m']:.3f}m")
