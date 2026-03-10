"""
============================================================================
CHANT-002 - Accessibilité des locaux techniques
============================================================================
Règle: Les locaux techniques (électriques, VDI, TGBT...) contiennent des
équipements sous tension ou dangereux. L'accès doit être réservé
exclusivement au personnel habilité et autorisé.
Tout local technique identifié dans la maquette doit être signalé
comme zone d'accès restreint.

Logique: Violation SYSTÉMATIQUE — chaque local technique = 1 violation.

Sévérité: MOYENNE
"""

from typing import List, Dict
from shared.logger import logger


class CHANT002AccessibiliteChecker:
    """Analyseur CHANT-002 - Accessibilité locaux techniques (systématique)"""

    RULE_ID = "CHANT-002"
    RULE_NAME = "Accessibilité des locaux techniques"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """Violation systématique pour chaque local technique détecté."""
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        locaux_techniques = space_types.get('local_technique', [])

        if not locaux_techniques:
            logger.info(f"    Aucun local technique trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(locaux_techniques)} locaux techniques — signalement accès restreint...")

        for local in locaux_techniques:
            local_name = local.get('name', 'Inconnu')
            local_height = local.get('height_m') or 0

            self.violations.append({
                "rule_id": self.RULE_ID,
                "severity": "MOYENNE",
                "space_name": local_name,
                "space_global_id": local.get('global_id', ''),
                "description": f"Local technique — accès réservé au personnel habilité",
                "details": {
                    "height_m": round(local_height, 2),
                    "area_m2": round(local.get('floor_area_m2') or 0, 2),
                },
                "location": list(local.get('centroid', [0, 0, 0])),
                "recommendation": (
                    f"Poser un panneau 'Accès interdit au public — Personnel habilité uniquement' "
                    f"sur la porte de {local_name}. Verrouiller l'accès en dehors des interventions."
                )
            })
            logger.rule_violation(self.RULE_ID, local_name, "Local technique — accès restreint requis")

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations
