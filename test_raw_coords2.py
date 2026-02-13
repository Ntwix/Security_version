"""Check actual dimensions of spaces - are they in cm or what?"""
import ifcopenshell
import ifcopenshell.geom

ifc = ifcopenshell.open("maquettes/Ibn_Sina_ARCHI.ifc")

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

spaces = ifc.by_type("IfcSpace")

# Check a few spaces with known types
print("--- Sample spaces (USE_WORLD_COORDS=True) ---")
for space in spaces[:10]:
    try:
        shape = ifcopenshell.geom.create_shape(settings, space)
        verts = shape.geometry.verts

        x = [verts[i] for i in range(0, len(verts), 3)]
        y = [verts[i] for i in range(1, len(verts), 3)]
        z = [verts[i] for i in range(2, len(verts), 3)]

        dx = max(x) - min(x)
        dy = max(y) - min(y)
        dz = max(z) - min(z)

        ln = getattr(space, 'LongName', '') or ''
        print(f"  {space.Name} ({ln}):")
        print(f"    dims: {dx:.2f} x {dy:.2f} x {dz:.2f}")
        print(f"    if cm: {dx*0.01:.2f}m x {dy*0.01:.2f}m x {dz*0.01:.2f}m")
        print(f"    if as-is (m): {dx:.2f}m x {dy:.2f}m x {dz:.2f}m")
    except:
        pass

# Check: what does ifcopenshell.geom CONVERT_BACK_UNITS do?
print("\n--- Testing with CONVERT_BACK_UNITS ---")
settings3 = ifcopenshell.geom.settings()
settings3.set(settings3.USE_WORLD_COORDS, True)
try:
    settings3.set(settings3.CONVERT_BACK_UNITS, True)
    space = spaces[0]
    shape3 = ifcopenshell.geom.create_shape(settings3, space)
    verts3 = shape3.geometry.verts

    x3 = [verts3[i] for i in range(0, len(verts3), 3)]
    y3 = [verts3[i] for i in range(1, len(verts3), 3)]
    z3 = [verts3[i] for i in range(2, len(verts3), 3)]

    dx3 = max(x3) - min(x3)
    dy3 = max(y3) - min(y3)
    dz3 = max(z3) - min(z3)

    print(f"  {spaces[0].Name} with CONVERT_BACK_UNITS:")
    print(f"    dims: {dx3:.4f} x {dy3:.4f} x {dz3:.4f}")
    print(f"    bbox: ({min(x3):.2f}, {min(y3):.2f}, {min(z3):.2f}) -> ({max(x3):.2f}, {max(y3):.2f}, {max(z3):.2f})")
except Exception as e:
    print(f"  CONVERT_BACK_UNITS error: {e}")
