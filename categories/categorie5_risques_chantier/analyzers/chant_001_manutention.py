"""
============================================================================
CHANT-001 - Manutention des équipements lourds
============================================================================
Règle: Lors de l'installation d'équipements électriques lourds (tableaux,
armoires, TGBT...), le chemin d'accès depuis l'entrée du bâtiment jusqu'au
local technique doit permettre le passage de ces équipements.

Fonctionnement:
- Python extrait les locaux techniques, équipements lourds, portes, escaliers
- Sauvegarde dans le JSON résultat avec clé "chant001_data"
- Le plugin Revit C# affiche un formulaire interactif
- L'utilisateur coche les obstacles sur le chemin (portes, escaliers, ascenseurs)
- Violation si un obstacle est trop étroit pour l'équipement

Sévérité: HAUTE
"""

from typing import List, Dict
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

# Mots-clés pour identifier les escaliers dans les espaces
ESCALIER_KEYWORDS = [
    "escalier", "esc.", "stair", "cage", "montée"
]

# Mots-clés pour identifier les ascenseurs
ASCENSEUR_KEYWORDS = [
    "ascenseur", "lift", "elevator", "monte-charge"
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
        Extrait les locaux techniques avec leurs équipements lourds,
        les portes, escaliers et ascenseurs disponibles.
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
            local = self._find_local_for_equipment(eq, locaux_techniques)
            if local:
                dims = self._get_dimensions(eq)
                dim_max = max(dims.get('width_m', 0), dims.get('depth_m', 0))
                equipements_lourds.append({
                    "name": eq.get('name', 'Inconnu'),
                    "local_name": local.get('name', 'Inconnu'),
                    "local_global_id": local.get('global_id', ''),
                    "weight_kg": eq.get('weight_kg') or 0,
                    "dimensions_m": dims,
                    "dim_max_m": round(dim_max, 2),
                    "location": list(eq.get('centroid', [0, 0, 0])),
                    "ifc_type": eq.get('ifc_type', ''),
                    "global_id": eq.get('global_id', '')
                })

        if not equipements_lourds:
            logger.info(f"    Aucun équipement lourd trouvé pour {self.RULE_ID}")
            return self.violations

        # Extraire les portes
        portes_info = []
        for door in (doors or []):
            portes_info.append({
                "type": "porte",
                "name": door.get('name', 'Porte inconnue'),
                "global_id": door.get('global_id', ''),
                "width_m": round(door.get('width_m') or door.get('width') or 0.9, 2),
                "location": list(door.get('centroid', [0, 0, 0])),
                "space_name": door.get('space_name', '')
            })

        # Extraire les escaliers depuis les espaces
        escaliers_info = []
        for sp in spaces:
            name = (sp.get('name', '') or '').lower()
            if any(kw in name for kw in ESCALIER_KEYWORDS):
                bbox_min = sp.get('bbox_min', [0, 0, 0])
                bbox_max = sp.get('bbox_max', [0, 0, 0])
                width = round(abs(bbox_max[0] - bbox_min[0]) if bbox_min and bbox_max else 1.2, 2)
                escaliers_info.append({
                    "type": "escalier",
                    "name": sp.get('name', 'Escalier'),
                    "global_id": sp.get('global_id', ''),
                    "width_m": max(width, 0.80),
                    "location": list(sp.get('centroid', [0, 0, 0])),
                    "space_name": sp.get('name', '')
                })

        # Extraire les ascenseurs depuis les équipements
        ascenseurs_info = []
        for eq in equipment:
            name = (eq.get('name', '') or '').lower()
            ifc = (eq.get('ifc_type', '') or '').lower()
            if any(kw in name for kw in ASCENSEUR_KEYWORDS) or 'transport' in ifc:
                dims = self._get_dimensions(eq)
                ascenseurs_info.append({
                    "type": "ascenseur",
                    "name": eq.get('name', 'Ascenseur'),
                    "global_id": eq.get('global_id', ''),
                    "width_m": round(dims.get('width_m', 1.1), 2),
                    "location": list(eq.get('centroid', [0, 0, 0])),
                    "space_name": ""
                })

        # Tous les obstacles disponibles
        obstacles = portes_info + escaliers_info + ascenseurs_info
        # Trier par hauteur (z) = ordre naturel du chemin
        obstacles.sort(key=lambda o: o['location'][2] if len(o['location']) >= 3 else 0)

        logger.info(
            f"   {len(equipements_lourds)} équipements lourds — "
            f"{len(portes_info)} portes, {len(escaliers_info)} escaliers, "
            f"{len(ascenseurs_info)} ascenseurs"
        )

        # Violation marker pour le formulaire C#
        self.violations.append({
            "rule_id": self.RULE_ID,
            "severity": "HAUTE",
            "space_name": f"Manutention — {len(equipements_lourds)} équipement(s) lourd(s) à vérifier",
            "space_global_id": "",
            "description": (
                f"Vérification du chemin d'accès requise pour "
                f"{len(equipements_lourds)} équipement(s) lourd(s). "
                f"Cochez les obstacles sur le trajet dans le formulaire."
            ),
            "details": {
                "equipements_lourds": equipements_lourds,
                "obstacles_disponibles": obstacles,
                "largeur_min_porte_m": LARGEUR_MIN_PORTE_M,
                "largeur_min_couloir_m": LARGEUR_MIN_COULOIR_M,
                "needs_form": True
            },
            "location": equipements_lourds[0]['location'] if equipements_lourds else [0, 0, 0],
            "recommendation": (
                "Dans le formulaire CHANT-001, cochez chaque obstacle "
                "(porte, escalier, ascenseur) sur le chemin depuis l'entrée "
                "du bâtiment jusqu'au local technique."
            )
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
