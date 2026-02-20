"""
============================================================================
GAINE-003 - Trappes d'accès aux équipements
============================================================================
Règle: Chaque équipement dans une gaine technique doit être accessible
via une trappe d'accès de dimensions suffisantes.

Sévérité: MOYENNE
Inclut un formulaire interactif CLI (click.prompt) pour la saisie manuelle.
"""

import json
import click
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class GAINE003TrappesAccesChecker:
    """Analyseur règle GAINE-003 - Trappes d'accès"""

    RULE_ID = "GAINE-003"
    RULE_NAME = "Trappes d'accès aux équipements en gaine"

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

            self.min_trappe_width = self.config.get('parameters', {}).get('min_trappe_width_m', 0.60)
            self.min_trappe_height = self.config.get('parameters', {}).get('min_trappe_height_m', 0.60)
            self.max_distance = self.config.get('parameters', {}).get('max_distance_to_equipment_m', 2.0)

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.min_trappe_width = 0.60
            self.min_trappe_height = 0.60
            self.max_distance = 2.0

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """Lance analyse GAINE-003

        Args:
            doors: Liste des portes extraites (IfcDoor). Les trappes d'accès
                   sont souvent modélisées comme des portes dans le modèle ARCHI.
        """
        logger.analysis_start(self.RULE_ID)

        self.violations = []
        self.doors = doors or []

        # Espaces gaine technique
        gaines = space_types.get('gaine_technique', [])

        if not gaines:
            logger.info(f"    Aucune gaine technique identifiée pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Analyse {len(gaines)} gaines techniques pour trappes d'accès...")
        logger.info(f"   {len(self.doors)} portes disponibles pour recherche de trappes")

        for gaine in gaines:
            self._analyze_gaine(gaine, equipment)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_gaine(self, gaine: Dict, equipment: List[Dict]):
        """Analyse accessibilité des équipements dans une gaine"""
        gaine_name = gaine.get('name', 'Inconnu')

        # Trouver équipements dans la gaine
        gaine_equipment = []
        tolerance = 0.5

        for eq in equipment:
            eq_centroid = eq.get('centroid', (0, 0, 0))
            bbox_min = gaine.get('bbox_min', (0, 0, 0))
            bbox_max = gaine.get('bbox_max', (0, 0, 0))

            in_range = (
                bbox_min[0] - tolerance <= eq_centroid[0] <= bbox_max[0] + tolerance and
                bbox_min[1] - tolerance <= eq_centroid[1] <= bbox_max[1] + tolerance and
                bbox_min[2] - tolerance <= eq_centroid[2] <= bbox_max[2] + tolerance
            )

            if in_range:
                gaine_equipment.append(eq)

        if not gaine_equipment:
            logger.debug(f"  {gaine_name}: Aucun équipement dans la gaine")
            return

        # Chercher trappes (IfcDoor ou éléments nommés "trappe")
        has_trappe = self._find_trappes_nearby(gaine, equipment)

        if not has_trappe:
            eq_names = [eq.get('name', '') for eq in gaine_equipment[:5]]

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "MOYENNE",
                "space_name": gaine_name,
                "space_global_id": gaine.get('global_id', ''),
                "description": "Équipements en gaine sans trappe d'accès identifiée",
                "details": {
                    "equipment_count": len(gaine_equipment),
                    "equipment_list": eq_names,
                    "min_trappe_width_m": self.min_trappe_width,
                    "min_trappe_height_m": self.min_trappe_height,
                    "trappe_found": False
                },
                "location": gaine.get('centroid', (0, 0, 0)),
                "recommendation": f"Installer trappe d'accès (min {self.min_trappe_width*100:.0f}x"
                                 f"{self.min_trappe_height*100:.0f}cm) pour {len(gaine_equipment)} équipement(s)"
            }

            self.violations.append(violation)
            logger.rule_violation(self.RULE_ID, gaine_name,
                                f"{len(gaine_equipment)} équipements sans trappe d'accès")
        else:
            logger.rule_passed(self.RULE_ID, gaine_name)

    def _is_in_range(self, centroid, bbox_min, bbox_max, tolerance) -> bool:
        """Vérifie si un point est dans la bbox étendue par la tolérance"""
        return (
            bbox_min[0] - tolerance <= centroid[0] <= bbox_max[0] + tolerance and
            bbox_min[1] - tolerance <= centroid[1] <= bbox_max[1] + tolerance and
            bbox_min[2] - tolerance <= centroid[2] <= bbox_max[2] + tolerance
        )

    def _find_trappes_nearby(self, gaine: Dict, equipment: List[Dict]) -> bool:
        """Cherche des trappes d'accès à proximité de la gaine.

        Cherche dans deux sources :
        1. Les équipements (nommés trappe/hatch/access/panneau/visite)
        2. Les portes du modèle ARCHI (les trappes sont souvent modélisées comme IfcDoor)
        """
        bbox_min = gaine.get('bbox_min', (0, 0, 0))
        bbox_max = gaine.get('bbox_max', (0, 0, 0))
        tolerance = self.max_distance

        trappe_keywords = ['trappe', 'hatch', 'access', 'panneau', 'visite']

        # 1. Chercher dans les équipements
        for eq in equipment:
            eq_centroid = eq.get('centroid', (0, 0, 0))
            if not self._is_in_range(eq_centroid, bbox_min, bbox_max, tolerance):
                continue

            eq_name = eq.get('name', '').lower()
            if any(kw in eq_name for kw in trappe_keywords):
                return True

            ifc_type = eq.get('ifc_type', '')
            if 'Door' in ifc_type or 'Opening' in ifc_type:
                width = (eq.get('width_m') or 0) or (eq.get('max_dimension_m') or 0)
                if width >= self.min_trappe_width:
                    return True

        # 2. Chercher dans les portes du modèle ARCHI
        for door in self.doors:
            door_centroid = door.get('centroid', (0, 0, 0))
            if not self._is_in_range(door_centroid, bbox_min, bbox_max, tolerance):
                continue

            door_name = door.get('name', '').lower()
            door_width = door.get('width_m') or 0

            # Porte nommée comme trappe
            if any(kw in door_name for kw in trappe_keywords):
                return True

            # Porte à proximité directe de la gaine avec dimensions suffisantes
            if door_width >= self.min_trappe_width:
                return True

        return False

    def interactive_trappe_assignment(self, gaines: List[Dict], equipment: List[Dict]):
        """
        Mode interactif CLI pour assigner manuellement les trappes aux gaines.
        Utilise click.prompt pour la saisie.
        """
        print("\n" + "=" * 70)
        print("  MODE INTERACTIF - ASSIGNATION TRAPPES D'ACCÈS")
        print("=" * 70)

        for i, gaine in enumerate(gaines):
            gaine_name = gaine.get('name', f'Gaine_{i}')
            print(f"\n--- Gaine: {gaine_name} ---")

            # Lister équipements dans la gaine
            gaine_eq = []
            for eq in equipment:
                if GeometryUtils.is_point_in_bbox(
                    eq.get('centroid', (0, 0, 0)),
                    gaine.get('bbox_min', (0, 0, 0)),
                    gaine.get('bbox_max', (0, 0, 0))
                ):
                    gaine_eq.append(eq)

            if not gaine_eq:
                print("  Aucun équipement détecté")
                continue

            print(f"  {len(gaine_eq)} équipement(s):")
            for j, eq in enumerate(gaine_eq):
                print(f"    [{j+1}] {eq.get('name', 'Inconnu')}")

            has_trappe = click.prompt(
                "  Trappe d'accès existante ?",
                type=click.Choice(['oui', 'non']),
                default='non'
            )

            if has_trappe == 'non':
                emplacement = click.prompt(
                    "  Emplacement recommandé pour la trappe",
                    default=f"Près de {gaine_name}"
                )
                print(f"  -> Trappe à prévoir: {emplacement}")

        print("\n" + "=" * 70)
