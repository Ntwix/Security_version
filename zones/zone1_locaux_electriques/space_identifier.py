"""
============================================================================
SPACE IDENTIFIER - Identification et Classification des Espaces
============================================================================
Classifie automatiquement les espaces IFC par catégorie fonctionnelle :
- Locaux techniques électriques -> ELEC-001, ELEC-002, ELEC-003
- Zones humides (salles de bain, toilettes) -> ELEC-004
- Cuisine/Restauration -> ELEC-004
- Laverie/Ménage -> ELEC-004
- Halls, Circulations, Studios, Bureaux, etc.

Utilise le LongName IFC comme source principale de classification.
"""

import json
import re
from typing import List, Dict, Optional
from pathlib import Path

from shared.logger import logger


class SpaceIdentifier:
    """Identifie et classifie les espaces depuis leur nomenclature IFC"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent / "config" / "nomenclature_mapping.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.categories = {}

        self.load_config()

        logger.info(" Space Identifier initialisé (v2 - classification multi-catégories)")

    def load_config(self):
        """Charge la configuration nomenclature"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

            self.categories = self.config.get('space_categories', {})
            # Retirer le champ _comment
            self.categories.pop('_comment', None)

            logger.debug(f"  Configuration chargée: {len(self.categories)} catégories")

        except Exception as e:
            logger.error(f"  Erreur chargement config: {str(e)}")
            self.config = {}
            self.categories = {}

    def identify_space_category(self, space_data: Dict) -> str:
        """
        Identifie la catégorie d'un espace.

        Priorité de recherche :
        1. LongName (source principale dans la maquette CHU Ibn Sina)
        2. Name (code type DOM-INT-xxx, DOM-ITEC-xxx, DOM-CGEN-xxx)
        3. ObjectType / PredefinedType / IFC type

        Args:
            space_data: Dictionnaire de données espace

        Returns:
            Nom de la catégorie (ex: 'local_technique', 'zone_humide', 'hall', ...)
            Retourne 'non_classifie' si aucune correspondance
        """
        long_name = space_data.get('long_name', '').strip()
        name = space_data.get('name', '').strip()
        description = space_data.get('description', '').strip()
        object_type = space_data.get('object_type', '').strip()
        predefined_type = space_data.get('predefined_type', '').strip()
        ifc_type = space_data.get('ifc_type', '').strip()

        # 1. Chercher par LongName (source principale)
        if long_name:
            for cat_key, cat_config in self.categories.items():
                keywords = cat_config.get('keywords', [])
                for keyword in keywords:
                    if keyword.lower() in long_name.lower():
                        return cat_key

        # 2. Chercher par préfixe du Name (DOM-ITEC -> local_technique, DOM-CGEN -> circulation)
        if name:
            for cat_key, cat_config in self.categories.items():
                prefixes = cat_config.get('name_prefixes', [])
                for prefix in prefixes:
                    if name.upper().startswith(prefix.upper()):
                        return cat_key

        # 3. Chercher par keywords anglais
        full_text = f"{long_name} {name} {description} {object_type}".lower()
        for cat_key, cat_config in self.categories.items():
            keywords_en = cat_config.get('keywords_english', [])
            for keyword in keywords_en:
                if keyword.lower() in full_text:
                    return cat_key

        # 4. Chercher par IFC space type
        combined_ifc = f"{object_type} {predefined_type} {ifc_type}".lower()
        for cat_key, cat_config in self.categories.items():
            ifc_types = cat_config.get('ifc_space_types', [])
            for ifc_check in ifc_types:
                token = ifc_check.split('.')[-1].lower()
                if token in combined_ifc or ifc_check.lower() in combined_ifc:
                    return cat_key

        # 5. Regex patterns
        regex_patterns = self.config.get('regex_patterns', {})
        if regex_patterns.get('technical_room_pattern') and re.search(regex_patterns['technical_room_pattern'], full_text):
            return 'local_technique'
        if regex_patterns.get('wet_room_pattern') and re.search(regex_patterns['wet_room_pattern'], full_text):
            return 'zone_humide'
        if regex_patterns.get('cuisine_pattern') and re.search(regex_patterns['cuisine_pattern'], full_text):
            return 'cuisine_restauration'

        return 'non_classifie'

    def get_applicable_rules(self, category: str) -> List[str]:
        """
        Retourne les règles de conformité applicables à une catégorie.

        Args:
            category: Nom de la catégorie

        Returns:
            Liste de règles (ex: ['ELEC-001', 'ELEC-002', 'ELEC-003'])
        """
        cat_config = self.categories.get(category, {})
        return cat_config.get('rules', [])

    def is_wet_zone(self, category: str) -> bool:
        """Vérifie si la catégorie est une zone humide (nécessite ELEC-004)"""
        return 'ELEC-004' in self.get_applicable_rules(category)

    def is_technical_room(self, category: str) -> bool:
        """Vérifie si la catégorie est un local technique"""
        rules = self.get_applicable_rules(category)
        return 'ELEC-001' in rules or 'ELEC-002' in rules or 'ELEC-003' in rules

    def classify_all_spaces(self, spaces: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Classifie tous les espaces par catégorie.

        Args:
            spaces: Liste espaces depuis IFCExtractor

        Returns:
            Dictionnaire {catégorie: [spaces]}
        """
        logger.info(f" Classification de {len(spaces)} espaces...")

        classified = {}

        for space in spaces:
            category = self.identify_space_category(space)
            space['category'] = category
            space['applicable_rules'] = self.get_applicable_rules(category)

            if category not in classified:
                classified[category] = []
            classified[category].append(space)

        # Log statistiques
        logger.info(f"   Classification terminée:")
        for cat_key in sorted(classified.keys()):
            cat_list = classified[cat_key]
            rules = self.get_applicable_rules(cat_key)
            rules_str = f" -> {', '.join(rules)}" if rules else ""
            logger.info(f"   - {cat_key}: {len(cat_list)} espaces{rules_str}")

        return classified

    def get_spaces_for_rule(self, classified: Dict[str, List[Dict]], rule: str) -> List[Dict]:
        """
        Retourne tous les espaces concernés par une règle donnée.

        Args:
            classified: Résultat de classify_all_spaces()
            rule: Code règle (ex: 'ELEC-004')

        Returns:
            Liste des espaces concernés
        """
        result = []
        for cat_key, spaces in classified.items():
            if rule in self.get_applicable_rules(cat_key):
                result.extend(spaces)
        return result

    def identify_space_type(self, space_data: Dict) -> List[str]:
        """
        Compatibilité avec l'ancienne API.
        Retourne les types identifiés sous forme de liste.
        """
        category = self.identify_space_category(space_data)
        types = []

        if self.is_technical_room(category):
            types.append('technical_room')
        if self.is_wet_zone(category):
            types.append('wet_room')

        return types

    def get_equipment_type(self, equipment_data: Dict) -> Optional[str]:
        """Identifie le type d'équipement"""
        ifc_type = equipment_data.get('ifc_type', '')
        name = equipment_data.get('name', '').lower()

        heavy_types = self.config.get('electrical_equipment', {}).get('heavy_equipment', {}).get('ifc_types', [])
        for heavy_type in heavy_types:
            if heavy_type in ifc_type:
                return 'heavy'

        wet_types = self.config.get('electrical_equipment', {}).get('wet_zone_equipment', {}).get('ifc_types', [])
        for wet_type in wet_types:
            if wet_type in ifc_type:
                return 'wet_zone'

        return 'standard'

    def estimate_equipment_weight(self, equipment_data: Dict) -> Optional[float]:
        """Estime le poids d'un équipement si non spécifié"""
        if equipment_data.get('weight_kg'):
            return equipment_data['weight_kg']

        ifc_type = equipment_data.get('ifc_type', '')
        typical_weights = self.config.get('electrical_equipment', {}).get('heavy_equipment', {}).get('typical_weights_kg', {})

        for type_key, weight in typical_weights.items():
            if type_key in ifc_type:
                return weight

        return None
