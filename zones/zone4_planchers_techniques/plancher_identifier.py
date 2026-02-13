"""
============================================================================
PLANCHER IDENTIFIER - Identification des Planchers Techniques
============================================================================
Classifie automatiquement les espaces IFC pour identifier les zones
avec planchers techniques :
- Planchers techniques / faux-planchers -> PLAN-001 à PLAN-005
- Locaux techniques (serveurs, TGBT) -> PLAN-001 à PLAN-005
- Gaines techniques avec accès plancher -> PLAN-001, PLAN-004

Utilise le LongName IFC comme source principale de classification.
"""

import json
import re
from typing import List, Dict
from pathlib import Path

from shared.logger import logger


class PlancherIdentifier:
    """Identifie et classifie les espaces avec planchers techniques"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent / "config" / "nomenclature_mapping.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.categories = {}

        self.load_config()
        logger.info(" Plancher Identifier initialisé")

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
        Identifie la catégorie d'un espace pour les planchers techniques.

        Returns:
            Nom de la catégorie ou 'non_concerne'
        """
        long_name = space_data.get('long_name', '').strip()
        name = space_data.get('name', '').strip()
        description = space_data.get('description', '').strip()
        object_type = space_data.get('object_type', '').strip()

        # 1. Chercher par LongName (keywords)
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

        # 3. Regex patterns
        full_text = f"{long_name} {name} {description} {object_type}".lower()
        regex_patterns = self.config.get('regex_patterns', {})

        if regex_patterns.get('plancher_pattern') and re.search(regex_patterns['plancher_pattern'], full_text):
            return 'plancher_technique'

        if regex_patterns.get('local_tech_pattern') and re.search(regex_patterns['local_tech_pattern'], full_text):
            return 'local_technique'

        return 'non_concerne'

    def get_applicable_rules(self, category: str) -> List[str]:
        """Retourne les règles applicables à une catégorie"""
        cat_config = self.categories.get(category, {})
        return cat_config.get('rules', [])

    def classify_all_spaces(self, spaces: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Classifie tous les espaces par catégorie planchers techniques.

        Returns:
            Dictionnaire {catégorie: [spaces]}
        """
        logger.info(f" Classification de {len(spaces)} espaces pour planchers techniques...")

        classified = {}

        for space in spaces:
            category = self.identify_space_category(space)
            space['plancher_category'] = category
            space['plancher_rules'] = self.get_applicable_rules(category)

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
