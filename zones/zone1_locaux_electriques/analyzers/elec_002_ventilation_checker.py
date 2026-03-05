"""
============================================================================
ELEC-002 - Vérification Ventilation Locaux Techniques
============================================================================
Règle: Chaque local technique électrique doit disposer d'une ventilation.

Critère: Signaler les locaux techniques (hors gaines < 5m²) qui nécessitent
une ventilation pour les équipements dégageant de la chaleur.
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

    # Surface minimale pour considérer un espace comme un vrai local (pas une gaine)
    MIN_FLOOR_AREA_M2 = 5.0

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

            logger.debug(f"  Config {self.RULE_ID} chargée")

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

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
        floor_area = space.get('floor_area_m2') or 0

        # Filtrer les gaines techniques (trop petites pour être des locaux)
        if floor_area < self.MIN_FLOOR_AREA_M2:
            return

        # Compter équipements dans l'espace si disponibles (maquette ELEC)
        space_bbox_min = space.get('bbox_min')
        space_bbox_max = space.get('bbox_max')

        equipment_count = 0
        equipment_names = []

        if space_bbox_min and space_bbox_max and equipment:
            for eq in equipment:
                if GeometryUtils.is_point_in_bbox(eq['centroid'], space_bbox_min, space_bbox_max):
                    equipment_count += 1
                    equipment_names.append(eq['name'])

        # Un local technique contient par définition des équipements électriques
        # → signaler le besoin de ventilation même sans maquette ELEC
        if equipment_count > 0:
            description = "Local technique nécessitant une ventilation"
            recommendation = (f"Prévoir une ventilation pour ce local technique "
                              f"({equipment_count} équipements, {round(floor_area, 2)} m²)")
            detail_note = f"Equipements modélisés: {equipment_count}"
        else:
            description = "Local technique sans maquette ELEC - ventilation à vérifier"
            recommendation = (f"Prévoir une ventilation pour ce local technique "
                              f"({round(floor_area, 2)} m²) - aucun équipement modélisé")
            detail_note = "Aucun équipement modélisé (maquette ELEC absente)"

        violation = {
            "rule_id": self.RULE_ID,
            "severity": "IMPORTANT",
            "space_name": space_name,
            "space_global_id": space['global_id'],
            "description": description,
            "details": {
                "floor_area_m2": round(floor_area, 2),
                "equipment_count": equipment_count,
                "equipment_list": equipment_names[:10],
                "note": detail_note
            },
            "location": space['centroid'],
            "recommendation": recommendation
        }

        self.violations.append(violation)
        logger.rule_violation(self.RULE_ID, space_name,
                            f"Ventilation requise - {detail_note}, {floor_area:.1f} m²")

