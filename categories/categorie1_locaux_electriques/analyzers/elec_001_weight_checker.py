"""
============================================================================
ELEC-001 - Vérification Poids Équipements vs Capacité Dalle
============================================================================
Règle: Le poids des équipements ne doit pas dépasser la capacité de charge
de la dalle du local technique.

Seuil: 150 kg (modifiable dans config/rules_config.json)
Marge sécurité: 10%
"""

import json
from typing import List, Dict, Tuple
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class ELEC001WeightChecker:
    """Analyseur règle ELEC-001 - Poids équipements"""

    RULE_ID = "ELEC-001"
    RULE_NAME = "Vérification poids équipements vs capacité dalle"

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

            # Paramètres
            self.weight_threshold = self.config.get('parameters', {}).get('weight_threshold_kg', 150)
            self.safety_margin = self.config.get('parameters', {}).get('safety_margin_percent', 10) / 100
            self.check_cumulative = self.config.get('parameters', {}).get('check_cumulative_weight', True)

            logger.debug(f"  Config {self.RULE_ID}: seuil={self.weight_threshold}kg, marge={self.safety_margin*100}%")

        except Exception as e:
            logger.error(f"  Erreur chargement config {self.RULE_ID}: {str(e)}")
            # Valeurs par défaut
            self.weight_threshold = 150
            self.safety_margin = 0.10
            self.check_cumulative = True

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """
        Lance l'analyse ELEC-001

        Args:
            spaces: Liste espaces extraits
            equipment: Liste équipements extraits
            slabs: Liste dalles extraites
            space_types: Classification espaces

        Returns:
            Liste violations détectées
        """
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Ne vérifier que les locaux techniques (local_technique)
        technical_rooms = space_types.get('local_technique', [])

        if not technical_rooms:
            logger.warning(f"   Aucun local technique identifié pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(technical_rooms)} locaux techniques...")

        for space in technical_rooms:
            self._analyze_space(space, equipment, slabs)

        logger.analysis_complete(self.RULE_ID, len(self.violations))

        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict], slabs: List[Dict]):
        """Analyse un espace spécifique"""
        space_name = space['name']

        # 1. Trouver équipements dans cet espace
        space_equipment = self._find_equipment_in_space(space, equipment)

        if not space_equipment:
            logger.debug(f"  {space_name}: Aucun équipement")
            return

        # 2. Calculer poids total
        total_weight = self._calculate_total_weight(space_equipment)

        if total_weight == 0:
            logger.debug(f"  {space_name}: Poids non spécifié")
            return

        # 3. Trouver dalle supportante
        slab = self._find_supporting_slab(space, slabs)

        # 4. Vérifier capacité
        if self.check_cumulative:
            # Vérifier poids cumulé
            self._check_cumulative_weight(space, space_equipment, total_weight, slab)
        else:
            # Vérifier chaque équipement individuellement
            for eq in space_equipment:
                eq_weight = eq.get('weight_kg') or 0
                if eq_weight > 0:
                    self._check_individual_weight(space, eq, eq_weight, slab)

    def _find_equipment_in_space(self, space: Dict, equipment: List[Dict]) -> List[Dict]:
        """Trouve les équipements situés dans un espace"""
        space_equipment = []

        space_bbox_min = space['bbox_min']
        space_bbox_max = space['bbox_max']

        for eq in equipment:
            eq_centroid = eq['centroid']

            # Vérifier si centroïde équipement dans bbox espace
            if GeometryUtils.is_point_in_bbox(eq_centroid, space_bbox_min, space_bbox_max):
                space_equipment.append(eq)

        return space_equipment

    def _calculate_total_weight(self, equipment_list: List[Dict]) -> float:
        """Calcule poids total des équipements"""
        total = 0

        for eq in equipment_list:
            weight = eq.get('weight_kg')
            if weight and weight > 0:
                total += weight

        return total

    def _find_supporting_slab(self, space: Dict, slabs: List[Dict]) -> Dict:
        """Trouve la dalle supportant l'espace"""
        # Simplification: prendre dalle la plus proche en Z
        space_z = space['bbox_min'][2]

        closest_slab = None
        min_distance = float('inf')

        for slab in slabs:
            slab_z = slab['bbox_max'][2]  # Dessus dalle
            distance = abs(space_z - slab_z)

            if distance < min_distance and distance < 0.5:  # < 50cm
                min_distance = distance
                closest_slab = slab

        return closest_slab

    def _check_cumulative_weight(self, space: Dict, equipment_list: List[Dict],
                                 total_weight: float, slab: Dict):
        """Vérifie poids cumulé vs capacité dalle"""
        space_name = space['name']

        # Capacité dalle
        if slab and slab.get('load_capacity_kg'):
            capacity = slab['load_capacity_kg']
        else:
            # Valeur par défaut si non spécifiée
            capacity = self.weight_threshold

        # Appliquer marge sécurité
        safe_capacity = capacity * (1 - self.safety_margin)

        # Vérifier
        if total_weight > safe_capacity:
            excess = total_weight - safe_capacity

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "CRITICAL",
                "space_name": space_name,
                "space_global_id": space['global_id'],
                "description": f"Poids cumulé équipements dépasse capacité dalle",
                "details": {
                    "total_weight_kg": round(total_weight, 1),
                    "slab_capacity_kg": round(capacity, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1),
                    "safety_margin_percent": self.safety_margin * 100,
                    "equipment_count": len(equipment_list),
                    "equipment_list": [
                        {
                            "name": eq['name'],
                            "weight_kg": eq.get('weight_kg') or 0
                        } for eq in equipment_list if (eq.get('weight_kg') or 0) > 0
                    ]
                },
                "location": space['centroid'],
                "recommendation": f"Renforcement dalle ou redistribution charge requise. "
                                 f"Excès: {round(excess, 1)}kg"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, space_name,
                                f"{total_weight:.1f}kg > {safe_capacity:.1f}kg (excès: {excess:.1f}kg)")
        else:
            logger.rule_passed(self.RULE_ID, space_name)

    def _check_individual_weight(self, space: Dict, equipment: Dict,
                                 weight: float, slab: Dict):
        """Vérifie poids individuel équipement"""
        if slab and slab.get('load_capacity_kg'):
            capacity = slab['load_capacity_kg']
        else:
            capacity = self.weight_threshold

        safe_capacity = capacity * (1 - self.safety_margin)

        if weight > safe_capacity:
            excess = weight - safe_capacity

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "CRITICAL",
                "space_name": space['name'],
                "space_global_id": space['global_id'],
                "description": f"Équipement individuel trop lourd",
                "details": {
                    "equipment_name": equipment['name'],
                    "equipment_weight_kg": round(weight, 1),
                    "slab_capacity_kg": round(capacity, 1),
                    "safe_capacity_kg": round(safe_capacity, 1),
                    "excess_kg": round(excess, 1)
                },
                "location": equipment['centroid'],
                "recommendation": f"Renforcement dalle ou relocalisation équipement requise"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, equipment['name'],
                                f"{weight:.1f}kg > {safe_capacity:.1f}kg")
