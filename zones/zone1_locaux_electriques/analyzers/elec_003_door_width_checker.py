"""
============================================================================
ELEC-003 - Vérification Largeur Porte vs Équipement
============================================================================
Règle: La largeur des portes d'accès doit excéder la dimension maximale
des équipements avec une marge de sécurité.

Marge: 20 cm (modifiable dans config)
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class ELEC003DoorWidthChecker:
    """Analyseur règle ELEC-003 - Largeur portes"""

    RULE_ID = "ELEC-003"
    RULE_NAME = "Vérification largeur porte vs équipement"

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

            self.clearance_margin_cm = self.config.get('parameters', {}).get('clearance_margin_cm', 20)
            self.check_diagonal = self.config.get('parameters', {}).get('check_diagonal', True)

            logger.debug(f"  Config {self.RULE_ID}: marge={self.clearance_margin_cm}cm")

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.clearance_margin_cm = 20
            self.check_diagonal = True

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict, doors: List[Dict]) -> List[Dict]:
        """Lance analyse ELEC-003"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []
        technical_rooms = space_types.get('local_technique', [])

        if not technical_rooms:
            logger.warning(f"   Aucun local technique pour {self.RULE_ID}")
            return self.violations

        for space in technical_rooms:
            self._analyze_space(space, equipment, doors)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict], doors: List[Dict]):
        """Analyse portes d'un espace"""
        space_name = space['name']

        # Trouver portes de cet espace
        space_doors = self._find_doors_for_space(space, doors)

        if not space_doors:
            logger.debug(f"  {space_name}: Aucune porte trouvée")
            return

        # Trouver équipements dans espace
        space_equipment = self._find_equipment_in_space(space, equipment)

        if not space_equipment:
            return

        # Pour chaque équipement, vérifier si peut passer par porte
        for eq in space_equipment:
            self._check_equipment_access(space, eq, space_doors)

    def _find_doors_for_space(self, space: Dict, doors: List[Dict]) -> List[Dict]:
        """Trouve portes d'un espace"""
        space_doors = []
        space_bbox_min = space['bbox_min']
        space_bbox_max = space['bbox_max']

        # Tolérance pour détecter porte (porte généralement sur le mur)
        tolerance = 0.5  # 50cm

        for door in doors:
            door_centroid = door['centroid']

            # Vérifier si porte proche de la bbox
            in_x_range = (space_bbox_min[0] - tolerance <= door_centroid[0] <= space_bbox_max[0] + tolerance)
            in_y_range = (space_bbox_min[1] - tolerance <= door_centroid[1] <= space_bbox_max[1] + tolerance)
            in_z_range = (space_bbox_min[2] - tolerance <= door_centroid[2] <= space_bbox_max[2] + tolerance)

            if in_x_range and in_y_range and in_z_range:
                space_doors.append(door)

        return space_doors

    def _find_equipment_in_space(self, space: Dict, equipment: List[Dict]) -> List[Dict]:
        """Trouve équipements dans espace"""
        space_equipment = []

        for eq in equipment:
            if GeometryUtils.is_point_in_bbox(eq['centroid'], space['bbox_min'], space['bbox_max']):
                space_equipment.append(eq)

        return space_equipment

    def _check_equipment_access(self, space: Dict, equipment: Dict, doors: List[Dict]):
        """Vérifie si équipement peut passer par les portes"""
        eq_name = equipment['name']

        # Dimension équipement
        if self.check_diagonal:
            eq_dimension = equipment['diagonal_dimension_m']
            dimension_type = "diagonale"
        else:
            eq_dimension = equipment['max_dimension_m']
            dimension_type = "maximale"

        # Marge requise
        margin_m = self.clearance_margin_cm / 100
        required_width = eq_dimension + margin_m

        # Vérifier si au moins une porte est assez large
        can_pass = False
        widest_door = None
        max_door_width = 0

        for door in doors:
            door_width = door['width_m']
            if door_width > max_door_width:
                max_door_width = door_width
                widest_door = door

            if door_width >= required_width:
                can_pass = True
                break

        # Si aucune porte assez large
        if not can_pass and widest_door:
            shortage = required_width - max_door_width

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "IMPORTANT",
                "space_name": space['name'],
                "space_global_id": space['global_id'],
                "description": f"Porte trop étroite pour équipement",
                "details": {
                    "equipment_name": eq_name,
                    "equipment_dimension_m": round(eq_dimension, 3),
                    "dimension_type": dimension_type,
                    "required_door_width_m": round(required_width, 3),
                    "actual_door_width_m": round(max_door_width, 3),
                    "shortage_m": round(shortage, 3),
                    "clearance_margin_cm": self.clearance_margin_cm,
                    "widest_door_name": widest_door['name']
                },
                "location": equipment['centroid'],
                "recommendation": f"Élargir porte ou prévoir démontage équipement. "
                                 f"Manque: {round(shortage*100, 1)}cm"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, f"{space['name']} / {eq_name}",
                                f"Porte {max_door_width:.2f}m < {required_width:.2f}m requis")
