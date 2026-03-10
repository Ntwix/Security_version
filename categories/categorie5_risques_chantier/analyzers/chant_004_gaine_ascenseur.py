"""
============================================================================
CHANT-004 - Risque de chute en gaine ascenseur
============================================================================
Règle: Avant l'installation de l'ascenseur, la gaine est un espace vide
vertical présentant un risque de chute mortelle.
Toute gaine d'ascenseur identifiée dans la maquette doit être signalée
comme zone dangereuse nécessitant des protections collectives
(garde-corps, filet, balisage).

Logique: Violation SYSTÉMATIQUE — chaque gaine ascenseur = 1 violation.

Sévérité: CRITIQUE
"""

from typing import List, Dict
from shared.logger import logger


class CHANT004GaineAscenseurChecker:
    """Analyseur CHANT-004 - Gaine ascenseur (systématique)"""

    RULE_ID = "CHANT-004"
    RULE_NAME = "Risque de chute en gaine ascenseur"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """Violation systématique pour chaque gaine ascenseur détectée."""
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        gaines_ascenseur = space_types.get('gaine_ascenseur', [])

        if not gaines_ascenseur:
            logger.info(f"    Aucune gaine ascenseur trouvée pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(gaines_ascenseur)} gaines ascenseur — signalement risque chute...")

        for gaine in gaines_ascenseur:
            gaine_name   = gaine.get('name', 'Inconnu')
            gaine_height = gaine.get('height_m') or 0

            self.violations.append({
                "rule_id": self.RULE_ID,
                "severity": "CRITIQUE",
                "space_name": gaine_name,
                "space_global_id": gaine.get('global_id', ''),
                "description": f"Gaine ascenseur — risque de chute mortelle avant installation",
                "details": {
                    "gaine_height_m": round(gaine_height, 2),
                },
                "location": list(gaine.get('centroid', [0, 0, 0])),
                "recommendation": (
                    f"Gaine ascenseur '{gaine_name}' ({gaine_height:.1f}m) : "
                    f"Mettre en place impérativement des protections collectives "
                    f"(garde-corps, filet de sécurité, balisage) avant tout accès. "
                    f"Interdire l'accès sans équipement de protection individuelle (EPI)."
                )
            })
            logger.rule_violation(self.RULE_ID, gaine_name,
                                  f"Gaine ascenseur détectée ({gaine_height:.1f}m)")

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations
