"""
============================================================================
GAINE-001 - Chute d'objets dans gaines techniques
============================================================================
Règle: Les gaines techniques verticales doivent être équipées de protections
anti-chute d'objets (grilles, filets, caillebotis, platelages).

Sévérité: HAUTE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class GAINE001ChuteObjetsChecker:
    """Analyseur règle GAINE-001 - Chute d'objets"""

    RULE_ID = "GAINE-001"
    RULE_NAME = "Chute d'objets dans gaines techniques"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def load_config(self):
        """Charge configuration règle"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
                self.config = config_full.get(self.RULE_ID, {})

            self.require_fall_protection = self.config.get('parameters', {}).get('require_fall_protection', True)
            self.protection_types = self.config.get('parameters', {}).get('protection_types',
                                                                          ['grille', 'filet', 'caillebotis', 'platelage'])

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.require_fall_protection = True
            self.protection_types = ['grille', 'filet', 'caillebotis', 'platelage']

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-001"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces gaine technique
        gaines = space_types.get('gaine_technique', [])

        if not gaines:
            logger.info(f"    Aucune gaine technique identifiée pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(gaines)} gaines techniques...")

        for gaine in gaines:
            self._analyze_gaine(gaine, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_gaine(self, gaine: Dict, equipment: List[Dict]):
        """Analyse une gaine technique pour la protection anti-chute"""
        gaine_name = gaine.get('name', 'Inconnu')
        gaine_height = gaine.get('height_m') or 0

        # Seules les gaines avec une hauteur significative (> 1m) sont concernées
        if gaine_height < 1.0:
            logger.debug(f"  {gaine_name}: Hauteur insuffisante ({gaine_height:.1f}m), ignorée")
            return

        # Chercher protections anti-chute dans les équipements à proximité
        has_protection = self._find_fall_protection(gaine, equipment)

        if not has_protection:
            violation = {
                "rule_id": self.RULE_ID,
                "severity": "HAUTE",
                "space_name": gaine_name,
                "space_global_id": gaine.get('global_id', ''),
                "description": "Gaine technique sans protection anti-chute d'objets",
                "details": {
                    "gaine_height_m": round(gaine_height, 2),
                    "required_protections": self.protection_types,
                    "protection_found": False
                },
                "location": gaine.get('centroid', (0, 0, 0)),
                "recommendation": f"Installer une protection anti-chute (types acceptés: "
                                 f"{', '.join(self.protection_types)})"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, gaine_name,
                                f"Hauteur {gaine_height:.1f}m sans protection anti-chute")
        else:
            logger.rule_passed(self.RULE_ID, gaine_name)

    @staticmethod
    def _props_to_dict(props) -> Dict:
        """Convertit les propriétés en dict (gère le format list de DataContractJsonSerializer)."""
        if isinstance(props, dict):
            return props
        if isinstance(props, list):
            result = {}
            for item in props:
                if isinstance(item, dict) and 'Key' in item:
                    result[item['Key']] = item.get('Value', '')
            return result
        return {}

    def _find_fall_protection(self, gaine: Dict, equipment: List[Dict]) -> bool:
        """
        Vérifie si une protection anti-chute existe dans/autour de la gaine.
        Cherche dans les noms et propriétés des équipements.
        """
        gaine_bbox_min = gaine.get('bbox_min', (0, 0, 0))
        gaine_bbox_max = gaine.get('bbox_max', (0, 0, 0))

        # Tolérance pour trouver éléments adjacents
        tolerance = 0.3  # 30cm

        for eq in equipment:
            eq_centroid = eq.get('centroid', (0, 0, 0))
            eq_name = eq.get('name', '').lower()
            eq_props = eq.get('properties', {})

            # Vérifier proximité avec la gaine
            in_range = (
                gaine_bbox_min[0] - tolerance <= eq_centroid[0] <= gaine_bbox_max[0] + tolerance and
                gaine_bbox_min[1] - tolerance <= eq_centroid[1] <= gaine_bbox_max[1] + tolerance and
                gaine_bbox_min[2] - tolerance <= eq_centroid[2] <= gaine_bbox_max[2] + tolerance
            )

            if not in_range:
                continue

            # Vérifier si c'est une protection
            for ptype in self.protection_types:
                if ptype.lower() in eq_name:
                    return True

            # Vérifier dans les propriétés (gérer format list ou dict)
            props_dict = self._props_to_dict(eq_props)
            for key, value in props_dict.items():
                if value and any(ptype.lower() in str(value).lower() for ptype in self.protection_types):
                    return True

        return False
