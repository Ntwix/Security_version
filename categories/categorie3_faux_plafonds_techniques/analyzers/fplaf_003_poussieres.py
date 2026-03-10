"""
============================================================================
FPLAF-003 - Détection de poussières
============================================================================
Règle: Détecter la présence de matériaux générateurs de poussières dans
les faux-plafonds et afficher une alerte automatique.

Fonctionnalités:
- Détection de matériaux à risque (laine minérale, fibre, isolant, flocage...)
- Analyse des propriétés IFC des matériaux
- Alerte automatique "Attention : présence de poussières" à chaque détection

Sévérité: MOYENNE
"""

import json
from typing import List, Dict
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class FPLAF003PoussieresChecker:
    """Analyseur règle FPLAF-003 - Détection poussières"""

    RULE_ID = "FPLAF-003"
    RULE_NAME = "Détection poussières dans faux-plafonds"

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
            self.dust_risk_keywords = params.get('dust_risk_keywords', [
                'laine', 'fibre', 'amiante', 'isolant', 'mineral wool',
                'glass fiber', 'rock wool', 'cellulose', 'vermiculite',
                'perlite', 'polystyrene', 'mousse', 'flocage'
            ])
            self.dust_risk_ifc_materials = params.get('dust_risk_ifc_materials', [
                'mineral', 'fibre', 'insulation', 'isolant', 'wool'
            ])
            self.alert_message = params.get('alert_message',
                                            "Attention : présence de poussières potentielles détectée")

        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.dust_risk_keywords = [
                'laine', 'fibre', 'amiante', 'isolant', 'mineral wool',
                'glass fiber', 'rock wool', 'cellulose', 'vermiculite',
                'perlite', 'polystyrene', 'mousse', 'flocage'
            ]
            self.dust_risk_ifc_materials = ['mineral', 'fibre', 'insulation', 'isolant', 'wool']
            self.alert_message = "Attention : présence de poussières potentielles détectée"

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse FPLAF-003"""
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

        logger.info(f"   Analyse {len(concerned_spaces)} espaces pour détection poussières...")

        for space in concerned_spaces:
            self._analyze_space(space, equipment, slabs)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _analyze_space(self, space: Dict, equipment: List[Dict], slabs: List[Dict]):
        """Analyse un espace pour la présence de matériaux poussiéreux"""
        space_name = space.get('name', 'Inconnu')
        dust_sources = []

        # 1. Vérifier les propriétés de l'espace lui-même
        space_dust = self._check_properties_for_dust(space)
        if space_dust:
            dust_sources.extend(space_dust)

        # 2. Vérifier les équipements dans l'espace
        bbox_min = space.get('bbox_min', (0, 0, 0))
        bbox_max = space.get('bbox_max', (0, 0, 0))

        for eq in equipment:
            eq_centroid = eq.get('centroid', (0, 0, 0))
            if not GeometryUtils.is_point_in_bbox(eq_centroid, bbox_min, bbox_max):
                continue

            eq_dust = self._check_equipment_for_dust(eq)
            if eq_dust:
                dust_sources.extend(eq_dust)

        # 3. Vérifier les dalles/plafonds au-dessus
        space_centroid = space.get('centroid', (0, 0, 0))
        for slab in slabs:
            slab_centroid = slab.get('centroid', (0, 0, 0))
            dx = abs(slab_centroid[0] - space_centroid[0])
            dy = abs(slab_centroid[1] - space_centroid[1])
            dz = slab_centroid[2] - space_centroid[2]

            if dx < 5 and dy < 5 and -1 < dz < 5:
                slab_dust = self._check_properties_for_dust(slab)
                if slab_dust:
                    dust_sources.extend(slab_dust)

        if dust_sources:
            # Dédupliquer
            unique_sources = list(set(dust_sources))

            violation = {
                "rule_id": self.RULE_ID,
                "severity": "MOYENNE",
                "space_name": space_name,
                "space_global_id": space.get('global_id', ''),
                "description": self.alert_message,
                "details": {
                    "dust_sources_count": len(unique_sources),
                    "dust_sources": unique_sources[:10],
                    "alert": self.alert_message,
                    "risk_type": "Poussières / particules en suspension"
                },
                "location": space.get('centroid', (0, 0, 0)),
                "recommendation": f"Port du masque FFP2 obligatoire. "
                                 f"Matériaux à risque détectés: {', '.join(unique_sources[:5])}. "
                                 f"Prévoir aspiration et confinement de la zone."
            }

            self.violations.append(violation)

            # Afficher l'alerte automatique
            logger.warning(f"  ⚠ ALERTE {self.RULE_ID} | {space_name} | {self.alert_message}")
            logger.rule_violation(self.RULE_ID, space_name,
                                f"{len(unique_sources)} source(s) de poussières détectée(s)")
        else:
            logger.rule_passed(self.RULE_ID, space_name)

    def _check_properties_for_dust(self, element: Dict) -> List[str]:
        """Vérifie les propriétés d'un élément pour détecter des matériaux poussiéreux"""
        found = []
        properties = element.get('properties', {})
        name = element.get('name', '').lower()
        materials = element.get('materials', [])

        # Vérifier le nom de l'élément
        for keyword in self.dust_risk_keywords:
            if keyword.lower() in name:
                found.append(f"{keyword} (nom: {element.get('name', '')})")
                break

        # Vérifier les propriétés
        for key, value in properties.items():
            if value is None:
                continue
            value_str = str(value).lower()
            for keyword in self.dust_risk_keywords:
                if keyword.lower() in value_str:
                    found.append(f"{keyword} (propriété {key})")
                    break

        # Vérifier les matériaux IFC
        if isinstance(materials, list):
            for mat in materials:
                mat_name = str(mat).lower() if mat else ''
                for keyword in self.dust_risk_ifc_materials:
                    if keyword.lower() in mat_name:
                        found.append(f"{keyword} (matériau: {mat})")
                        break

        return found

    def _check_equipment_for_dust(self, equipment: Dict) -> List[str]:
        """Vérifie un équipement pour la présence de matériaux poussiéreux"""
        found = []
        eq_name = equipment.get('name', '').lower()
        ifc_type = equipment.get('ifc_type', '').lower()
        properties = equipment.get('properties', {})

        # Vérifier nom de l'équipement
        for keyword in self.dust_risk_keywords:
            if keyword.lower() in eq_name:
                found.append(f"{keyword} (équipement: {equipment.get('name', '')})")
                break

        # Vérifier type IFC (isolation, etc.)
        dust_ifc_types = ['ifccovering', 'ifcbuildingelementproxy']
        if any(t in ifc_type for t in dust_ifc_types):
            # Vérifier si c'est un isolant
            for keyword in self.dust_risk_keywords:
                if keyword.lower() in eq_name:
                    found.append(f"Revêtement/isolant ({equipment.get('name', '')})")
                    break

        # Vérifier propriétés
        for key, value in properties.items():
            if value is None:
                continue
            value_str = str(value).lower()
            for keyword in self.dust_risk_ifc_materials:
                if keyword.lower() in value_str:
                    found.append(f"{keyword} (propriété {key}: {equipment.get('name', '')})")
                    break

        return found
