# 🚀 GUIDE D'INSTALLATION - ZONE 1 Locaux Électriques

## ⚡ Installation Rapide (5 minutes)

### 1️⃣ Prérequis
- Python 3.8 ou supérieur
- Fichier IFC de votre maquette Revit

### 2️⃣ Installation

```bash
# 1. Créer environnement virtuel
python -m venv venv

# 2. Activer l'environnement
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Installer dépendances
pip install -r requirements.txt
```

### 3️⃣ Premier Test

```bash
python main.py --ifc chemin/vers/votre_maquette.ifc
```

Les résultats seront dans `resultats/analysis_results.json` et `.xlsx`

---

## 📁 Structure du Projet

```
zone1_locaux_electriques/
│
├── config/                      # ⚙️ Configuration
│   ├── rules_config.json        # Seuils des règles (MODIFIABLE)
│   └── nomenclature_mapping.json # Mots-clés (MODIFIABLE)
│
├── extractors/                  # 📥 Extraction données IFC
│   ├── ifc_extractor.py         # Lecteur IFC principal
│   └── space_identifier.py      # Identification types espaces
│
├── analyzers/                   #  Analyseurs règles
│   ├── elec_001_weight_checker.py
│   ├── elec_002_ventilation_checker.py
│   ├── elec_003_door_width_checker.py
│   └── elec_004_shower_zone_checker.py
│
├── generators/                  #    Génération rapports
│   └── annotation_generator.py
│
├── utils/                       # 🛠️ Utilitaires
│   ├── logger.py                # Système logs
│   └── geometry_utils.py        # Calculs géométriques
│
├── main.py                      # ▶️ Point d'entrée
├── requirements.txt
└── README.md
```

---

## 🎯 Utilisation

### Commandes de Base

```bash
# Analyse complète
python main.py --ifc maquette.ifc

# Analyser règles spécifiques
python main.py --ifc maquette.ifc --rules ELEC-001 ELEC-003

# Export Excel uniquement
python main.py --ifc maquette.ifc --format excel

# Mode debug (logs détaillés)
python main.py --ifc maquette.ifc --verbose

# Extraction seulement (pas d'analyse)
python main.py --ifc maquette.ifc --extract-only
```

### Fichiers de Sortie

Après exécution, vous trouverez:

1. **`resultats/analysis_results.json`** - Résultats détaillés
2. **`resultats/analysis_results.xlsx`** - Rapport Excel (3 feuilles)
3. **`logs/analysis_YYYYMMDD_HHMMSS.log`** - Journal d'exécution

---

## ⚙️ Configuration

### Modifier les Seuils des Règles

**Fichier:** `config/rules_config.json`

```json
{
  "ELEC-001": {
    "parameters": {
      "weight_threshold_kg": 150,  // ← Changer le seuil de poids
      "safety_margin_percent": 10   // ← Changer la marge de sécurité
    }
  },
  "ELEC-002": {
    "parameters": {
      "min_volume_per_equipment_m3": 10  // ← Volume minimal ventilation
    }
  },
  "ELEC-003": {
    "parameters": {
      "clearance_margin_cm": 20  // ← Marge porte (cm)
    }
  }
}
```

### Ajouter Mots-Clés Nomenclature

**Fichier:** `config/nomenclature_mapping.json`

Si vos maquettes utilisent des noms différents:

```json
{
  "technical_rooms": {
    "keywords_french": [
      "local technique",
      "salle électrique",
      "VOTRE_NOM_ICI"  // ← Ajouter ici
    ]
  },
  "wet_rooms": {
    "keywords_french": [
      "douche",
      "salle de bain",
      "VOTRE_ZONE_HUMIDE"  // ← Ajouter ici
    ]
  }
}
```

---

## 🔧 Dépannage

### Problème 1: `ModuleNotFoundError: No module named 'ifcopenshell'`

**Solution:**
```bash
pip install --upgrade pip
pip install ifcopenshell==0.7.0
```

### Problème 2: Aucun local technique détecté

**Cause:** Les noms dans votre maquette ne correspondent pas aux mots-clés

**Solution:**
1. Ouvrez `logs/analysis_XXX.log`
2. Cherchez les noms de vos locaux
3. Ajoutez-les dans `config/nomenclature_mapping.json`

**Exemple:**
Si vos locaux s'appellent "SALLE TRANSFO" mais ne sont pas détectés:

```json
{
  "technical_rooms": {
    "keywords_french": [
      "salle transfo",  // ← Ajouter ici
      "transformateur"
    ]
  }
}
```

### Problème 3: Fichier IFC ne se charge pas

**Vérifications:**
- Le fichier existe ?
- Extension est bien `.ifc` (pas `.rvt`) ?
- Le fichier n'est pas corrompu ?

**Export IFC depuis Revit:**
1. Fichier → Exporter → IFC
2. Options → IFC 2x3 Coordination View 2.0
3. Exporter

### Problème 4: Poids équipements non détectés

**Cause:** Propriétés poids manquantes dans IFC

**Solutions:**
1. **Dans Revit:** Ajouter propriété "Poids" aux équipements
2. **Dans code:** Le système estime automatiquement depuis type IFC
3. **Manuel:** Ajouter poids typiques dans `config/nomenclature_mapping.json`

```json
{
  "electrical_equipment": {
    "heavy_equipment": {
      "typical_weights_kg": {
        "IfcTransformer": 250,  // ← Ajuster ici
        "VotreType": 180        // ← Ajouter nouveau type
      }
    }
  }
}
```

---

##    Comprendre les Résultats

### Format JSON

```json
{
  "metadata": {
    "timestamp": "2026-02-05T10:30:00",
    "ifc_file": "hospital_ibno_sina.ifc",
    "statistics": {
      "total_violations": 12,
      "critical": 3,
      "important": 9
    }
  },
  "violations": [
    {
      "rule_id": "ELEC-001",
      "severity": "CRITICAL",
      "space_name": "Local Technique Niveau 2",
      "description": "Poids équipement dépasse capacité dalle",
      "details": {
        "total_weight_kg": 180,
        "slab_capacity_kg": 150,
        "excess_kg": 30
      },
      "location": [12.5, 8.3, 3.0],
      "recommendation": "Renforcement dalle ou redistribution charge"
    }
  ]
}
```

### Format Excel

**Feuille 1: Violations** - Liste détaillée
**Feuille 2: Statistiques** - Résumé global
**Feuille 3: Par Règle** - Comptage par règle

---

## 🎓 Exemple Complet

```bash
# 1. Activer environnement
source venv/bin/activate

# 2. Analyser maquette
python main.py --ifc maquettes/hopital_niveau1.ifc --output rapports/analyse_n1.xlsx

# 3. Consulter logs si problème
cat logs/analysis_*.log

# 4. Modifier config si nécessaire
nano config/rules_config.json

# 5. Relancer
python main.py --ifc maquettes/hopital_niveau1.ifc --output rapports/analyse_n1_v2.xlsx
```

---

## 💡 Astuces

### Analyser Plusieurs Maquettes

```bash
# Script batch
for file in maquettes/*.ifc; do
    python main.py --ifc "$file" --output "rapports/$(basename $file .ifc).xlsx"
done
```

### Désactiver une Règle

Dans `config/rules_config.json`:

```json
{
  "ELEC-002": {
    "enabled": false  // ← Désactiver ici
  }
}
```

### Logs Plus Détaillés

```bash
python main.py --ifc maquette.ifc --verbose > analyse_detaillee.log 2>&1
```

---

## ❓ Support

**Email:** votre_email@example.com  
**Documentation:** Voir `README.md`  
**Exemples:** Voir `exemple_utilisation.py`

---

##   Checklist Avant Production

- [ ] Installer toutes dépendances (`pip install -r requirements.txt`)
- [ ] Tester sur maquette exemple
- [ ] Adapter nomenclature à votre projet (`config/nomenclature_mapping.json`)
- [ ] Vérifier seuils règles (`config/rules_config.json`)
- [ ] Valider résultats avec encadrant
- [ ] Documenter personnalisations

---

**Version:** 1.0  
**Dernière mise à jour:** 05/02/2026  
**Projet:** IBNO SINA - Stage 2026
