"""
============================================================================
ELEC-002 - Vérification Ventilation Locaux Techniques
============================================================================
Règle: Les locaux techniques doivent avoir un volume suffisant pour assurer
la ventilation des équipements électriques.

Critère: Minimum 10m³ par équipement électrique
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class ELEC002VentilationChecker:
    """Analyseur règle ELEC-002 - Ventilation"""

    RULE_ID = "ELEC-002"
    RULE_NAME = "Vérification ventilation locaux techniques"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def load_config(self):
        """Charge configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
                self.config = config_full.get(self.RULE_ID, {})

            self.min_volume_per_equipment = self.config.get('parameters', {}).get('min_volume_per_equipment_m3', 10)

            logger.debug(f"  Config {self.RULE_ID}: {self.min_volume_per_equipment}m³/équipement")

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.min_volume_per_equipment = 10

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse ELEC-002"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []
        technical_rooms = space_types.get('local_technique', [])

        if not technical_rooms:
            logger.warning(f"   Aucun local technique pour {self.RULE_ID}")
            return self.violations

        for space in technical_rooms:
            self._analyze_space(space, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict]):
        """Analyse ventilation d'un espace"""
        space_name = space['name']
        space_volume = space['volume_m3']

        # Compter équipements dans espace
        space_bbox_min = space['bbox_min']
        space_bbox_max = space['bbox_max']

        equipment_count = 0
        equipment_names = []

        for eq in equipment:
            if GeometryUtils.is_point_in_bbox(eq['centroid'], space_bbox_min, space_bbox_max):
                equipment_count += 1
                equipment_names.append(eq['name'])

        if equipment_count == 0:
            return

        # Volume requis
        required_volume = equipment_count * self.min_volume_per_equipment

        # Vérifier
        if space_volume < required_volume:
            deficit = required_volume - space_volume

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "IMPORTANT",
                "space_name": space_name,
                "space_global_id": space['global_id'],
                "description": "Volume insuffisant pour ventilation",
                "details": {
                    "space_volume_m3": round(space_volume, 2),
                    "required_volume_m3": round(required_volume, 2),
                    "deficit_m3": round(deficit, 2),
                    "equipment_count": equipment_count,
                    "equipment_list": equipment_names
                },
                "location": space['centroid'],
                "recommendation": f"Augmenter ventilation ou réduire nombre équipements. "
                                 f"Déficit: {round(deficit, 2)}m³"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, space_name,
                                f"{space_volume:.1f}m³ < {required_volume:.1f}m³ requis")
        else:
            logger.rule_passed(self.RULE_ID, space_name)
