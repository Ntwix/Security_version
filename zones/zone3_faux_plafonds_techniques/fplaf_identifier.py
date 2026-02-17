"""
============================================================================
FPLAF IDENTIFIER - Identification et Classification des Faux-Plafonds
============================================================================
Classifie automatiquement les espaces IFC pour identifier les faux-plafonds :
- Faux-plafonds / plénums -> FPLAF-001 à FPLAF-003
- Locaux techniques avec faux-plafond -> FPLAF-001 à FPLAF-003
- Circulations avec faux-plafond -> FPLAF-001, FPLAF-003

Utilise le LongName IFC comme source principale de classification.
"""

import json
import re
from typing import List, Dict
from pathlib import Path
from shared.logger import logger



class FPlafIdentifier:
    """Identifie et classifie les espaces faux-plafonds depuis leur nomenclature IFC"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent / "config" / "nomenclature_mapping.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.categories = {}

        self.load_config()

        logger.info(" FPlaf Identifier initialisé")

    def load_config(self):
        """Charge la configuration nomenclature"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

            self.categories = self.config.get('space_categories', {})
            self.categories.pop('_comment', None)

            logger.debug(f"  Configuration chargée: {len(self.categories)} catégories")

        except Exception as e:
            logger.error(f"  Erreur chargement config: {str(e)}")
            self.config = {}
            self.categories = {}

    def identify_space_category(self, space_data: Dict) -> str:
        """
        Identifie la catégorie d'un espace pour les faux-plafonds.

        Priorité de recherche :
        1. LongName (source principale)
        2. Name (préfixe DOM-FP, etc.)
        3. Keywords anglais
        4. IFC space type
        5. Regex patterns

        Returns:
            Nom de la catégorie ou 'non_concerne'
        """
        long_name = space_data.get('long_name', '').strip()
        name = space_data.get('name', '').strip()
        description = space_data.get('description', '').strip()
        object_type = space_data.get('object_type', '').strip()

        # 1. Chercher par LongName
        if long_name:
            for cat_key, cat_config in self.categories.items():
                keywords = cat_config.get('keywords', [])
                for keyword in keywords:
                    if keyword.lower() in long_name.lower():
                        return cat_key

        # 2. Chercher par préfixe du Name
        if name:
            for cat_key, cat_config in self.categories.items():
                prefixes = cat_config.get('name_prefixes', [])
                for prefix in prefixes:
                    if name.upper().startswith(prefix.upper()):
                        return cat_key

        # 3. Keywords anglais
        full_text = f"{long_name} {name} {description} {object_type}".lower()
        for cat_key, cat_config in self.categories.items():
            keywords_en = cat_config.get('keywords_english', [])
            for keyword in keywords_en:
                if keyword.lower() in full_text:
                    return cat_key

        # 4. IFC space type
        
        combined_ifc = f"{object_type} {space_data.get('predefined_type', '')} {space_data.get('ifc_type', '')}".lower()
        for cat_key, cat_config in self.categories.items():
            ifc_types = cat_config.get('ifc_space_types', [])
            for ifc_check in ifc_types:
                token = ifc_check.split('.')[-1].lower()
                if token in combined_ifc or ifc_check.lower() in combined_ifc:
                    return cat_key

        # 5. Regex patterns
        
        regex_patterns = self.config.get('regex_patterns', {})
        if regex_patterns.get('faux_plafond_pattern') and re.search(regex_patterns['faux_plafond_pattern'], full_text):
            return 'faux_plafond'

        return 'non_concerne'

    def get_applicable_rules(self, category: str) -> List[str]:
        """Retourne les règles applicables à une catégorie"""
        cat_config = self.categories.get(category, {})
        return cat_config.get('rules', [])



    def classify_all_spaces(self, spaces: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Classifie tous les espaces par catégorie faux-plafonds.

        Args:
            spaces: Liste espaces depuis IFCExtractor
            
        Returns:
            Dictionnaire {catégorie: [spaces]}
        """
        logger.info(f" Classification de {len(spaces)} espaces pour faux-plafonds techniques...")

        classified = {}

        for space in spaces:
            category = self.identify_space_category(space)
            space['fplaf_category'] = category
            space['fplaf_rules'] = self.get_applicable_rules(category)

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
        """Retourne tous les espaces concernés par une règle donnée"""
        result = []
        for cat_key, spaces in classified.items():
            if rule in self.get_applicable_rules(cat_key):
                result.extend(spaces)
        return result

    def classify_equipment_type(self, equipment_data: Dict) -> str:
        """Classifie un équipement dans le contexte des faux-plafonds.
        Returns:
            'cable', 'support_cables', 'luminaire', 'cvc' ou 'autre'"""
        name = equipment_data.get('name', '').lower()
        ifc_type = equipment_data.get('ifc_type', '')

        eq_categories = self.config.get('equipment_categories', {})

        for cat_key, cat_config in eq_categories.items():
            keywords = cat_config.get('keywords', [])
            for kw in keywords:
                if kw.lower() in name:
                    return cat_key

            ifc_types = cat_config.get('ifc_types', [])
            for ifc_t in ifc_types:
                if ifc_t in ifc_type:
                    return cat_key

        # Regex fallback
        regex_patterns = self.config.get('regex_patterns', {})
        if regex_patterns.get('cable_pattern') and re.search(regex_patterns['cable_pattern'], name):
            return 'cable'

        return 'autre'
