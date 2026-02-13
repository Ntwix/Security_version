"""Quick check: what long_names does ifc_extractor_v2 produce?"""
import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor_v2 import IFCExtractor

extractor = IFCExtractor(
    "maquettes/Ibn_Sina_ARCHI.ifc",
    "maquettes/Ibn_Sina_ELEC.ifc"
)
data = extractor.extract_all()

# Check long_name values
from collections import Counter
long_names = Counter(s.get('long_name', '') for s in data['spaces'])
print(f"\nTotal spaces: {len(data['spaces'])}")
print(f"\nLongName distribution:")
for ln, count in long_names.most_common():
    print(f"  [{count:3d}x] '{ln}' (type={type(ln).__name__}, len={len(ln)})")
