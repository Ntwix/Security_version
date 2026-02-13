"""Check: does ifcopenshell.geom already convert to meters?"""
import ifcopenshell
import ifcopenshell.geom

ifc = ifcopenshell.open("maquettes/Ibn_Sina_ARCHI.ifc")

# Check length unit
units = ifc.by_type("IfcUnitAssignment")
for ua in units:
    for u in ua.Units:
        if hasattr(u, 'UnitType') and u.UnitType == 'LENGTHUNIT':
            print(f"LENGTHUNIT: Name={u.Name}, Prefix={getattr(u, 'Prefix', None)}")

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

# Get first space
spaces = ifc.by_type("IfcSpace")
space = spaces[0]
print(f"\nSpace: {space.Name}")

shape = ifcopenshell.geom.create_shape(settings, space)
verts = shape.geometry.verts

x_coords = [verts[i] for i in range(0, len(verts), 3)]
y_coords = [verts[i] for i in range(1, len(verts), 3)]
z_coords = [verts[i] for i in range(2, len(verts), 3)]

print(f"Raw bbox: ({min(x_coords):.2f}, {min(y_coords):.2f}, {min(z_coords):.2f})")
print(f"       -> ({max(x_coords):.2f}, {max(y_coords):.2f}, {max(z_coords):.2f})")
print(f"Raw dims: dx={max(x_coords)-min(x_coords):.2f}, dy={max(y_coords)-min(y_coords):.2f}, dz={max(z_coords)-min(z_coords):.2f}")

# Now test WITHOUT USE_WORLD_COORDS
settings2 = ifcopenshell.geom.settings()
shape2 = ifcopenshell.geom.create_shape(settings2, space)
verts2 = shape2.geometry.verts

x2 = [verts2[i] for i in range(0, len(verts2), 3)]
y2 = [verts2[i] for i in range(1, len(verts2), 3)]
z2 = [verts2[i] for i in range(2, len(verts2), 3)]

print(f"\nWithout USE_WORLD_COORDS:")
print(f"Raw bbox: ({min(x2):.2f}, {min(y2):.2f}, {min(z2):.2f})")
print(f"       -> ({max(x2):.2f}, {max(y2):.2f}, {max(z2):.2f})")
print(f"Raw dims: dx={max(x2)-min(x2):.2f}, dy={max(y2)-min(y2):.2f}, dz={max(z2)-min(z2):.2f}")

# Check the OverallWidth of first door for reference
doors = ifc.by_type("IfcDoor")
if doors:
    d = doors[0]
    print(f"\nDoor: {d.Name}")
    print(f"  OverallWidth={d.OverallWidth}, OverallHeight={d.OverallHeight}")
    print(f"  OverallWidth is in IFC units (cm), so {d.OverallWidth}cm = {d.OverallWidth*0.01}m")
