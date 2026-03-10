"""
============================================================================
CHANT-005 - Ventilation des locaux techniques
============================================================================
Règle: Pendant les travaux d'installation, les locaux techniques fermés
sans ventilation adéquate exposent les ouvriers à des risques d'accumulation
de chaleur, de fumées ou de manque d'oxygène.
Tout local technique sans système de ventilation identifié dans la maquette
doit être signalé.

Logique: Violation si aucun équipement de ventilation détecté dans le local.

Sévérité: HAUTE
"""

from typing import List, Dict
from shared.logger import logger

# Mots-clés pour identifier les équipements de ventilation
VENTILATION_KEYWORDS = [
    "ventilation", "ventilateur", "extracteur", "vmc",
    "climatisation", "clim", "split", "cvc", "hvac",
    "bouche air", "grille ventilation", "diffuseur",
    "air conditionné", "soufflage", "reprise air"
]

VENTILATION_IFC_TYPES = [
    "ifcairterminal", "ifcductfitting", "ifcductsegment",
    "ifcfan", "ifcaircooler", "ifcunitaryequipment"
]

# Tolérance pour associer un équipement à un local (mètres)
TOLERANCE_M = 0.5


class CHANT005VentilationChecker:
    """Analyseur CHANT-005 - Ventilation locaux techniques"""

    RULE_ID = "CHANT-005"
    RULE_NAME = "Ventilation des locaux techniques"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        Pour chaque local technique, vérifie si un équipement de ventilation
        est présent dans la maquette.
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        locaux_techniques = space_types.get('local_technique', [])

        if not locaux_techniques:
            logger.info(f"    Aucun local technique trouvé pour {self.RULE_ID}")
            return self.violations

        # Filtrer les équipements de ventilation
        equip_ventilation = [eq for eq in equipment if self._is_ventilation(eq)]
        logger.info(f"   {len(equip_ventilation)} équipements de ventilation détectés")

        for local in locaux_techniques:
            local_name = local.get('name', 'Inconnu')
            has_ventilation = self._has_ventilation_in_local(local, equip_ventilation)

            if not has_ventilation:
                self.violations.append({
                    "rule_id": self.RULE_ID,
                    "severity": "HAUTE",
                    "space_name": local_name,
                    "space_global_id": local.get('global_id', ''),
                    "description": f"Local technique sans ventilation — risque pour les ouvriers",
                    "details": {
                        "height_m": round(local.get('height_m') or 0, 2),
                        "area_m2": round(local.get('floor_area_m2') or 0, 2),
                        "ventilation_detectee": False,
                    },
                    "location": list(local.get('centroid', [0, 0, 0])),
                    "recommendation": (
                        f"Local '{local_name}' sans ventilation détectée dans la maquette. "
                        f"Pendant les travaux : prévoir une ventilation temporaire (ventilateur mobile), "
                        f"limiter la durée d'intervention, surveiller la qualité de l'air."
                    )
                })
                logger.rule_violation(self.RULE_ID, local_name, "Pas de ventilation détectée")
            else:
                logger.rule_passed(self.RULE_ID, local_name)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _is_ventilation(self, eq: Dict) -> bool:
        name = (eq.get('name', '') or '').lower()
        ifc  = (eq.get('ifc_type', '') or '').lower()
        for kw in VENTILATION_KEYWORDS:
            if kw in name:
                return True
        if ifc in VENTILATION_IFC_TYPES:
            return True
        return False

    def _has_ventilation_in_local(self, local: Dict, equip_ventilation: List[Dict]) -> bool:
        """Vérifie si un équipement de ventilation est dans le local (par bbox)."""
        bbox_min = local.get('bbox_min', (0, 0, 0))
        bbox_max = local.get('bbox_max', (0, 0, 0))

        for eq in equip_ventilation:
            centroid = eq.get('centroid', (0, 0, 0))
            if (bbox_min[0] - TOLERANCE_M <= centroid[0] <= bbox_max[0] + TOLERANCE_M and
                bbox_min[1] - TOLERANCE_M <= centroid[1] <= bbox_max[1] + TOLERANCE_M and
                bbox_min[2] - TOLERANCE_M <= centroid[2] <= bbox_max[2] + TOLERANCE_M):
                return True
        return False
