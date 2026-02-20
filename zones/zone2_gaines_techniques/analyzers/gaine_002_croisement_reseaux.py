"""
============================================================================
GAINE-002 - Croisement réseaux courant fort / courant faible
============================================================================
Règle: La distance entre supports courant fort et courant faible doit être
>= 30 cm pour éviter les interférences électromagnétiques.

Sévérité: CRITIQUE
"""

import json
import re
from typing import List, Dict, Tuple
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class GAINE002CroisementReseauxChecker:
    """Analyseur règle GAINE-002 - Croisement réseaux"""

    RULE_ID = "GAINE-002"
    RULE_NAME = "Croisement réseaux courant fort / courant faible"

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

            self.min_distance = self.config.get('parameters', {}).get('min_distance_m', 0.30)
            self.cf_keywords = self.config.get('parameters', {}).get('courant_fort_keywords',
                                                                      ['cf', 'courant fort', 'power'])
            self.cfa_keywords = self.config.get('parameters', {}).get('courant_faible_keywords',
                                                                       ['cfa', 'courant faible', 'data', 'vdi'])

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.min_distance = 0.30
            self.cf_keywords = ['cf', 'courant fort', 'power']
            self.cfa_keywords = ['cfa', 'courant faible', 'data', 'vdi']

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-002"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces concernés (gaines + locaux techniques)
        concerned_spaces = []
        concerned_spaces.extend(space_types.get('gaine_technique', []))
        concerned_spaces.extend(space_types.get('local_technique', []))
        concerned_spaces.extend(space_types.get('faux_plafond', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerné pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour croisement réseaux...")

        for space in concerned_spaces:
            self._analyze_space(space, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _classify_equipment(self, eq: Dict) -> str:
        """Classifie un équipement comme courant_fort, courant_faible ou autre.

        Ordre important : tester CFA d'abord (plus spécifique) car 'cf' est
        un sous-ensemble de 'cfa' et matcherait à tort les équipements CFA.
        Ensuite classifier par type IFC en fallback.
        """
        name = eq.get('name', '').lower()
        ifc_type = eq.get('ifc_type', '')
        combined = f"{name} {ifc_type}".lower()

        # CFA d'abord (plus spécifique, évite que 'cf' matche 'cfa')
        for kw in self.cfa_keywords:
            if kw.lower() in combined:
                return 'courant_faible'

        for kw in self.cf_keywords:
            if kw.lower() in combined:
                return 'courant_fort'

        # Fallback par type IFC
        cfa_ifc_types = ['IfcCommunicationsAppliance', 'IfcAudioVisualAppliance',
                         'IfcAlarm', 'IfcSensor']
        cf_ifc_types = ['IfcElectricDistributionBoard', 'IfcTransformer',
                        'IfcElectricGenerator']

        for t in cfa_ifc_types:
            if t in ifc_type:
                return 'courant_faible'
        for t in cf_ifc_types:
            if t in ifc_type:
                return 'courant_fort'

        return 'autre'

    def _analyze_space(self, space: Dict, equipment: List[Dict]):
        """Analyse croisements dans un espace"""
        space_name = space.get('name', 'Inconnu')

        # Trouver équipements dans l'espace
        space_equipment = []
        for eq in equipment:
            if GeometryUtils.is_point_in_bbox(
                eq.get('centroid', (0, 0, 0)),
                space.get('bbox_min', (0, 0, 0)),
                space.get('bbox_max', (0, 0, 0))
            ):
                eq_type = self._classify_equipment(eq)
                if eq_type != 'autre':
                    space_equipment.append((eq, eq_type))

        # Séparer courant fort et courant faible
        cf_equipment = [(eq, t) for eq, t in space_equipment if t == 'courant_fort']
        cfa_equipment = [(eq, t) for eq, t in space_equipment if t == 'courant_faible']

        if not cf_equipment or not cfa_equipment:
            return

        # Vérifier distances entre chaque paire CF/CFA
        for eq_cf, _ in cf_equipment:
            for eq_cfa, _ in cfa_equipment:
                cf_centroid = eq_cf.get('centroid', (0, 0, 0))
                cfa_centroid = eq_cfa.get('centroid', (0, 0, 0))

                distance = GeometryUtils.calculate_distance_3d(cf_centroid, cfa_centroid)

                if distance < self.min_distance:
                    shortage = self.min_distance - distance

                    violation = {
                        "rule_id": self.RULE_ID,
                        "severity": "CRITIQUE",
                        "space_name": space_name,
                        "space_global_id": space.get('global_id', ''),
                        "description": "Distance insuffisante entre courant fort et courant faible",
                        "details": {
                            "equipment_cf": eq_cf.get('name', ''),
                            "equipment_cfa": eq_cfa.get('name', ''),
                            "actual_distance_m": round(distance, 3),
                            "required_distance_m": self.min_distance,
                            "shortage_m": round(shortage, 3)
                        },
                        "location": cf_centroid,
                        "recommendation": f"Séparer les réseaux CF/CFA d'au moins {self.min_distance*100:.0f}cm. "
                                         f"Manque: {shortage*100:.1f}cm"
                    }

                    self.violations.append(violation)
                    logger.rule_violation(self.RULE_ID, space_name,
                                        f"{eq_cf.get('name', '')} <-> {eq_cfa.get('name', '')}: "
                                        f"{distance*100:.1f}cm < {self.min_distance*100:.0f}cm")
