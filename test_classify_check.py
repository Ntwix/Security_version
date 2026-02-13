"""Quick check: classify spaces from extractor"""
import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor_v2 import IFCExtractor
from extractors.space_identifier import SpaceIdentifier

extractor = IFCExtractor(
    "maquettes/Ibn_Sina_ARCHI.ifc",
    "maquettes/Ibn_Sina_ELEC.ifc"
)
data = extractor.extract_all()

identifier = SpaceIdentifier()
classified = identifier.classify_all_spaces(data['spaces'])

print(f"\nClassification result:")
for cat, spaces in sorted(classified.items()):
    print(f"  {cat}: {len(spaces)}")

# Show some non-classified
non_class = classified.get('non_classifie', [])
if non_class:
    print(f"\nExemples non classifies (10 premiers):")
    for s in non_class[:10]:
        print(f"  name='{s['name']}' long_name='{s.get('long_name', 'N/A')}'")
