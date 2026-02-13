#    MISE À JOUR : Support 2 Fichiers IFC

##   NOUVELLE FONCTIONNALITÉ

Le programme supporte maintenant **2 fichiers IFC** pour fusionner Architecture + Électrique !

---

## 🚀 UTILISATION

### **Option 1 : 2 fichiers (Archi + Élec)**

```powershell
python main.py --ifc-archi maquettes/archi.ifc --ifc-elec maquettes/elec.ifc
```

**Ce qui se passe :**
-   Pièces, portes, dalles → Depuis **archi.ifc**
-   Équipements électriques → Depuis **elec.ifc**
-   **Fusion automatique** par coordonnées spatiales
-   Association équipements ↔ pièces par position

---

### **Option 2 : 1 seul fichier (comme avant)**

```powershell
python main.py --ifc maquettes/Ibn_Sina.ifc
```

---

##   STRUCTURE MAQUETTES

```
maquettes/
├── archi.ifc     ← Export depuis maquette Architecture Revit
└── elec.ifc      ← Export depuis maquette Électrique Revit
```

---

## 📖 EXPORT DEPUIS REVIT

### **Fichier Architecture :**
1. Ouvrir `Projet_ARCHI.rvt`
2. Fichier → Exporter → IFC
3. Sauvegarder : `maquettes/archi.ifc`

### **Fichier Électrique :**
1. Ouvrir `Projet_ELEC.rvt`
2. Fichier → Exporter → IFC
3. Sauvegarder : `maquettes/elec.ifc`

---

## 🎯 EXEMPLE COMPLET

```powershell
# 1. Placer fichiers
maquettes/
├── Ibn_Sina_ARCHI.ifc
└── Ibn_Sina_ELEC.ifc

# 2. Lancer analyse
python main.py --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc

# 3. Résultats dans
resultats/analysis_results.json
resultats/analysis_results.xlsx
```

---

##  COMMENT ÇA FONCTIONNE ?

### **Fusion Automatique par Coordonnées**

```
ARCHI.IFC:
└── Pièce "Local Technique RDC"
    └── Position: (10-15m, 5-10m, 0-3m)
    └── Porte: Largeur 0.9m

ELEC.IFC:
└── Équipement "Transformateur T1"
    └── Position: (12.5m, 8.3m, 1.5m)
    └── Dimension: 1.2m

FUSION:
  Équipement (12.5, 8.3, 1.5) EST DANS Pièce (10-15, 5-10, 0-3)
→ Association automatique
→ Analyse ELEC-003: Transformateur 1.2m vs Porte 0.9m
→ 🚨 VIOLATION: Porte trop étroite !
```

---

## ⚙️ OPTIONS SUPPLÉMENTAIRES

```powershell
# Mode verbose (voir détails fusion)
python main.py --ifc-archi archi.ifc --ifc-elec elec.ifc --verbose

# Règle spécifique
python main.py --ifc-archi archi.ifc --ifc-elec elec.ifc --rules ELEC-003

# Format Excel uniquement
python main.py --ifc-archi archi.ifc --ifc-elec elec.ifc --format excel
```

---

##    DIFFÉRENCES vs ANCIEN MODE

| Critère | Mode 1 fichier | Mode 2 fichiers |
|---------|---------------|-----------------|
| Pièces |   Si dans fichier |   Depuis ARCHI |
| Équipements |   Si dans fichier |   Depuis ÉLEC |
| Portes |   Si dans fichier |   Depuis ARCHI |
| Dalles |   Si dans fichier |   Depuis ARCHI |
| Fusion | - |   Automatique |

---

## 🆘 PROBLÈMES FRÉQUENTS

### **Aucune association équipement ↔ pièce**

**Cause :** Coordonnées incompatibles entre fichiers

**Solution :**
- Vérifier que les 2 maquettes Revit ont **même point d'origine**
- Vérifier export IFC avec **coordonnées partagées**

---

### **0 équipements extraits**

**Cause :** Mots-clés ne correspondent pas

**Solution :**
Modifier `extractors/ifc_extractor.py` ligne 155 :
```python
keywords = ['elec', 'light', 'lampe', 'transfo', 
           'VOTRE_MOT_CLE']  # ← Ajouter ici
```

---

##   NOTES IMPORTANTES

-   Les 2 fichiers **doivent avoir les mêmes coordonnées** (point base)
-   La fusion se fait **automatiquement** par position spatiale
-   Tolérance de positionnement : ±10cm
-   Si équipement non associé → Warning dans logs

---

**Testez maintenant avec vos 2 fichiers IFC !** 🚀
