"""
Verification: est-ce que les donnees sont bien presentes pour les analyseurs?
- ELEC-003: equipements dans locaux techniques + portes avec dimensions
- ELEC-004: equipements dans zones humides + proprietes IP/materiau
"""
import sys
sys.path.insert(0, '.')
from extractors.ifc_extractor import IFCExtractor
from extractors.space_identifier import SpaceIdentifier
from utils.geometry_utils import GeometryUtils

# Charger
extractor = IFCExtractor(
    "maquettes/Ibn_Sina_ARCHI.ifc",
    "maquettes/Ibn_Sina_ELEC.ifc"
)
data = extractor.extract_all()

identifier = SpaceIdentifier()
classified = identifier.classify_all_spaces(data['spaces'])

print("=" * 70)
print("VERIFICATION ELEC-003 : Equipements dans locaux techniques + Portes")
print("=" * 70)

tech_rooms = classified.get('local_technique', [])
equipment = data['equipment']
doors = data['doors']

# Compter equipements par local technique
tech_with_eq = 0
tech_with_doors = 0

for space in tech_rooms[:20]:  # 20 premiers
    space_eq = []
    for eq in equipment:
        if GeometryUtils.is_point_in_bbox(eq['centroid'], space['bbox_min'], space['bbox_max']):
            space_eq.append(eq)

    space_doors = []
    tolerance = 0.5
    for door in doors:
        dc = door['centroid']
        in_x = (space['bbox_min'][0] - tolerance <= dc[0] <= space['bbox_max'][0] + tolerance)
        in_y = (space['bbox_min'][1] - tolerance <= dc[1] <= space['bbox_max'][1] + tolerance)
        in_z = (space['bbox_min'][2] - tolerance <= dc[2] <= space['bbox_max'][2] + tolerance)
        if in_x and in_y and in_z:
            space_doors.append(door)

    if space_eq:
        tech_with_eq += 1
    if space_doors:
        tech_with_doors += 1

    print(f"\n  {space['name']} ({space.get('long_name', '')})")
    print(f"    Equipements: {len(space_eq)}")
    for eq in space_eq[:3]:
        print(f"      - {eq['name']} (type={eq['ifc_type']}, max_dim={eq.get('max_dimension_m', '?')}m, diag={eq.get('diagonal_dimension_m', '?')}m)")
    if len(space_eq) > 3:
        print(f"      ... et {len(space_eq) - 3} autres")

    print(f"    Portes: {len(space_doors)}")
    for d in space_doors:
        print(f"      - {d['name']} (largeur={d['width_m']}m, hauteur={d['height_m']}m)")

print(f"\n  RESUME ELEC-003:")
print(f"    Locaux techniques: {len(tech_rooms)}")
print(f"    Avec equipements (20 premiers): {tech_with_eq}")
print(f"    Avec portes (20 premiers): {tech_with_doors}")

print("\n" + "=" * 70)
print("VERIFICATION ELEC-004 : Equipements dans zones humides + proprietes")
print("=" * 70)

wet_rooms = classified.get('zone_humide', [])
cuisine = classified.get('cuisine_restauration', [])
laverie = classified.get('laverie_menage', [])
all_wet = wet_rooms + cuisine + laverie

wet_with_eq = 0
for space in all_wet[:15]:  # 15 premiers
    space_eq = []
    for eq in equipment:
        if GeometryUtils.is_point_in_bbox(eq['centroid'], space['bbox_min'], space['bbox_max']):
            space_eq.append(eq)

    if space_eq:
        wet_with_eq += 1

    cat = space.get('category', '?')
    print(f"\n  {space['name']} ({space.get('long_name', '')}) [{cat}]")
    print(f"    Equipements: {len(space_eq)}")
    for eq in space_eq[:3]:
        props = eq.get('properties', {})
        ip = None
        mat = None
        for k in ['IPRating', 'IP_Rating', 'Protection', 'ProtectionIndex']:
            if k in props:
                ip = props[k]
        for k in ['Material', 'Materiau', 'FinishMaterial']:
            if k in props:
                mat = props[k]
        print(f"      - {eq['name']} (type={eq['ifc_type']}, IP={ip}, Material={mat})")
        if props:
            print(f"        Proprietes: {list(props.keys())[:5]}")
    if len(space_eq) > 3:
        print(f"      ... et {len(space_eq) - 3} autres")

print(f"\n  RESUME ELEC-004:")
print(f"    Zones humides totales: {len(all_wet)}")
print(f"    Avec equipements (15 premiers): {wet_with_eq}")

# Exemples de proprietes d'equipements
print("\n" + "=" * 70)
print("ECHANTILLON PROPRIETES EQUIPEMENTS (10 premiers)")
print("=" * 70)
for eq in equipment[:10]:
    props = eq.get('properties', {})
    print(f"\n  {eq['name']} ({eq['ifc_type']})")
    print(f"    weight_kg: {eq.get('weight_kg', 'N/A')}")
    print(f"    max_dim: {eq.get('max_dimension_m', 'N/A')}m")
    if props:
        for k, v in list(props.items())[:5]:
            print(f"    {k}: {v}")
    else:
        print(f"    (aucune propriete)")

# Portes - echantillon
print("\n" + "=" * 70)
print("ECHANTILLON PORTES (10 premieres)")
print("=" * 70)
for d in doors[:10]:
    print(f"  {d['name']}: largeur={d['width_m']}m, hauteur={d['height_m']}m")
