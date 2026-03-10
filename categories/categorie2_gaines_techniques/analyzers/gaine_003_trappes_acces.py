"""
============================================================================
GAINE-003 - Trappes d'accès aux équipements en gaine
============================================================================
Règle: Chaque équipement nécessitant une maintenance dans une gaine technique
doit être accessible via une trappe de visite (min 60x60cm).

Fonctionnement:
- Python extrait automatiquement tous les équipements présents dans les gaines
- Génère une liste structurée dans le JSON résultat
- Le plugin Revit C# affiche un formulaire interactif à l'utilisateur
- L'utilisateur sélectionne les équipements nécessitant une trappe
- Revit dessine un cercle à l'emplacement de chaque équipement sélectionné

Sévérité: MOYENNE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger


# Équipements prioritaires pour la maintenance
PRIORITY_KEYWORDS = [
    "tableau", "tgbt", "td-", "td_", "baie",
    "gaine a barre", "gaine à barre", "canalis", "busbar",
    "colonne montante", "cm-", "cm_",
    "coffret", "armoire",
    "baes",
]


class GAINE003TrappesAccesChecker:
    """Analyseur règle GAINE-003 - Trappes d'accès (formulaire interactif Revit)"""

    RULE_ID = "GAINE-003"
    RULE_NAME = "Trappes d'accès aux équipements en gaine"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        self.min_trappe_width = 0.60
        self.min_trappe_height = 0.60
        self.max_distance = 2.0

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
            self.config = config_full.get(self.RULE_ID, {})
            params = self.config.get('parameters', {})
            self.min_trappe_width = float(params.get('min_trappe_width_m', 0.60))
            self.min_trappe_height = float(params.get('min_trappe_height_m', 0.60))
            self.max_distance = float(params.get('max_distance_to_equipment_m', 2.0))
        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        Extrait tous les équipements dans les gaines techniques et génère
        une violation de type 'selection_requise' pour le formulaire Revit.
        Le plugin C# lit needs_trappe_selection=True pour ouvrir le dialog.
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        gaines = space_types.get('gaine_technique', [])
        gaines += space_types.get('local_technique', [])

        if not gaines:
            logger.info(f"    Aucune gaine technique identifiée pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   Extraction équipements dans {len(gaines)} gaines/locaux...")

        all_equipment_in_gaines = []

        for gaine in gaines:
            gaine_eqs = self._find_equipment_in_gaine(gaine, equipment)
            for eq in gaine_eqs:
                all_equipment_in_gaines.append({
                    "revit_element_id": eq.get('revit_element_id', 0),
                    "name": eq.get('name', 'Inconnu'),
                    "ifc_type": eq.get('ifc_type', ''),
                    "location": list(eq.get('centroid', [0, 0, 0])),
                    "gaine_name": gaine.get('name', 'Inconnu'),
                    "gaine_global_id": gaine.get('global_id', ''),
                    "priority": self._get_priority(eq),
                })

        if not all_equipment_in_gaines:
            logger.info(f"    Aucun équipement trouvé dans les gaines pour {self.RULE_ID}")
            return self.violations

        # Dédupliquer par revit_element_id
        seen = set()
        unique_eqs = []
        for eq in all_equipment_in_gaines:
            eid = eq['revit_element_id']
            if eid not in seen:
                seen.add(eid)
                unique_eqs.append(eq)

        # Trier : prioritaires d'abord, puis par nom
        unique_eqs.sort(key=lambda e: (0 if e['priority'] == 'haute' else 1, e['name']))

        nb_haute = sum(1 for e in unique_eqs if e['priority'] == 'haute')
        logger.info(f"   {len(unique_eqs)} équipements ({nb_haute} prioritaires)")

        # Violation unique de type formulaire interactif
        violation = {
            "rule_id": self.RULE_ID,
            "severity": "MOYENNE",
            "space_name": "Gaines Techniques",
            "space_global_id": "",
            "description": (
                f"{len(unique_eqs)} équipement(s) dans les gaines — "
                f"sélectionner ceux nécessitant une trappe de visite"
            ),
            "details": {
                "needs_trappe_selection": True,
                "min_trappe_width_m": self.min_trappe_width,
                "min_trappe_height_m": self.min_trappe_height,
                "equipment_list": unique_eqs,
                "total_equipment": len(unique_eqs),
                "priority_equipment": nb_haute,
            },
            "location": [0, 0, 0],
            "recommendation": (
                f"Ouvrir le formulaire GAINE-003 dans Revit pour sélectionner "
                f"les équipements nécessitant une trappe "
                f"(min {int(self.min_trappe_width*100)}x{int(self.min_trappe_height*100)}cm)."
            )
        }

        self.violations.append(violation)
        logger.analysis_complete(self.RULE_ID, len(unique_eqs))
        return self.violations

    def _find_equipment_in_gaine(self, gaine: Dict, equipment: List[Dict]) -> List[Dict]:
        """Trouve les équipements dans la bbox d'une gaine (tolérance 0.5m)"""
        result = []
        tolerance = 0.5
        bbox_min = gaine.get('bbox_min', (0, 0, 0))
        bbox_max = gaine.get('bbox_max', (0, 0, 0))

        for eq in equipment:
            centroid = eq.get('centroid', (0, 0, 0))
            in_range = (
                bbox_min[0] - tolerance <= centroid[0] <= bbox_max[0] + tolerance and
                bbox_min[1] - tolerance <= centroid[1] <= bbox_max[1] + tolerance and
                bbox_min[2] - tolerance <= centroid[2] <= bbox_max[2] + tolerance
            )
            if in_range:
                result.append(eq)

        return result

    def _get_priority(self, equipment: Dict) -> str:
        """Détermine si un équipement est prioritaire (tableau, gaine à barres...)"""
        name = equipment.get('name', '').lower()
        for kw in PRIORITY_KEYWORDS:
            if kw in name:
                return 'haute'
        return 'normale'
