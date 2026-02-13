"""
============================================================================
GAINE-005 - Calcul charge des supports
============================================================================
Rule: The total load handled by each support is computed from the length
and weight of the cables mounted on it.

Severity: HAUTE
"""

import json
from typing import List, Dict, Optional
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils

DEFAULT_SUPPORT_KEYWORDS = [
    "chemin de cables", "support", "echelle a cables", "goulotte",
    "tablette", "rail", "cable tray", "ladder"
]
DEFAULT_SUPPORT_IFC_TYPES = [
    "IfcCableCarrierSegment", "IfcCableCarrierFitting", "IfcDiscreteAccessory"
]
DEFAULT_CABLE_KEYWORDS = ["cable", "fil", "conducteur", "wire"]
DEFAULT_CABLE_IFC_TYPES = ["IfcCableSegment", "IfcCableFitting"]
DEFAULT_CF_KEYWORDS = ["courant fort", "cf", "power", "puissance", "ht", "bt", "tgbt"]
DEFAULT_CFA_KEYWORDS = ["courant faible", "cfa", "data", "vdi", "rj45", "fibre", "fiber"]
DEFAULT_LENGTH_KEYS = ["Length", "Longueur", "Length_m", "Longueur_m"]
DEFAULT_WEIGHT_KEYS = ["Weight", "Poids", "Masse"]


class GAINE005CalculChargeSupportsChecker:
    RULE_ID = "GAINE-005"
    RULE_NAME = "Calcul charge supports cables"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        self.safety_margin = 0.20
        self.default_support_capacity = 90
        self.default_weight_per_m = 1.0
        self.cf_weight_per_m = 1.4
        self.cfa_weight_per_m = 0.6
        self.max_cable_distance = 0.6
        self.length_keys = list(DEFAULT_LENGTH_KEYS)
        self.weight_keys = list(DEFAULT_WEIGHT_KEYS)
        self.support_keywords = list(DEFAULT_SUPPORT_KEYWORDS)
        self.support_ifc_types = list(DEFAULT_SUPPORT_IFC_TYPES)
        self.cable_keywords = list(DEFAULT_CABLE_KEYWORDS)
        self.cable_ifc_types = list(DEFAULT_CABLE_IFC_TYPES)
        self.cf_keywords = list(DEFAULT_CF_KEYWORDS)
        self.cfa_keywords = list(DEFAULT_CFA_KEYWORDS)

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialise")

    def load_config(self):
        """Charge configuration regle"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
            self.config = config_full.get(self.RULE_ID, {})
            params = self.config.get('parameters', {})

            self.safety_margin = float(params.get('safety_margin_percent', 20)) / 100
            self.default_support_capacity = float(params.get('default_support_capacity_kg', 90))
            self.default_weight_per_m = float(params.get('default_weight_kg_per_m', 1.0))
            self.cf_weight_per_m = float(params.get('courant_fort_weight_kg_per_m', 1.4))
            self.cfa_weight_per_m = float(params.get('courant_faible_weight_kg_per_m', 0.6))
            self.max_cable_distance = float(params.get('max_cable_distance_m', 0.6))
            self.length_keys = list(params.get('length_property_keys', DEFAULT_LENGTH_KEYS))
            self.weight_keys = list(params.get('weight_property_keys', DEFAULT_WEIGHT_KEYS))
            self.support_keywords = [kw.lower() for kw in params.get('support_keywords', DEFAULT_SUPPORT_KEYWORDS)]
            self.cable_keywords = [kw.lower() for kw in params.get('cable_keywords', DEFAULT_CABLE_KEYWORDS)]
            self.cf_keywords = [kw.lower() for kw in params.get('courant_fort_keywords', DEFAULT_CF_KEYWORDS)]
            self.cfa_keywords = [kw.lower() for kw in params.get('courant_faible_keywords', DEFAULT_CFA_KEYWORDS)]
            self.support_ifc_types = list(params.get('support_ifc_types', DEFAULT_SUPPORT_IFC_TYPES))
            self.cable_ifc_types = list(params.get('cable_ifc_types', DEFAULT_CABLE_IFC_TYPES))

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-005"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        concerned_spaces = []
        concerned_spaces.extend(space_types.get('gaine_technique', []))
        concerned_spaces.extend(space_types.get('local_technique', []))
        concerned_spaces.extend(space_types.get('faux_plafond', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerne pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour calcul charge supports...")

        for space in concerned_spaces:
            self._analyze_space(space, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict]):
        """Analyse supports et cables dans un espace"""
        supports = []
        cables = []

        for eq in equipment:
            if not GeometryUtils.is_point_in_bbox(
                eq.get('centroid', (0, 0, 0)),
                space.get('bbox_min', (0, 0, 0)),
                space.get('bbox_max', (0, 0, 0))
            ):
                continue

            if self._is_support(eq):
                supports.append(eq)
                continue

            if self._is_cable(eq):
                cables.append(eq)

        if not supports or not cables:
            return

        for support in supports:
            self._check_support_load(space, support, cables)

    def _check_support_load(self, space: Dict, support: Dict, cables: List[Dict]):
        """Verifie la charge par support"""
        support_name = support.get('name', 'Inconnu')
        properties = support.get('properties', {})

        capacity = self._extract_capacity(properties)
        if capacity is None or capacity <= 0:
            capacity = self.default_support_capacity

        total_weight, total_length, cable_count = self._calculate_cable_load(support, cables)
        if cable_count == 0:
            return

        safe_capacity = capacity * (1 - self.safety_margin)

        if total_weight > safe_capacity:
            excess = total_weight - safe_capacity
            violation = {
                "rule_id": self.RULE_ID,
                "severity": "HAUTE",
                "space_name": space.get('name', 'Inconnu'),
                "space_global_id": space.get('global_id', ''),
                "description": "Charge des cables superieure a la capacite declaree du support",
                "details": {
                    "support_name": support_name,
                    "total_cable_weight_kg": round(total_weight, 1),
                    "total_cable_length_m": round(total_length, 1),
                    "cable_count": cable_count,
                    "support_capacity_kg": round(capacity, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1)
                },
                "location": support.get('centroid', (0, 0, 0)),
                "recommendation": "Redistribuer les cables ou renforcer le support pour respecter la marge de securite"
            }
            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, support_name,
                                 f"{total_weight:.1f}kg > {safe_capacity:.1f}kg")
        else:
            logger.rule_passed(self.RULE_ID, support_name)

    def _calculate_cable_load(self, support: Dict, cables: List[Dict]):
        """Somme des poids et longueurs des cables autour du support"""
        total_weight = 0.0
        total_length = 0.0
        count = 0
        support_centroid = support.get('centroid', (0, 0, 0))

        for cable in cables:
            cable_centroid = cable.get('centroid', (0, 0, 0))
            distance = GeometryUtils.calculate_distance_3d(support_centroid, cable_centroid)
            if distance > self.max_cable_distance:
                continue

            length = self._extract_length(cable)
            if length <= 0:
                length = cable.get('max_dimension_m') or 1.0

            weight = self._extract_weight(cable)
            if weight is None or weight <= 0:
                weight = length * self._select_weight_per_meter(cable)

            total_length += length
            total_weight += weight
            count += 1

        return total_weight, total_length, count

    def _extract_length(self, cable: Dict) -> float:
        props = cable.get('properties', {})
        for key in self.length_keys:
            if key in props:
                value = self._safe_float(props[key])
                if value and value > 0:
                    return value
        fallback = cable.get('max_dimension_m')
        return fallback if fallback else 1.0

    def _extract_weight(self, cable: Dict) -> Optional[float]:
        props = cable.get('properties', {})
        for key in self.weight_keys:
            if key in props:
                value = self._safe_float(props[key])
                if value and value > 0:
                    return value
        return None

    def _select_weight_per_meter(self, cable: Dict) -> float:
        combined = f"{cable.get('name', '')} {cable.get('ifc_type', '')}".lower()
        for kw in self.cf_keywords:
            if kw in combined:
                return self.cf_weight_per_m
        for kw in self.cfa_keywords:
            if kw in combined:
                return self.cfa_weight_per_m
        return self.default_weight_per_m

    def _is_support(self, equipment: Dict) -> bool:
        name = equipment.get('name', '').lower()
        if any(kw in name for kw in self.support_keywords):
            return True
        if equipment.get('ifc_type') in self.support_ifc_types:
            return True
        return False

    def _is_cable(self, equipment: Dict) -> bool:
        name = equipment.get('name', '').lower()
        if any(kw in name for kw in self.cable_keywords):
            return True
        if equipment.get('ifc_type') in self.cable_ifc_types:
            return True
        return False

    def _extract_capacity(self, properties: Dict) -> Optional[float]:
        capacity_keys = ['LoadCapacity', 'ChargeAdmissible', 'MaxLoad',
                         'Capacite', 'Capacity', 'ChargeMax']
        for key in capacity_keys:
            if key in properties:
                value = self._safe_float(properties[key])
                if value and value > 0:
                    return value
        return None

    def _safe_float(self, value, default: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default
        try:
            text = str(value).strip()
            if not text:
                return default
            text = text.replace(',', '.')
            return float(text)
        except:
            return default
