"""
============================================================================
FPLAF-002 - Surcharge plafond
============================================================================
Règle: Comparer le poids des câbles et équipements avec la capacité portante
des faux-plafonds. Le poids total ne doit pas dépasser la capacité portante
diminuée d'une marge de sécurité.

Sévérité: HAUTE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class FPLAF002SurchargePlafondChecker:
    """Analyseur règle FPLAF-002 - Surcharge plafond"""

    RULE_ID = "FPLAF-002"
    RULE_NAME = "Surcharge plafond - Poids câbles vs capacité portante"

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

            params = self.config.get('parameters', {})
            self.safety_margin = params.get('safety_margin_percent', 20) / 100
            self.default_ceiling_capacity = params.get('default_ceiling_capacity_kg_per_m2', 25)
            self.default_cable_weight = params.get('default_cable_weight_kg_per_m', 1.5)
            self.default_equipment_weight = params.get('default_equipment_weight_kg', 5.0)
            self.capacity_keys = params.get('capacity_property_keys',
                                            ['LoadCapacity', 'ChargeAdmissible', 'MaxLoad', 'Capacite', 'Capacity'])
            self.weight_keys = params.get('weight_property_keys',
                                          ['Weight', 'Poids', 'Masse', 'NetWeight', 'GrossWeight'])

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.safety_margin = 0.20
            self.default_ceiling_capacity = 25
            self.default_cable_weight = 1.5
            self.default_equipment_weight = 5.0
            self.capacity_keys = ['LoadCapacity', 'ChargeAdmissible', 'MaxLoad', 'Capacite', 'Capacity']
            self.weight_keys = ['Weight', 'Poids', 'Masse', 'NetWeight', 'GrossWeight']

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse FPLAF-002"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces concernés
        concerned_spaces = []
        concerned_spaces.extend(space_types.get('faux_plafond', []))
        concerned_spaces.extend(space_types.get('local_technique', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerné pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour surcharge plafond...")

        for space in concerned_spaces:
            self._analyze_space(space, equipment, slabs)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict], slabs: List[Dict]):
        """Analyse la surcharge dans un espace"""
        space_name = space.get('name', 'Inconnu')

        # Calculer la surface du plafond
        ceiling_area = self._calculate_ceiling_area(space)
        if ceiling_area <= 0:
            logger.debug(f"  {space_name}: Surface plafond non calculable, ignoré")
            return

        # Trouver la capacité portante
        ceiling_capacity_total = self._find_ceiling_capacity(space, slabs) * ceiling_area

        # Appliquer marge de sécurité
        safe_capacity = ceiling_capacity_total * (1 - self.safety_margin)

        # Calculer le poids total des équipements dans l'espace
        total_weight = self._calculate_equipment_weight(space, equipment)

        if total_weight > safe_capacity:
            excess = total_weight - safe_capacity

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "HAUTE",
                "space_name": space_name,
                "space_global_id": space.get('global_id', ''),
                "description": "Surcharge détectée sur faux-plafond",
                "details": {
                    "total_weight_kg": round(total_weight, 1),
                    "ceiling_area_m2": round(ceiling_area, 2),
                    "capacity_kg_per_m2": round(self.default_ceiling_capacity, 1),
                    "total_capacity_kg": round(ceiling_capacity_total, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1),
                    "load_ratio_percent": round((total_weight / ceiling_capacity_total) * 100, 1),
                    "safety_margin_percent": self.safety_margin * 100
                },
                "location": space.get('centroid', (0, 0, 0)),
                "recommendation": f"Réduire la charge sur le faux-plafond. "
                                 f"Excès: {excess:.1f}kg. "
                                 f"Redistribuer câbles ou renforcer la structure portante."
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, space_name,
                                f"{total_weight:.1f}kg > {safe_capacity:.1f}kg (capacité sûre)")
        else:
            logger.rule_passed(self.RULE_ID, space_name)

    def _calculate_ceiling_area(self, space: Dict) -> float:
        """Calcule la surface du plafond depuis les dimensions de l'espace"""
        # Essayer area_m2 direct
        area = space.get('area_m2') or 0
        if area > 0:
            return area

        # Calculer depuis bbox (projection XY)
        bbox_min = space.get('bbox_min', (0, 0, 0))
        bbox_max = space.get('bbox_max', (0, 0, 0))

        dx = bbox_max[0] - bbox_min[0]
        dy = bbox_max[1] - bbox_min[1]

        if dx > 0 and dy > 0:
            return dx * dy

        return 0

    def _find_ceiling_capacity(self, space: Dict, slabs: List[Dict]) -> float:
        """
        Trouve la capacité portante du plafond (kg/m2).
        Cherche d'abord dans les dalles au-dessus, puis valeur par défaut.
        """
        space_centroid = space.get('centroid', (0, 0, 0))
        properties = space.get('properties', {})

        # 1. Chercher dans les propriétés de l'espace
        for key in self.capacity_keys:
            if key in properties:
                try:
                    return float(properties[key])
                except (ValueError, TypeError):
                    pass

        # 2. Chercher dans les dalles au-dessus de l'espace
        for slab in slabs:
            slab_centroid = slab.get('centroid', (0, 0, 0))
            slab_props = slab.get('properties', {})

            # Dalle au-dessus si proche en XY et au-dessus en Z
            dx = abs(slab_centroid[0] - space_centroid[0])
            dy = abs(slab_centroid[1] - space_centroid[1])
            dz = slab_centroid[2] - space_centroid[2]

            if dx < 5 and dy < 5 and 0 < dz < 5:
                for key in self.capacity_keys:
                    if key in slab_props:
                        try:
                            return float(slab_props[key])
                        except (ValueError, TypeError):
                            pass

        return self.default_ceiling_capacity

    def _calculate_equipment_weight(self, space: Dict, equipment: List[Dict]) -> float:
        """Calcule le poids total des équipements dans l'espace"""
        total_weight = 0
        bbox_min = space.get('bbox_min', (0, 0, 0))
        bbox_max = space.get('bbox_max', (0, 0, 0))

        for eq in equipment:
            eq_centroid = eq.get('centroid', (0, 0, 0))

            if not GeometryUtils.is_point_in_bbox(eq_centroid, bbox_min, bbox_max):
                continue

            # Extraire le poids
            weight = self._extract_weight(eq)
            total_weight += weight

        return total_weight

    def _extract_weight(self, equipment: Dict) -> float:
        """Extrait le poids d'un équipement"""
        properties = equipment.get('properties', {})

        # Chercher poids déclaré
        for key in self.weight_keys:
            if key in properties:
                try:
                    return float(properties[key])
                except (ValueError, TypeError):
                    pass

        # Poids direct
        weight = equipment.get('weight_kg')
        if weight:
            return float(weight)

        # Estimation par type
        eq_name = equipment.get('name', '').lower()
        ifc_type = equipment.get('ifc_type', '')

        # Câbles: poids par longueur
        cable_keywords = ['câble', 'cable', 'fil', 'conducteur', 'wire']
        cable_ifc = ['IfcCableSegment', 'IfcCableFitting']
        if any(kw in eq_name for kw in cable_keywords) or any(t in ifc_type for t in cable_ifc):
            length = equipment.get('max_dimension_m', 1.0)
            return length * self.default_cable_weight

        # Autres équipements: poids par défaut
        return self.default_equipment_weight
