# Rapport d'Avancement - Projet CHU Ibn Sina
# Analyse Automatique de Conformité Sécurité par BIM
**Date : 18 Février 2026**

---

## 1. Objectif du Projet

Le projet consiste à développer un outil capable d'analyser automatiquement les maquettes 3D (BIM) du CHU Ibn Sina afin de détecter les non-conformités de sécurité dans les locaux techniques. L'outil lit les maquettes Architecture et Électricité, identifie les espaces concernés, applique les règles de sécurité, et produit des rapports détaillés avec visualisation directe dans Revit.

---

## 2. Ce qui a été Réalisé

### 2.1 Système d'analyse multi-zones complet

Le programme analyse **4 zones à risque** distinctes, avec **17 règles de sécurité** au total :

| Zone | Description | Nb de règles | Statut |
|------|-------------|:------------:|--------|
| Zone 1 | Locaux Électriques | 4 règles | Opérationnel |
| Zone 2 | Gaines Techniques Verticales | 5 règles | Opérationnel |
| Zone 3 | Faux Plafonds Techniques | 3 règles | Opérationnel |
| Zone 4 | Planchers Techniques | 5 règles | Opérationnel (formulaire) |

### 2.2 Détail des règles par zone

#### Zone 1 - Locaux Électriques (4 règles)

| Règle | Vérification | Niveau |
|-------|-------------|--------|
| ELEC-001 | Le poids cumulé des équipements électriques dans un local ne dépasse pas la capacité portante de la dalle (avec marge de sécurité 10%) | Critique |
| ELEC-002 | Tout local technique contenant des équipements électriques doit disposer d'une ventilation adaptée | Important |
| ELEC-003 | La largeur des portes d'accès doit permettre le passage des équipements les plus larges (marge de 20 cm) | Important |
| ELEC-004 | Les équipements en zones humides (sanitaires, cuisines, laveries) doivent être IP65 et en inox | Critique |

#### Zone 2 - Gaines Techniques (5 règles)

| Règle | Vérification | Niveau |
|-------|-------------|--------|
| GAINE-001 | Protection contre la chute d'objets dans les gaines verticales de plus d'1 m de hauteur | Haute |
| GAINE-002 | Distance minimale de 30 cm entre courant fort et courant faible (interférences électromagnétiques) | Critique |
| GAINE-003 | Présence de trappes d'accès pour la maintenance des équipements dans les gaines | Moyenne |
| GAINE-004 | Vérification que les chemins de câbles ne sont pas surchargés | Haute |
| GAINE-005 | Calcul détaillé de charge sur les supports (différencié courant fort/faible) | Haute |

#### Zone 3 - Faux Plafonds Techniques (3 règles)

| Règle | Vérification | Niveau |
|-------|-------------|--------|
| FPLAF-001 | Risque de chute de hauteur lors des interventions en faux plafond (seuils : 3 m élevé, 4 m critique) | Haute |
| FPLAF-002 | Surcharge du plafond par les équipements suspendus (capacité par défaut 25 kg/m²) | Haute |
| FPLAF-003 | Détection de matériaux générant des poussières nocives (laine minérale, amiante, fibres...) | Moyenne |

#### Zone 4 - Planchers Techniques (5 règles)

| Règle | Vérification | Niveau |
|-------|-------------|--------|
| PLAN-001 | Identification du type de plancher technique installé | Info |
| PLAN-002 | Vérification de la protection des câbles sous plancher | Haute |
| PLAN-003 | Détection des risques d'humidité | Haute |
| PLAN-004 | Risques d'écrasement des doigts | Haute |
| PLAN-005 | Synthèse automatique de tous les risques plancher | Haute |

---

### 2.3 Extraction des données depuis les maquettes BIM

Le système fonctionne avec les vraies maquettes du CHU Ibn Sina. Il sait lire :

- **631 espaces** (pièces, locaux techniques, circulations...)
- **3 190 équipements électriques** (tableaux, prises, luminaires, chemins de câbles, BAES...)
- **276 portes**
- **73 dalles** (planchers porteurs)

L'extraction se fait en deux modes :
- **Mode fichiers IFC** : lecture directe des fichiers IFC Architecture + Électricité (pour travailler hors de Revit)
- **Mode Plugin Revit** : extraction live depuis le modèle ouvert dans Revit (pour un usage intégré)

### 2.4 Plugin Revit (C#)

Un plugin intégré directement dans Autodesk Revit a été développé :

- Bouton "Analyser Zone" dans l'onglet "CHU Sécurité" du ruban Revit
- Détection automatique de la maquette Architecture vs Électricité
- Choix de la zone à analyser (1, 2, 3, 4, ou toutes)
- Extraction des données, lancement de l'analyse, récupération des résultats
- **Visualisation directe dans Revit** :
  - Création de vues dupliquées nommées "ZONES RISQUES - ..."
  - Coloration automatique des équipements en infraction : **rouge** (critique) ou **orange** (important)
  - Symboles graphiques sur les plans (cercles, triangles, losanges) avec légendes
  - Navigation automatique vers la vue la plus pertinente

### 2.5 Rapports de sortie

Chaque analyse produit :
- Un fichier **JSON** structuré (exploitable par d'autres logiciels)
- Un fichier **Excel** avec 3 onglets : Violations, Statistiques, Par Règle

---

## 3. Résultats Obtenus sur les Maquettes CHU Ibn Sina

Les analyses ont été exécutées sur les vraies maquettes du projet. Voici les résultats :

### Zone 1 - Locaux Électriques (dernière exécution : 17/02/2026)
| Règle | Violations détectées |
|-------|:-------------------:|
| ELEC-001 (poids) | 0 |
| ELEC-002 (ventilation) | 40 |
| ELEC-003 (largeur portes) | 60 |
| ELEC-004 (zones humides IP65) | 548 |
| **Total Zone 1** | **648** |

### Zone 2 - Gaines Techniques (dernière exécution : 09/02/2026)
| Règle | Violations détectées |
|-------|:-------------------:|
| GAINE-001 (chute objets) | 213 |
| GAINE-002 (croisement réseaux) | 0 |
| GAINE-003 (trappes accès) | 65 |
| GAINE-004 (surcharge supports) | 0 |
| **Total Zone 2** | **278** |

### Zone 3 - Faux Plafonds (dernière exécution : 10/02/2026)
| Règle | Violations détectées |
|-------|:-------------------:|
| FPLAF-001 (chute hauteur) | 332 |
| FPLAF-002 (surcharge plafond) | 0 |
| FPLAF-003 (poussières) | 0 |
| **Total Zone 3** | **332** |

### Zone 4 - Planchers Techniques
Pas encore exécutée sur les maquettes (fonctionne par formulaire interactif).

### Total général : **1 258 points de vigilance** détectés sur l'ensemble du bâtiment.

---

## 4. Outils et Technologies Utilisés

| Composant | Technologie |
|-----------|-------------|
| Analyse des maquettes | Python 3 + ifcopenshell |
| Plugin Revit | C# .NET (Revit API 2024) |
| Format d'échange | IFC (Industry Foundation Classes) |
| Rapports | JSON + Excel (openpyxl) |
| Gestion de version | Git + GitHub |

---

## 5. Lien du Code Source

Le code est versionné et accessible sur GitHub :
**https://github.com/Ntwix/CHU_BIM**

---

## 6. Prochaines Étapes Possibles

- Affiner les seuils des règles après retour des ingénieurs sécurité
- Enrichir les propriétés des équipements dans les maquettes (poids, IP, matériaux) pour améliorer la précision
- Tester le plugin Revit avec les dernières versions des maquettes
- Exécuter la Zone 4 en mode interactif avec l'équipe sur site
- Ajouter un export PDF avec captures des vues "Zones Risques"
