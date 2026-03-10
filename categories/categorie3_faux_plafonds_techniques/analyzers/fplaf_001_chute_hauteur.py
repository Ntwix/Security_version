"""
============================================================================
FPLAF-001 - Chute de hauteur
============================================================================
Règle: Vérifier la hauteur des pièces avec faux-plafond.
Les hauteurs supérieures à un seuil indiquent un risque de chute
lors des interventions en faux-plafond.

Fonctionnalités:
- Extraction automatique des hauteurs depuis la maquette IFC
- Support multi-unités (m, cm, mm) avec conversion automatique
- Seuils configurables (min, max sécuritaire, critique)

Sévérité: MOYENNE
"""

import json
import click
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class FPLAF001ChuteHauteurChecker:
    """Analyseur règle FPLAF-001 - Chute de hauteur"""

    RULE_ID = "FPLAF-001"
    RULE_NAME = "Chute de hauteur - Hauteur des pièces"

    # Facteurs de conversion vers mètres
    UNIT_FACTORS = {
        'm': 1.0,
        'cm': 0.01,
        'mm': 0.001
    }

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
            self.min_height = params.get('min_height_m', 2.50)
            self.max_safe_height = params.get('max_safe_height_m', 3.00)
            self.critical_height = params.get('critical_height_m', 4.00)
            self.default_unit = params.get('default_unit', 'm')
            self.height_property_keys = params.get('height_property_keys',
                                                    ['Height', 'OverallHeight', 'Hauteur', 'ClearHeight', 'NetHeight'])

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.min_height = 2.50
            self.max_safe_height = 3.00
            self.critical_height = 4.00
            self.default_unit = 'm'
            self.height_property_keys = ['Height', 'OverallHeight', 'Hauteur', 'ClearHeight', 'NetHeight']

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse FPLAF-001"""
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces concernés
        concerned_spaces = []
        concerned_spaces.extend(space_types.get('faux_plafond', []))
        concerned_spaces.extend(space_types.get('local_technique', []))
        concerned_spaces.extend(space_types.get('circulation', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerné pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour risque chute de hauteur...")

        for space in concerned_spaces:
            self._analyze_space_height(space)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _extract_height_m(self, space: Dict) -> float:
        """
        Extrait la hauteur d'un espace en mètres.
        Cherche dans les propriétés IFC puis dans les données géométriques.
        """
        properties = space.get('properties', {})

        # 1. Chercher dans les propriétés IFC
        for key in self.height_property_keys:
            if key in properties:
                try:
                    raw_value = float(properties[key])
                    # Déterminer l'unité: si la valeur > 100, probablement en cm ou mm
                    if raw_value > 100:
                        return raw_value * self.UNIT_FACTORS['mm']
                    elif raw_value > 10:
                        return raw_value * self.UNIT_FACTORS['cm']
                    else:
                        return raw_value
                except (ValueError, TypeError):
                    pass

        # 2. Utiliser height_m déjà calculé par l'extracteur
        height = space.get('height_m') or 0
        if height > 0:
            return height

        # 3. Calculer depuis bbox
        bbox_min = space.get('bbox_min', (0, 0, 0))
        bbox_max = space.get('bbox_max', (0, 0, 0))
        if bbox_max[2] > bbox_min[2]:
            return bbox_max[2] - bbox_min[2]

        return 0

    def _analyze_space_height(self, space: Dict):
        """Analyse la hauteur d'un espace et détecte les risques"""
        space_name = space.get('name', 'Inconnu')
        height_m = self._extract_height_m(space)

        if height_m <= 0:
            logger.debug(f"  {space_name}: Hauteur non disponible, ignoré")
            return

        # Déterminer le niveau de risque
        if height_m >= self.critical_height:
            severity = "HAUTE"
            risk_level = "CRITIQUE"
            description = f"Hauteur critique pour travail en faux-plafond ({height_m:.2f}m >= {self.critical_height:.2f}m)"
            recommendation = (f"Hauteur {height_m:.2f}m - Utiliser obligatoirement un échafaudage ou "
                            f"une nacelle élévatrice. Harnais de sécurité requis.")
        elif height_m > self.max_safe_height:
            severity = "MOYENNE"
            risk_level = "ÉLEVÉ"
            description = f"Hauteur élevée pour travail en faux-plafond ({height_m:.2f}m > {self.max_safe_height:.2f}m)"
            recommendation = (f"Hauteur {height_m:.2f}m - Prévoir un escabeau sécurisé ou "
                            f"une plateforme individuelle roulante (PIR).")
        else:
            # Hauteur dans la plage sécuritaire
            logger.rule_passed(self.RULE_ID, space_name)
            return

        violation = {
            "rule_id": self.RULE_ID,
            "severity": severity,
            "space_name": space_name,
            "space_global_id": space.get('global_id', ''),
            "description": description,
            "details": {
                "height_m": round(height_m, 2),
                "height_cm": round(height_m * 100, 1),
                "min_safe_height_m": self.min_height,
                "max_safe_height_m": self.max_safe_height,
                "critical_height_m": self.critical_height,
                "risk_level": risk_level,
                "unit_used": "m"
            },
            "location": space.get('centroid', (0, 0, 0)),
            "recommendation": recommendation
        }

        self.violations.append(violation)
        logger.rule_violation(self.RULE_ID, space_name,
                            f"Hauteur {height_m:.2f}m - Risque {risk_level}")

    def interactive_unit_selection(self):
        """Mode interactif CLI pour sélectionner l'unité de mesure.
        Utilise click.prompt pour la saisie."""
        
        print("\n" + "=" * 70)
        print("  FPLAF-001 - SÉLECTION UNITÉ DE MESURE")
        print("=" * 70)

        unit = click.prompt(
            "\n  Unité de mesure de la maquette",
            type=click.Choice(['m', 'cm', 'mm']),
            default=self.default_unit
        )

        factor = self.UNIT_FACTORS[unit]
        print(f"\n  -> Unité sélectionnée: {unit} (facteur conversion: {factor})")
        print(f"  -> Seuil sécuritaire: {self.max_safe_height / factor:.1f} {unit}")
        print(f"  -> Seuil critique:    {self.critical_height / factor:.1f} {unit}")
        print("=" * 70)

        return unit
