"""
============================================================================
CHANT-001 - Manutention des équipements lourds
============================================================================
Règle: Lors de l'installation d'équipements électriques lourds (tableaux,
armoires, TGBT...), le chemin d'accès depuis l'entrée du bâtiment jusqu'au
local technique doit permettre le passage de ces équipements.
Toute porte ou couloir sur ce trajet dont la largeur est insuffisante
représente un risque de blessure pour les ouvriers et d'endommagement du matériel.

Fonctionnement:
- Python extrait les locaux techniques et leurs équipements lourds
- Génère une liste dans le JSON résultat
- Le plugin Revit C# affiche un formulaire interactif
- L'utilisateur sélectionne les portes/couloirs sur le chemin d'accès
- Violation si largeur < dimension max de l'équipement à transporter

Sévérité: HAUTE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger

# Seuil de poids pour considérer un équipement "lourd"
POIDS_LOURD_KG = 50.0

# Largeur minimale requise pour passage (mètres)
LARGEUR_MIN_PORTE_M = 0.90
LARGEUR_MIN_COULOIR_M = 1.20

# Mots-clés pour identifier les équipements lourds
EQUIPEMENT_LOURD_KEYWORDS = [
    "tableau", "tgbt", "td-", "td_", "armoire", "baie",
    "coffret", "onduleur", "ups", "groupe électrogène",
    "transformateur", "chargeur", "batterie"
]


class CHANT001ManutentionChecker:
    """Analyseur CHANT-001 - Manutention équipements lourds (formulaire interactif)"""

    RULE_ID = "CHANT-001"
    RULE_NAME = "Manutention des équipements lourds"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        Extrait les locaux techniques avec leurs équipements lourds et les portes.
        Produit un marker JSON pour le formulaire interactif C#.
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        locaux_techniques = space_types.get('local_technique', [])
        if not locaux_techniques:
            logger.info(f"    Aucun local technique trouvé pour {self.RULE_ID}")
            return self.violations

        # Trouver les équipements lourds dans les locaux techniques
        equipements_lourds = []
        for eq in equipment:
            if not self._is_equipement_lourd(eq):
                continue
            # Trouver le local technique contenant cet équipement
            local = self._find_local_for_equipment(eq, locaux_techniques)
            if local:
                equipements_lourds.append({
                    "name": eq.get('name', 'Inconnu'),
                    "local_name": local.get('name', 'Inconnu'),
                    "local_global_id": local.get('global_id', ''),
                    "weight_kg": eq.get('weight_kg') or 0,
                    "dimensions_m": self._get_dimensions(eq),
                    "location": list(eq.get('centroid', [0, 0, 0])),
                    "ifc_type": eq.get('ifc_type', ''),
                    "revit_element_id": eq.get('revit_element_id', 0)
                })

        if not equipements_lourds:
            logger.info(f"    Aucun équipement lourd trouvé pour {self.RULE_ID}")
            return self.violations

        # Extraire les portes disponibles pour le formulaire
        portes_info = []
        for door in (doors or []):
            portes_info.append({
                "name": door.get('name', 'Porte inconnue'),
                "global_id": door.get('global_id', ''),
                "width_m": door.get('width_m') or door.get('width') or 0.9,
                "location": list(door.get('centroid', [0, 0, 0])),
                "space_name": door.get('space_name', '')
            })

        logger.info(f"   {len(equipements_lourds)} équipements lourds — {len(portes_info)} portes")

        # Violation marker pour le formulaire C#
        self.violations.append({
            "rule_id": self.RULE_ID,
            "severity": "HAUTE",
            "space_name": "Locaux techniques — en attente de saisie utilisateur",
            "space_global_id": "",
            "description": f"Vérification manutention requise pour {len(equipements_lourds)} équipements lourds",
            "details": {
                "equipements_lourds": equipements_lourds,
                "portes_disponibles": portes_info,
                "largeur_min_porte_m": LARGEUR_MIN_PORTE_M,
                "largeur_min_couloir_m": LARGEUR_MIN_COULOIR_M,
            },
            "location": [0, 0, 0],
            "recommendation": "Sélectionner les portes/couloirs sur le chemin d'accès dans le formulaire CHANT-001."
        })

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _is_equipement_lourd(self, eq: Dict) -> bool:
        name = (eq.get('name', '') or '').lower()
        for kw in EQUIPEMENT_LOURD_KEYWORDS:
            if kw in name:
                return True
        weight = eq.get('weight_kg') or 0
        return weight >= POIDS_LOURD_KG

    def _find_local_for_equipment(self, eq: Dict, locaux: List[Dict]) -> Dict:
        """Trouve le local technique qui contient l'équipement (par bbox)."""
        eq_centroid = eq.get('centroid', (0, 0, 0))
        for local in locaux:
            bbox_min = local.get('bbox_min', (0, 0, 0))
            bbox_max = local.get('bbox_max', (0, 0, 0))
            if (bbox_min[0] <= eq_centroid[0] <= bbox_max[0] and
                bbox_min[1] <= eq_centroid[1] <= bbox_max[1] and
                bbox_min[2] <= eq_centroid[2] <= bbox_max[2]):
                return local
        return None

    def _get_dimensions(self, eq: Dict) -> Dict:
        bbox_min = eq.get('bbox_min', (0, 0, 0))
        bbox_max = eq.get('bbox_max', (0, 0, 0))
        return {
            "width_m": round(abs(bbox_max[0] - bbox_min[0]), 2),
            "depth_m": round(abs(bbox_max[1] - bbox_min[1]), 2),
            "height_m": round(abs(bbox_max[2] - bbox_min[2]), 2),
        }
