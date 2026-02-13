"""Diagnostic: why volume_m3 = 0.0 for technical spaces?"""
import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor import IFCExtractor

extractor = IFCExtractor(
    "maquettes/Ibn_Sina_ARCHI.ifc",
    "maquettes/Ibn_Sina_ELEC.ifc"
)
data = extractor.extract_all()

# Check DOM-ITEC spaces (local technique)
print("\n--- Locaux Techniques (DOM-ITEC) ---")
for s in data['spaces']:
    if 'ITEC' in s['name']:
        dx = s['bbox_max'][0] - s['bbox_min'][0]
        dy = s['bbox_max'][1] - s['bbox_min'][1]
        dz = s['bbox_max'][2] - s['bbox_min'][2]
        print(f"  {s['name']}:")
        print(f"    bbox_min=({s['bbox_min'][0]:.4f}, {s['bbox_min'][1]:.4f}, {s['bbox_min'][2]:.4f})")
        print(f"    bbox_max=({s['bbox_max'][0]:.4f}, {s['bbox_max'][1]:.4f}, {s['bbox_max'][2]:.4f})")
        print(f"    dims: dx={dx:.4f}m, dy={dy:.4f}m, dz={dz:.4f}m")
        print(f"    volume={s['volume_m3']}m3, area={s['floor_area_m2']}m2, height={s['height_m']}m")
