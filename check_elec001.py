import json

with open('resultats/zone1/analysis_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

elec001 = [v for v in data['violations'] if v['rule_id'] == 'ELEC-001']
print(f"=== ELEC-001 : {len(elec001)} violations ===\n")

for v in elec001:
    print(f"Space: {v['space_name']}")
    print(f"  Severite: {v['severity']}")
    print(f"  Description: {v['description']}")
    if 'details' in v:
        d = v['details']
        print(f"  Poids total: {d.get('total_weight_kg', '?')} kg")
        print(f"  Capacite dalle: {d.get('slab_capacity_kg', '?')} kg")
        print(f"  Nb equipements: {d.get('equipment_count', '?')}")
        eq_list = d.get('equipment_list', [])
        if eq_list:
            print(f"  Equipements avec poids:")
            for eq in eq_list[:5]:
                print(f"    - {eq['name']}: {eq['weight_kg']} kg")
    print()

# Verifier les donnees brutes
print("\n=== DONNEES BRUTES : poids des equipements ===")
with open('extracted_data.json', 'r', encoding='utf-8') as f:
    extracted = json.load(f)

equips = extracted['equipment']
with_weight = [e for e in equips if e.get('weight_kg') is not None]
without_weight = [e for e in equips if e.get('weight_kg') is None]
print(f"Total equipements: {len(equips)}")
print(f"Avec poids renseigne: {len(with_weight)}")
print(f"Sans poids (null): {len(without_weight)}")

# Verifier les proprietes pour des mots-cles poids
print("\n=== Recherche proprietes liees au poids ===")
weight_keys = set()
for eq in equips[:200]:
    props = eq.get('properties', {})
    if isinstance(props, list):
        for p in props:
            key = p.get('Key', '')
            if any(w in key.lower() for w in ['poids', 'weight', 'mass', 'masse', 'charge', 'kg']):
                weight_keys.add(key)
    elif isinstance(props, dict):
        for key in props:
            if any(w in key.lower() for w in ['poids', 'weight', 'mass', 'masse', 'charge', 'kg']):
                weight_keys.add(key)

if weight_keys:
    print(f"Cles trouvees: {weight_keys}")
else:
    print("Aucune propriete de poids trouvee dans les 200 premiers equipements")
