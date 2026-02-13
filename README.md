#  ZONE 1 - Automatisation Annotations Locaux Électriques

##  Description
Système d'analyse automatique des maquettes 3D (Revit/IFC) pour détecter les non-conformités de sécurité dans les **locaux électriques** selon le guide de sécurité IBNO SINA.

##  Règles Implémentées

| Code | Règle | Priorité | Statut |
|------|-------|----------|--------|
| ELEC-001 | Poids équipements vs capacité dalle |   Critique |   Implémenté |
| ELEC-002 | Volume ventilation locaux techniques |   Important |   Implémenté |
| ELEC-003 | Largeur porte vs équipement |   Important |   Implémenté |
| ELEC-004 | Zones humides (douches) - IP65 requis |   Critique |   Implémenté |

##  Architecture du Projet

```
zone1_locaux_electriques/
│
├── config/                          # Configuration et mappings
│   ├── rules_config.json           # Paramètres des règles (seuils, etc.)
│   └── nomenclature_mapping.json   # Mapping noms Revit → Catégories
│
├── extractors/                      # Extraction données IFC/Revit
│   ├── ifc_extractor.py            # Extraction éléments depuis IFC
│   └── space_identifier.py         # Identification types d'espaces
│
├── analyzers/                       # Analyseurs de règles
│   ├── elec_001_weight_checker.py  # Vérification poids équipements
│   ├── elec_002_ventilation_checker.py
│   ├── elec_003_door_width_checker.py
│   └── elec_004_shower_zone_checker.py
│
├── generators/                      # Génération annotations
│   └── annotation_generator.py     # Génère JSON d'annotations
│
├── utils/                          # Utilitaires
│   ├── logger.py                   # Logging centralisé
│   └── geometry_utils.py           # Calculs géométriques
│
├── main.py                         # Point d'entrée principal
├── requirements.txt                # Dépendances Python
└── README.md                       # Documentation
```

##  Installation

```bash
# 1. Créer environnement virtuel
python -m venv venv

# 2. Activer l'environnement
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Installer dépendances
pip install -r requirements.txt
```

##  Utilisation

### Extraction et Analyse Complète

```bash
python main.py --ifc chemin/vers/maquette.ifc --output resultats.json
```

### Options Avancées

```bash
# Analyser une règle spécifique
python main.py --ifc maquette.ifc --rules ELEC-001 ELEC-003

# Mode verbose (debug)
python main.py --ifc maquette.ifc --verbose

# Générer rapport Excel
python main.py --ifc maquette.ifc --output resultats.xlsx --format excel
```

##    Format de Sortie

```json
{
  "metadata": {
    "timestamp": "2026-02-05T10:30:00",
    "ifc_file": "hospital_projet_ibno_sina.ifc",
    "rules_analyzed": ["ELEC-001", "ELEC-002", "ELEC-003", "ELEC-004"]
  },
  "violations": [
    {
      "rule_id": "ELEC-001",
      "severity": "CRITICAL",
      "space_name": "Local Technique Électrique - Niveau 2",
      "description": "Poids équipement dépasse capacité dalle",
      "details": {
        "equipment_weight_kg": 180,
        "slab_capacity_kg": 150,
        "excess_kg": 30
      },
      "location": {
        "x": 12.5,
        "y": 8.3,
        "z": 3.0
      },
      "recommendation": "Renforcement dalle ou redistribution charge requise"
    }
  ],
  "statistics": {
    "total_spaces_analyzed": 45,
    "total_violations": 12,
    "critical": 3,
    "important": 9
  }
}
```

## 🔧 Configuration

### Modifier les Seuils (config/rules_config.json)

```json
{
  "ELEC-001": {
    "weight_threshold_kg": 150,  // ← Modifiable ici
    "safety_margin": 0.1
  }
}
```

### Adapter la Nomenclature (config/nomenclature_mapping.json)

Si vos maquettes utilisent des noms différents :

```json
{
  "technical_rooms": [
    "local technique",
    "salle électrique",
    "your_custom_name_here"  // ← Ajouter ici
  ]
}
```

##  Tests

```bash
# Tester sur maquette d'exemple
python main.py --ifc exemples/sample.ifc --test

# Vérifier extraction uniquement (sans analyse)
python main.py --ifc maquette.ifc --extract-only
```

##  Évolutions Futures

- [ ] ZONE 2 - Gaines techniques verticales
- [ ] ZONE 3 - Faux plafonds techniques
- [ ] Export PDF avec visualisations 3D
- [ ] Interface web pour visualisation interactive
- [ ] Intégration API Revit (réinjection annotations)

##  Contribution

Développé dans le cadre du projet pilote IBNO SINA

##   License

Projet académique - Stage 2026
