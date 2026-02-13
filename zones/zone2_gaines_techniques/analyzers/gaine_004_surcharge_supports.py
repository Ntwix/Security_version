"""
============================================================================
GAINE-004 - Surcharge supports de câbles
============================================================================
Règle: Le poids des câbles ne doit pas dépasser la capacité portante
des supports (chemins de câbles, échelles, goulottes).

Sévérité: HAUTE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class GAINE004SurchargeSupportsChecker:
    """Analyseur règle GAINE-004 - Surcharge supports"""

    RULE_ID = "GAINE-004"
    RULE_NAME = "Surcharge supports de câbles"

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

            self.safety_margin = self.config.get('parameters', {}).get('safety_margin_percent', 15) / 100
            self.default_cable_weight = self.config.get('parameters', {}).get('default_cable_weight_kg_per_m', 2.5)
            self.default_support_capacity = self.config.get('parameters', {}).get('default_support_capacity_kg', 50)

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.safety_margin = 0.15
            self.default_cable_weight = 2.5
            self.default_support_capacity = 50

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-004"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces concernés
        concerned_spaces = []
        concerned_spaces.extend(space_types.get('gaine_technique', []))
        concerned_spaces.extend(space_types.get('local_technique', []))
        concerned_spaces.extend(space_types.get('faux_plafond', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerné pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour surcharge supports...")

        for space in concerned_spaces:
            self._analyze_space(space, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict]):
        """Analyse surcharge des supports dans un espace"""
        space_name = space.get('name', 'Inconnu')

        # Identifier supports et câbles dans l'espace
        supports = []
        cables = []

        for eq in equipment:
            if not GeometryUtils.is_point_in_bbox(
                eq.get('centroid', (0, 0, 0)),
                space.get('bbox_min', (0, 0, 0)),
                space.get('bbox_max', (0, 0, 0))
            ):
                continue

            eq_name = eq.get('name', '').lower()
            ifc_type = eq.get('ifc_type', '')

            # Identifier supports
            support_keywords = ['chemin de câbles', 'support', 'échelle', 'goulotte',
                               'tablette', 'rail', 'cable tray', 'ladder']
            support_ifc = ['IfcCableCarrierSegment', 'IfcCableCarrierFitting', 'IfcDiscreteAccessory']

            if any(kw in eq_name for kw in support_keywords) or any(t in ifc_type for t in support_ifc):
                supports.append(eq)
                continue

            # Identifier câbles
            cable_keywords = ['câble', 'cable', 'fil', 'conducteur', 'wire']
            cable_ifc = ['IfcCableSegment', 'IfcCableFitting']

            if any(kw in eq_name for kw in cable_keywords) or any(t in ifc_type for t in cable_ifc):
                cables.append(eq)

        if not supports:
            return

        # Pour chaque support, vérifier la charge
        for support in supports:
            self._check_support_load(space, support, cables)

    def _check_support_load(self, space: Dict, support: Dict, cables: List[Dict]):
        """Vérifie la charge sur un support"""
        support_name = support.get('name', 'Inconnu')
        properties = support.get('properties', {})

        # Capacité portante du support
        capacity = self._extract_capacity(properties)
        if capacity is None:
            capacity = self.default_support_capacity

        # Calculer poids câbles sur ce support
        cable_weight = self._calculate_cable_weight_on_support(support, cables)

        if cable_weight == 0:
            # Estimer poids par dimension du support
            support_length = support.get('max_dimension_m', 1.0)
            cable_weight = support_length * self.default_cable_weight

        # Appliquer marge sécurité
        safe_capacity = capacity * (1 - self.safety_margin)

        if cable_weight > safe_capacity:
            excess = cable_weight - safe_capacity

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "HAUTE",
                "space_name": space.get('name', 'Inconnu'),
                "space_global_id": space.get('global_id', ''),
                "description": "Surcharge détectée sur support de câbles",
                "details": {
                    "support_name": support_name,
                    "cable_weight_kg": round(cable_weight, 1),
                    "support_capacity_kg": round(capacity, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1),
                    "safety_margin_percent": self.safety_margin * 100
                },
                "location": support.get('centroid', (0, 0, 0)),
                "recommendation": f"Renforcer support ou redistribuer câbles. "
                                 f"Excès: {excess:.1f}kg"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, support_name,
                                f"{cable_weight:.1f}kg > {safe_capacity:.1f}kg")
        else:
            logger.rule_passed(self.RULE_ID, support_name)

    def _extract_capacity(self, properties: Dict) -> float:
        """Extrait la capacité portante depuis les propriétés"""
        capacity_keys = ['LoadCapacity', 'ChargeAdmissible', 'MaxLoad',
                        'Capacite', 'Capacity', 'ChargeMax']

        for key in capacity_keys:
            if key in properties:
                try:
                    return float(properties[key])
                except:
                    pass
        return None

    def _calculate_cable_weight_on_support(self, support: Dict, cables: List[Dict]) -> float:
        """Calcule le poids des câbles sur un support"""
        total_weight = 0
        support_centroid = support.get('centroid', (0, 0, 0))

        for cable in cables:
            cable_centroid = cable.get('centroid', (0, 0, 0))
            distance = GeometryUtils.calculate_distance_3d(support_centroid, cable_centroid)

            # Câble considéré sur le support si à moins de 50cm
            if distance < 0.5:
                cable_weight = cable.get('weight_kg')
                if cable_weight:
                    total_weight += cable_weight
                else:
                    # Estimer par longueur
                    cable_length = cable.get('max_dimension_m', 1.0)
                    total_weight += cable_length * self.default_cable_weight

        return total_weight
