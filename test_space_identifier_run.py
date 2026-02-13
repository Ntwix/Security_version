from extractors.space_identifier import SpaceIdentifier

identifier = SpaceIdentifier()

# Sample: technical room
space_tech = {
    "name": "Local Technique Électrique - Niveau 2",
    "description": "Salle TGBT",
    "object_type": "ElectricalRoom",
    "ifc_type": "IfcSpace",
    "predefined_type": "ELECTRICALROOM"
}

# Sample: wet room
space_wet = {
    "name": "Salle de bain personnel",
    "description": "Sanitaires avec douche",
    "object_type": "Bathroom",
    "ifc_type": "IfcSpace",
    "predefined_type": "BATHROOM"
}

print('Technical sample ->', identifier.identify_space_type(space_tech))
print('Wet sample       ->', identifier.identify_space_type(space_wet))
