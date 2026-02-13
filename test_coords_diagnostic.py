"""
Diagnostic coordonnees : comparer les referentiels ARCHI vs ELEC
"""
import ifcopenshell
import ifcopenshell.geom

# === 1. Charger les 2 fichiers ===
print("=" * 70)
print("DIAGNOSTIC COORDONNEES ARCHI vs ELEC")
print("=" * 70)

archi = ifcopenshell.open("maquettes/Ibn_Sina_ARCHI.ifc")
elec = ifcopenshell.open("maquettes/Ibn_Sina_ELEC.ifc")

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# === 2. Verifier les unites ===
print("\n--- UNITES ---")
for label, f in [("ARCHI", archi), ("ELEC", elec)]:
    units = f.by_type("IfcUnitAssignment")
    if units:
        for unit_assign in units:
            for unit in unit_assign.Units:
                if hasattr(unit, 'UnitType') and unit.UnitType == 'LENGTHUNIT':
                    name = getattr(unit, 'Name', '?')
                    prefix = getattr(unit, 'Prefix', None)
                    print(f"  {label}: UnitType=LENGTHUNIT, Name={name}, Prefix={prefix}")

# === 3. Verifier IfcSite / IfcProject placement ===
print("\n--- SITE PLACEMENT ---")
for label, f in [("ARCHI", archi), ("ELEC", elec)]:
    sites = f.by_type("IfcSite")
    for site in sites:
        if hasattr(site, 'RefLatitude'):
            print(f"  {label} Site: Lat={site.RefLatitude}, Lon={site.RefLongitude}")
        if hasattr(site, 'ObjectPlacement') and site.ObjectPlacement:
            placement = site.ObjectPlacement
            if hasattr(placement, 'RelativePlacement') and placement.RelativePlacement:
                rp = placement.RelativePlacement
                if hasattr(rp, 'Location') and rp.Location:
                    coords = rp.Location.Coordinates
                    print(f"  {label} Site Origin: ({coords[0]}, {coords[1]}, {coords[2]})")

# === 4. Comparer les bounding boxes globales ===
print("\n--- BOUNDING BOX GLOBALE ---")

def get_global_bbox(ifc_file, ifc_type, settings, max_elements=50):
    """Calcule la bounding box globale pour un type d'element"""
    elements = ifc_file.by_type(ifc_type)
    all_x, all_y, all_z = [], [], []
    count = 0
    for elem in elements[:max_elements]:
        try:
            shape = ifcopenshell.geom.create_shape(settings, elem)
            verts = shape.geometry.verts
            xs = [verts[i] for i in range(0, len(verts), 3)]
            ys = [verts[i] for i in range(1, len(verts), 3)]
            zs = [verts[i] for i in range(2, len(verts), 3)]
            all_x.extend(xs)
            all_y.extend(ys)
            all_z.extend(zs)
            count += 1
        except:
            pass
    if all_x:
        return {
            'min': (min(all_x), min(all_y), min(all_z)),
            'max': (max(all_x), max(all_y), max(all_z)),
            'count': count
        }
    return None

# Spaces (ARCHI)
print("\n  ARCHI - IfcSpace (50 premiers):")
bbox_spaces = get_global_bbox(archi, "IfcSpace", settings, 50)
if bbox_spaces:
    print(f"    Min: ({bbox_spaces['min'][0]:.2f}, {bbox_spaces['min'][1]:.2f}, {bbox_spaces['min'][2]:.2f})")
    print(f"    Max: ({bbox_spaces['max'][0]:.2f}, {bbox_spaces['max'][1]:.2f}, {bbox_spaces['max'][2]:.2f})")
    print(f"    ({bbox_spaces['count']} elements)")

# Doors (ARCHI)
print("\n  ARCHI - IfcDoor (50 premiers):")
bbox_doors = get_global_bbox(archi, "IfcDoor", settings, 50)
if bbox_doors:
    print(f"    Min: ({bbox_doors['min'][0]:.2f}, {bbox_doors['min'][1]:.2f}, {bbox_doors['min'][2]:.2f})")
    print(f"    Max: ({bbox_doors['max'][0]:.2f}, {bbox_doors['max'][1]:.2f}, {bbox_doors['max'][2]:.2f})")
    print(f"    ({bbox_doors['count']} elements)")

# Equipment (ELEC)
print("\n  ELEC - IfcProduct electriques (50 premiers):")
all_products = elec.by_type("IfcProduct")
elec_products = []
for p in all_products:
    name = str(p.Name or "").lower()
    keywords = ['elec', 'light', 'lampe', 'transfo', 'armoire',
                'tableau', 'prise', 'inter', 'switch']
    if any(kw in name for kw in keywords):
        elec_products.append(p)

all_x, all_y, all_z = [], [], []
count = 0
for elem in elec_products[:50]:
    try:
        shape = ifcopenshell.geom.create_shape(settings, elem)
        verts = shape.geometry.verts
        xs = [verts[i] for i in range(0, len(verts), 3)]
        ys = [verts[i] for i in range(1, len(verts), 3)]
        zs = [verts[i] for i in range(2, len(verts), 3)]
        all_x.extend(xs)
        all_y.extend(ys)
        all_z.extend(zs)
        count += 1
    except:
        pass

if all_x:
    print(f"    Min: ({min(all_x):.2f}, {min(all_y):.2f}, {min(all_z):.2f})")
    print(f"    Max: ({max(all_x):.2f}, {max(all_y):.2f}, {max(all_z):.2f})")
    print(f"    ({count} elements)")

# === 5. Exemples de coordonnees specifiques ===
print("\n--- EXEMPLES COORDONNEES ---")

# 3 premiers espaces ARCHI
spaces = archi.by_type("IfcSpace")
print("\n  3 premiers IfcSpace (ARCHI):")
for space in spaces[:3]:
    try:
        shape = ifcopenshell.geom.create_shape(settings, space)
        verts = shape.geometry.verts
        xs = [verts[i] for i in range(0, len(verts), 3)]
        ys = [verts[i] for i in range(1, len(verts), 3)]
        zs = [verts[i] for i in range(2, len(verts), 3)]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        cz = (min(zs) + max(zs)) / 2
        name = space.Name or "?"
        ln = getattr(space, 'LongName', '') or ""
        print(f"    {name} ({ln}): centroid=({cx:.2f}, {cy:.2f}, {cz:.2f})")
    except:
        pass

# 3 premiers equipements ELEC
print("\n  3 premiers equipements (ELEC):")
for elem in elec_products[:3]:
    try:
        shape = ifcopenshell.geom.create_shape(settings, elem)
        verts = shape.geometry.verts
        xs = [verts[i] for i in range(0, len(verts), 3)]
        ys = [verts[i] for i in range(1, len(verts), 3)]
        zs = [verts[i] for i in range(2, len(verts), 3)]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        cz = (min(zs) + max(zs)) / 2
        print(f"    {elem.Name}: centroid=({cx:.2f}, {cy:.2f}, {cz:.2f})")
    except:
        pass

# === 6. Calculer le decalage potentiel ===
print("\n--- DECALAGE ESTIME ---")
if bbox_spaces and all_x:
    dx = ((min(all_x) + max(all_x))/2) - ((bbox_spaces['min'][0] + bbox_spaces['max'][0])/2)
    dy = ((min(all_y) + max(all_y))/2) - ((bbox_spaces['min'][1] + bbox_spaces['max'][1])/2)
    dz = ((min(all_z) + max(all_z))/2) - ((bbox_spaces['min'][2] + bbox_spaces['max'][2])/2)
    print(f"  Centre ARCHI spaces: ({(bbox_spaces['min'][0]+bbox_spaces['max'][0])/2:.2f}, {(bbox_spaces['min'][1]+bbox_spaces['max'][1])/2:.2f}, {(bbox_spaces['min'][2]+bbox_spaces['max'][2])/2:.2f})")
    print(f"  Centre ELEC equip:   ({(min(all_x)+max(all_x))/2:.2f}, {(min(all_y)+max(all_y))/2:.2f}, {(min(all_z)+max(all_z))/2:.2f})")
    print(f"  Decalage estime: dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f}")

    # Verifier si les ranges se chevauchent
    overlap_x = bbox_spaces['min'][0] <= max(all_x) and min(all_x) <= bbox_spaces['max'][0]
    overlap_y = bbox_spaces['min'][1] <= max(all_y) and min(all_y) <= bbox_spaces['max'][1]
    overlap_z = bbox_spaces['min'][2] <= max(all_z) and min(all_z) <= bbox_spaces['max'][2]
    print(f"  Chevauchement X: {overlap_x}")
    print(f"  Chevauchement Y: {overlap_y}")
    print(f"  Chevauchement Z: {overlap_z}")

print("\n  Diagnostic termine")
