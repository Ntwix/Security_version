# CHU Ibn Sina - Analyseur de Conformité Sécurité BIM

Système d'analyse automatique des maquettes 3D (Revit/IFC) pour détecter les non-conformités de sécurité dans le cadre du projet CHU Ibn Sina.

## Catégories Analysées

| Catégorie | Domaine | Règles |
|-----------|---------|--------|
| Catégorie 1 | Locaux Électriques | ELEC-001 à ELEC-004 |
| Catégorie 2 | Gaines Techniques | GAINE-001 à GAINE-005 |
| Catégorie 3 | Faux Plafonds Techniques | FPLAF-001 à FPLAF-003 |
| Catégorie 4 | Planchers Techniques | PLAN-001 à PLAN-005 |
| Catégorie 5 | Risques Chantier | CHANT-001 à CHANT-005 |

## Architecture

```
CHU_SecurityAnalyzer/
├── main.py                          # Point d'entrée principal
├── requirements.txt                 # Dépendances Python
├── CHU_SecurityAnalyzer.sln         # Solution Visual Studio
│
├── shared/                          # Modules partagés
│   ├── logger.py
│   ├── ifc_extractor.py
│   └── annotation_generator.py
│
├── categories/                      # Analyseurs par catégorie
│   ├── categorie1_locaux_electriques/
│   ├── categorie2_gaines_techniques/
│   ├── categorie3_faux_plafonds_techniques/
│   ├── categorie4_planchers_techniques/
│   └── categorie5_risques_chantier/
│
├── RevitPlugin/                     # Plugin C# Revit
│   └── CHU_SecurityAnalyzer/
│
├── maquettes/                       # Fichiers IFC
├── resultats/                       # Sorties générées
└── logs/                            # Fichiers de logs
```

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Utilisation

```bash
# Analyser une catégorie spécifique
python main.py --zone 1 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc

# Analyser toutes les catégories
python main.py --zone all --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc

# Règles spécifiques uniquement
python main.py --zone 2 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --rules GAINE-001 GAINE-003
```

## Projet

Stage 2026 - CHU Ibn Sina
