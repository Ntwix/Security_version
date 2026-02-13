"""
============================================================================
ELEC-004 - Zones Humides - Protection IP65 Requise
============================================================================
Règle: Les équipements électriques en zones humides (douches, salles de bain)
doivent avoir protection IP65 et être en inox.
"""

import json
import re
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class ELEC004ShowerZoneChecker:
    """Analyseur règle ELEC-004 - Zones humides"""

    RULE_ID = "ELEC-004"
    RULE_NAME = "Zones humides - Protection IP65 requise"

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

            self.required_ip_rating = self.config.get('parameters', {}).get('required_ip_rating', 'IP65')
            self.required_material = self.config.get('parameters', {}).get('required_material', 'inox')

            logger.debug(f"  Config {self.RULE_ID}: {self.required_ip_rating} + {self.required_material}")

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.required_ip_rating = 'IP65'
            self.required_material = 'inox'

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse ELEC-004"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Collecter toutes les zones nécessitant ELEC-004
        wet_rooms = []
        wet_rooms.extend(space_types.get('zone_humide', []))
        wet_rooms.extend(space_types.get('cuisine_restauration', []))
        wet_rooms.extend(space_types.get('laverie_menage', []))

        if not wet_rooms:
            logger.info(f"    Aucune zone humide identifiée pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(wet_rooms)} zones humides (salles de bain, cuisines, laveries)...")

        for space in wet_rooms:
            self._analyze_space(space, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict]):
        """Analyse équipements en zone humide"""
        space_name = space['name']

        # Trouver équipements dans zone humide
        wet_zone_equipment = self._find_equipment_in_space(space, equipment)

        if not wet_zone_equipment:
            logger.debug(f"  {space_name}: Aucun équipement")
            return

        # Vérifier chaque équipement
        for eq in wet_zone_equipment:
            self._check_equipment_protection(space, eq)

    def _find_equipment_in_space(self, space: Dict, equipment: List[Dict]) -> List[Dict]:
        """Trouve équipements dans espace"""
        space_equipment = []

        for eq in equipment:
            if GeometryUtils.is_point_in_bbox(eq['centroid'], space['bbox_min'], space['bbox_max']):
                space_equipment.append(eq)

        return space_equipment

    def _check_equipment_protection(self, space: Dict, equipment: Dict):
        """Vérifie protection équipement en zone humide"""
        eq_name = equipment['name']
        properties = equipment.get('properties', {})

        # Vérifier IP rating
        ip_rating = self._extract_ip_rating(properties)
        has_correct_ip = self._is_ip_sufficient(ip_rating)

        # Vérifier matériau
        material = self._extract_material(properties)
        has_correct_material = (self.required_material.lower() in material.lower()) if material else False

        # Si non conforme
        if not has_correct_ip or not has_correct_material:
            issues = []
            if not has_correct_ip:
                issues.append(f"Protection IP insuffisante ({ip_rating or 'non spécifiée'})")
            if not has_correct_material:
                issues.append(f"Matériau incorrect ({material or 'non spécifié'})")

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "CRITICAL",
                "space_name": space['name'],
                "space_global_id": space['global_id'],
                "description": "Équipement non conforme en zone humide",
                "details": {
                    "equipment_name": eq_name,
                    "equipment_type": equipment['ifc_type'],
                    "current_ip_rating": ip_rating or "non spécifiée",
                    "required_ip_rating": self.required_ip_rating,
                    "current_material": material or "non spécifié",
                    "required_material": self.required_material,
                    "issues": issues
                },
                "location": equipment['centroid'],
                "recommendation": f"Remplacer par équipement {self.required_ip_rating} en {self.required_material}. "
                                 f"Problèmes: {', '.join(issues)}"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, f"{space['name']} / {eq_name}",
                                ", ".join(issues))
        else:
            logger.rule_passed(self.RULE_ID, f"{space['name']} / {eq_name}")

    def _extract_ip_rating(self, properties: Dict) -> str:
        """Extrait protection IP depuis propriétés"""
        ip_keys = ['IPRating', 'IP_Rating', 'Protection', 'ProtectionIndex']

        for key in ip_keys:
            if key in properties:
                return str(properties[key])

        return None

    def _is_ip_sufficient(self, ip_rating: str) -> bool:
        """Vérifie si IP rating suffisant"""
        if not ip_rating:
            return False

        # Extraire chiffres
        try:
            # Exemple: "IP65" -> 65
            match = re.search(r'IP(\d{2})', ip_rating.upper())
            if match:
                rating_value = int(match.group(1))
                required_value = int(self.required_ip_rating.replace('IP', ''))
                return rating_value >= required_value
        except:
            pass

        return False

    def _extract_material(self, properties: Dict) -> str:
        """Extrait matériau depuis propriétés"""
        material_keys = ['Material', 'Materiau', 'Matériau', 'FinishMaterial']

        for key in material_keys:
            if key in properties:
                return str(properties[key])

        return None
