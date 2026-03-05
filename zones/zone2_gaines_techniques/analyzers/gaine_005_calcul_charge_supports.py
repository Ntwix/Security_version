"""
============================================================================
GAINE-005 - Calcul de charge cumulée des chemins de câbles
============================================================================
Règle: La charge cumulée (CFO + CFA + Incendie) sur un même chemin de câbles
ne doit pas dépasser la capacité admissible du support (avec marge sécurité).

Contexte CHU Ibn Sina:
- Chemins de câbles "Chemin de câbles avec raccords" (IfcCableCarrierSegment)
- Types : CDC CFO (1.4 kg/m), CDC CFA (0.6 kg/m), CDC Incendie (0.6 kg/m)
- Les chemins de câbles superposés (même X/Y, Z différents) sont analysés
  individuellement — chaque segment est son propre support.
- Charge estimée = longueur × poids/m selon type de service

Sévérité: HAUTE
"""

import json
from typing import List, Dict, Optional
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils

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
        self.default_support_capacity = 90.0
        self.default_weight_per_m = 1.0
        self.cf_weight_per_m = 1.4
        self.cfa_weight_per_m = 0.6
        self.max_cable_distance = 0.6
        self.length_keys = list(DEFAULT_LENGTH_KEYS)
        self.weight_keys = list(DEFAULT_WEIGHT_KEYS)
        self.cf_keywords = ["cfo", "cdc cfo", "courant fort", "power", "ht", "bt", "tgbt"]
        self.cfa_keywords = ["cfa", "cdc cfa", "cdc incendie", "courant faible", "data", "vdi",
                             "rj45", "fibre", "fiber"]

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

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-005"""
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        # Tous les chemins de câbles
        cable_trays = [eq for eq in equipment if self._is_cable_tray(eq)]

        if not cable_trays:
            logger.info(f"    Aucun chemin de câbles trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(cable_trays)} chemins de câbles — analyse charge cumulée...")

        # Grouper les chemins de câbles superposés (même position XY, tolérance 0.6m)
        # Chaque groupe = un même "point de support" potentiel
        groups = self._group_overlapping_trays(cable_trays)
        logger.info(f"   {len(groups)} groupes de chemins superposés détectés")

        for group in groups:
            self._check_group_load(group)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _group_overlapping_trays(self, cable_trays: List[Dict]) -> List[List[Dict]]:
        """
        Regroupe les chemins de câbles qui se superposent (même XY, Z différent).
        Un groupe = plusieurs CDC empilés au même endroit → charge cumulée sur le support.
        """
        groups = []
        used = set()

        for i, tray in enumerate(cable_trays):
            if i in used:
                continue
            group = [tray]
            used.add(i)
            c1 = tray.get('centroid', (0, 0, 0))

            for j, other in enumerate(cable_trays):
                if j in used:
                    continue
                c2 = other.get('centroid', (0, 0, 0))
                # Même position XY (tolérance max_cable_distance), Z peut différer
                dist_xy = ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
                if dist_xy <= self.max_cable_distance:
                    group.append(other)
                    used.add(j)

            groups.append(group)

        return groups

    def _check_group_load(self, group: List[Dict]):
        """Vérifie la charge cumulée d'un groupe de chemins superposés"""
        if not group:
            return

        total_weight = 0.0
        total_length = 0.0
        breakdown = []

        for tray in group:
            length = self._extract_length(tray)
            weight = self._extract_weight(tray)
            if weight is None or weight <= 0:
                weight = length * self._select_weight_per_meter(tray)

            total_weight += weight
            total_length += length
            breakdown.append({
                "name": tray.get('name', 'Inconnu'),
                "service_type": self._get_service_type(tray),
                "length_m": round(length, 2),
                "weight_kg": round(weight, 1),
            })

        safe_capacity = self.default_support_capacity * (1 - self.safety_margin)

        if total_weight > safe_capacity:
            excess = total_weight - safe_capacity
            ref_tray = group[0]

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "HAUTE",
                "space_name": ref_tray.get('name', 'Inconnu'),
                "space_global_id": ref_tray.get('global_id', ''),
                "description": (
                    f"Charge cumulée ({len(group)} chemins superposés) = {total_weight:.1f}kg "
                    f"> capacité admissible {safe_capacity:.1f}kg"
                ),
                "details": {
                    "nb_trays": len(group),
                    "total_cable_weight_kg": round(total_weight, 1),
                    "total_cable_length_m": round(total_length, 1),
                    "support_capacity_kg": round(self.default_support_capacity, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1),
                    "breakdown": breakdown,
                },
                "location": ref_tray.get('centroid', (0, 0, 0)),
                "recommendation": (
                    f"Renforcer le support ou répartir les chemins de câbles. "
                    f"Excès: {excess:.1f}kg. "
                    f"Détail: {', '.join(b['name'] + ' ' + b['service_type'] for b in breakdown)}"
                )
            }
            self.violations.append(violation)
            logger.rule_violation(
                self.RULE_ID,
                ref_tray.get('name', 'Inconnu'),
                f"{len(group)} CDC superposés — {total_weight:.1f}kg > {safe_capacity:.1f}kg"
            )
        else:
            logger.rule_passed(self.RULE_ID, group[0].get('name', 'Inconnu'))

    def _is_cable_tray(self, equipment: Dict) -> bool:
        """Vérifie si un équipement est un chemin de câbles"""
        if equipment.get('ifc_type') == 'IfcCableCarrierSegment':
            return True
        name = equipment.get('name', '').lower()
        return 'chemin de c' in name or 'cable tray' in name

    def _get_service_type(self, tray: Dict) -> str:
        """Extrait le type de service depuis les propriétés ou le nom"""
        props = self._props_to_dict(tray.get('properties', {}))
        service = props.get('Type de service', '') or props.get('Service Type', '') or ''
        if service:
            return service
        name = tray.get('name', '').lower()
        if 'incendie' in name:
            return 'CDC Incendie'
        for kw in self.cfa_keywords:
            if kw in name:
                return 'CDC CFA'
        for kw in self.cf_keywords:
            if kw in name:
                return 'CDC CFO'
        return 'Inconnu'

    def _select_weight_per_meter(self, tray: Dict) -> float:
        """Sélectionne le poids/m selon le type de service"""
        service = self._get_service_type(tray).lower()
        name = tray.get('name', '').lower()
        combined = f"{service} {name}"
        for kw in self.cfa_keywords:
            if kw in combined:
                return self.cfa_weight_per_m
        for kw in self.cf_keywords:
            if kw in combined:
                return self.cf_weight_per_m
        return self.default_weight_per_m

    def _extract_length(self, tray: Dict) -> float:
        """Extrait la longueur du chemin de câbles"""
        props = self._props_to_dict(tray.get('properties', {}))
        for key in self.length_keys:
            if key in props:
                value = self._safe_float(props[key])
                if value and value > 0:
                    return value
        # max_dimension_m = longueur réelle extraite depuis Revit (CURVE_ELEM_LENGTH)
        fallback = tray.get('max_dimension_m')
        return fallback if fallback and fallback > 0 else 1.0

    def _extract_weight(self, tray: Dict) -> Optional[float]:
        """Extrait le poids déclaré si disponible"""
        props = self._props_to_dict(tray.get('properties', {}))
        for key in self.weight_keys:
            if key in props:
                value = self._safe_float(props[key])
                if value and value > 0:
                    return value
        return None

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

    def _safe_float(self, value, default: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default
        try:
            text = str(value).strip().replace(',', '.')
            return float(text) if text else default
        except Exception:
            return default
