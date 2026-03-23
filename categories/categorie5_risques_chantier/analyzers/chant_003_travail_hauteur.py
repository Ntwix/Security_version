"""
============================================================================
CHANT-003 - Travail en hauteur
============================================================================
Règle: L'installation d'équipements électriques dans des locaux de grande
hauteur expose les ouvriers à un risque de chute.

La hauteur analysée est celle de la PIÈCE (height_m de l'espace Revit).
Chaque pièce dont la hauteur dépasse 2m génère 1 violation avec le matériel
de travail en hauteur adapté.

Selon la hauteur de la pièce :
  < 2m        : OK — pas de matériel spécial requis
  2m – 3m     : Escabeau (travaux légers, maintenance, installation rapide)
  3m – 4.5m   : PIR/PIRL (Plateforme Individuelle Roulante) — plus stable
  4.5m – 6m   : Échafaudage roulant équipé de garde-corps
  6m – 20m    : Échafaudage roulant / fixe
  ≥ 20m       : Échafaudage fixe ou Nacelle PEMP (10m à 40m+)

Sévérité: MOYENNE (2–3m) / HAUTE (3–6m) / CRITIQUE (≥6m) 
"""

from typing import List, Dict
from shared.logger import logger

# Seuils de hauteur (mètres)
SEUIL_ESCABEAU_M    = 2.0
SEUIL_PIR_M         = 3.0
SEUIL_ECHAFAUDAGE_M = 4.5
SEUIL_ECHAF_FIXE_M  = 6.0
SEUIL_PEMP_M        = 20.0


class CHANT003TravailHauteurChecker:
    """Analyseur CHANT-003 - Travail en hauteur (1 violation par pièce trop haute)"""

    RULE_ID = "CHANT-003"
    RULE_NAME = "Travail en hauteur"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        1 violation par pièce dont la hauteur dépasse 2m.
        La hauteur utilisée est height_m de l'espace (hauteur réelle de la pièce).
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        if not spaces:
            logger.info(f"    Aucun espace trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(spaces)} espaces — analyse hauteur des pièces...")

        for space in spaces:
            self._check_espace(space)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _check_espace(self, space: Dict):
        hauteur_m = space.get('height_m') or 0

        if hauteur_m < SEUIL_ESCABEAU_M:
            return  # Pas de risque

        space_name = space.get('name', '') or space.get('long_name', 'Inconnu')
        long_name  = space.get('long_name', '')
        label      = f"{space_name} — {long_name}" if long_name and long_name != space_name else space_name

        if hauteur_m >= SEUIL_PEMP_M:
            severity = "CRITIQUE"
            materiel = "Nacelle élévatrice PEMP (10m à 40m+) ou Échafaudage fixe"
            niveau_risque = f"{hauteur_m:.1f}m ≥ {SEUIL_PEMP_M}m"
        elif hauteur_m >= SEUIL_ECHAF_FIXE_M:
            severity = "CRITIQUE"
            materiel = "Échafaudage roulant (6m–12m) équipé de garde-corps obligatoires"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_ECHAF_FIXE_M}m et {SEUIL_PEMP_M}m"
        elif hauteur_m >= SEUIL_ECHAFAUDAGE_M:
            severity = "HAUTE"
            materiel = "Échafaudage roulant — doit être stabilisé et équipé de garde-corps"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_ECHAFAUDAGE_M}m et {SEUIL_ECHAF_FIXE_M}m"
        elif hauteur_m >= SEUIL_PIR_M:
            severity = "HAUTE"
            materiel = "PIR/PIRL (Plateforme Individuelle Roulante) — plus stable que l'escabeau"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_PIR_M}m et {SEUIL_ECHAFAUDAGE_M}m"
        else:
            severity = "MOYENNE"
            materiel = "Escabeau (pour travaux légers, maintenance, installation rapide)"
            niveau_risque = f"{hauteur_m:.1f}m entre {SEUIL_ESCABEAU_M}m et {SEUIL_PIR_M}m"

        self.violations.append({
            "rule_id":         self.RULE_ID,
            "severity":        severity,
            "space_name":      label,
            "space_global_id": space.get('global_id', ''),
            "description":     f"Local de {hauteur_m:.1f}m de hauteur — {materiel}",
            "details": {
                "hauteur_piece_m":      round(hauteur_m, 2),
                "seuil_escabeau_m":     SEUIL_ESCABEAU_M,
                "seuil_pir_m":          SEUIL_PIR_M,
                "seuil_echafaudage_m":  SEUIL_ECHAFAUDAGE_M,
                "seuil_echaf_fixe_m":   SEUIL_ECHAF_FIXE_M,
                "seuil_pemp_m":         SEUIL_PEMP_M,
                "niveau_risque":        niveau_risque,
                "materiel_requis":      materiel,
            },
            "location":        list(space.get('centroid', [0, 0, 0])),
            "recommendation": (
                f"Pièce '{label}' : hauteur {hauteur_m:.1f}m. "
                f"Matériel requis pour toute intervention en hauteur : {materiel}. "
                f"Vérifier la stabilité du sol et dégager la zone de travail avant montage."
            )
        })
        logger.rule_violation(self.RULE_ID, label, f"Hauteur pièce {hauteur_m:.1f}m — {materiel}")
