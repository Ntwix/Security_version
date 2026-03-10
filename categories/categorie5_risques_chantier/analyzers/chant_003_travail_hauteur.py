"""
============================================================================
CHANT-003 - Travail en hauteur
============================================================================
Règle: L'installation d'équipements électriques (chemins de câbles, tableaux,
luminaires, appareillage...) dans des locaux de grande hauteur expose les
ouvriers à un risque de chute.

Selon la hauteur d'intervention, un équipement de travail en hauteur
adapté est obligatoire :
  < 2m   : OK — pas de matériel spécial requis
  2m–3m  : Échelle simple
  3m–4m  : PIR (Plateforme Individuelle Roulante)
  ≥ 4m   : PEMP (Plateforme Élévatrice Mobile de Personnel)

Sévérité: MOYENNE (2–3m) / HAUTE (3–4m) / CRITIQUE (≥4m)
"""

from typing import List, Dict
from shared.logger import logger

# Seuils de hauteur (mètres)
SEUIL_ECHELLE_M   = 2.0
SEUIL_PIR_M       = 3.0
SEUIL_PEMP_M      = 4.0

# Mots-clés pour identifier les équipements électriques concernés
EQUIPMENT_KEYWORDS = [
    "luminaire", "éclairage", "spot", "plafonnier",
    "chemin de c", "cdc ", "cable tray",
    "tableau", "armoire", "coffret",
    "détecteur", "extracteur", "ventilateur",
    "baes", "diffuseur", "bouche"
]


class CHANT003TravailHauteurChecker:
    """Analyseur CHANT-003 - Travail en hauteur (conditionnel selon hauteur)"""

    RULE_ID = "CHANT-003"
    RULE_NAME = "Travail en hauteur"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        Vérifie la hauteur d'installation de chaque équipement électrique.
        Violation si hauteur > 2m.
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        equip_electriques = [eq for eq in equipment if self._is_electrique(eq)]

        if not equip_electriques:
            logger.info(f"    Aucun équipement électrique trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(equip_electriques)} équipements électriques — analyse hauteur...")

        for eq in equip_electriques:
            self._check_hauteur(eq)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _check_hauteur(self, eq: Dict):
        centroid = eq.get('centroid', (0, 0, 0))
        hauteur_m = centroid[2] if centroid else 0

        if hauteur_m < SEUIL_ECHELLE_M:
            return  # Pas de risque

        eq_name = eq.get('name', 'Inconnu')

        if hauteur_m >= SEUIL_PEMP_M:
            severity = "CRITIQUE"
            materiel = "PEMP (Plateforme Élévatrice Mobile de Personnel) obligatoire"
            niveau_risque = f"{hauteur_m:.1f}m ≥ {SEUIL_PEMP_M}m"
        elif hauteur_m >= SEUIL_PIR_M:
            severity = "HAUTE"
            materiel = "PIR (Plateforme Individuelle Roulante) recommandée"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_PIR_M}m et {SEUIL_PEMP_M}m"
        else:
            severity = "MOYENNE"
            materiel = "Échelle simple avec dispositif anti-chute"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_ECHELLE_M}m et {SEUIL_PIR_M}m"

        self.violations.append({
            "rule_id": self.RULE_ID,
            "severity": severity,
            "space_name": eq_name,
            "space_global_id": eq.get('global_id', ''),
            "description": f"Installation en hauteur ({hauteur_m:.1f}m) — {materiel}",
            "details": {
                "hauteur_installation_m": round(hauteur_m, 2),
                "seuil_echelle_m": SEUIL_ECHELLE_M,
                "seuil_pir_m": SEUIL_PIR_M,
                "seuil_pemp_m": SEUIL_PEMP_M,
                "niveau_risque": niveau_risque,
                "materiel_requis": materiel,
            },
            "location": list(centroid),
            "recommendation": (
                f"Pour l'installation de '{eq_name}' à {hauteur_m:.1f}m : {materiel}. "
                f"Vérifier la stabilité du sol et dégager la zone de travail."
            )
        })
        logger.rule_violation(self.RULE_ID, eq_name, f"Hauteur {hauteur_m:.1f}m — {materiel}")

    def _is_electrique(self, eq: Dict) -> bool:
        name = (eq.get('name', '') or '').lower()
        ifc  = (eq.get('ifc_type', '') or '').lower()
        for kw in EQUIPMENT_KEYWORDS:
            if kw in name:
                return True
        if any(t in ifc for t in ['light', 'cable', 'electrical', 'outlet', 'alarm']):
            return True
        return False
