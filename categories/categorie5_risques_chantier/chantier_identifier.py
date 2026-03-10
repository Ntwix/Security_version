"""
============================================================================
CHANTIER IDENTIFIER - Classification des espaces Zone 5 Risques Chantier
============================================================================
Classifie les espaces de la maquette pour les risques chantier :
- local_technique   : locaux techniques (DOM-ITEC, DOM-GTEC, DOM-TGBT...)
- gaine_ascenseur   : gaines d'ascenseur
- circulation       : couloirs, halls, dégagements
- tous              : tous les espaces (pour CHANT-003 hauteur)
"""

from typing import List, Dict
from shared.logger import logger


# Mots-clés pour identifier les locaux techniques
LOCAL_TECHNIQUE_KEYWORDS = [
    "local technique", "local.technique", "lt vdi", "local vdi",
    "local électrique", "salle électrique", "tgbt", "tableau général",
    "gaine technique", "g.t", "local elec", "chaufferie", "local cvc"
]
LOCAL_TECHNIQUE_PREFIXES = ["DOM-ITEC", "DOM-GTEC", "DOM-TGBT", "DOM-LT"]

# Mots-clés pour identifier les gaines ascenseur
ASCENSEUR_KEYWORDS = [
    "ascenseur", "elevator", "lift", "gaine ascenseur",
    "cage ascenseur", "monte-charge", "monte charge"
]
ASCENSEUR_PREFIXES = ["DOM-ASC", "DOM-ELEV"]

# Mots-clés pour identifier les circulations
CIRCULATION_KEYWORDS = [
    "circulation", "couloir", "dégagement", "hall", "sas",
    "corridor", "passage", "palier"
]
CIRCULATION_PREFIXES = ["DOM-CIRC", "DOM-HALL", "DOM-CGEN"]


class ChantierIdentifier:
    """Classifie les espaces pour l'analyse des risques chantier Zone 5."""

    def classify_all_spaces(self, spaces: List[Dict]) -> Dict:
        """
        Classe tous les espaces en catégories chantier.
        Retourne un dict : { 'local_technique': [...], 'gaine_ascenseur': [...],
                              'circulation': [...], 'tous': [...] }
        """
        result = {
            'local_technique': [],
            'gaine_ascenseur': [],
            'circulation': [],
            'tous': list(spaces)
        }

        for space in spaces:
            cat = self._classify_space(space)
            if cat in result:
                result[cat].append(space)

        logger.info(f"   Chantier — Locaux techniques : {len(result['local_technique'])}")
        logger.info(f"   Chantier — Gaines ascenseur  : {len(result['gaine_ascenseur'])}")
        logger.info(f"   Chantier — Circulations      : {len(result['circulation'])}")
        logger.info(f"   Chantier — Total espaces      : {len(result['tous'])}")

        return result

    def _classify_space(self, space: Dict) -> str:
        name      = (space.get('name', '') or '').upper()
        longname  = (space.get('long_name', '') or space.get('longname', '') or '').lower()
        combined  = f"{name.lower()} {longname}"

        # Gaine ascenseur en priorité
        for kw in ASCENSEUR_KEYWORDS:
            if kw in combined:
                return 'gaine_ascenseur'
        for pfx in ASCENSEUR_PREFIXES:
            if name.startswith(pfx):
                return 'gaine_ascenseur'

        # Local technique
        for kw in LOCAL_TECHNIQUE_KEYWORDS:
            if kw in combined:
                return 'local_technique'
        for pfx in LOCAL_TECHNIQUE_PREFIXES:
            if name.startswith(pfx):
                return 'local_technique'

        # Circulation
        for kw in CIRCULATION_KEYWORDS:
            if kw in combined:
                return 'circulation'
        for pfx in CIRCULATION_PREFIXES:
            if name.startswith(pfx):
                return 'circulation'

        return 'autre'

    def get_spaces_for_rule(self, space_types: Dict, rule: str) -> List[Dict]:
        """Retourne les espaces concernés par une règle donnée."""
        mapping = {
            'CHANT-001': space_types.get('local_technique', []),
            'CHANT-002': space_types.get('local_technique', []),
            'CHANT-003': space_types.get('tous', []),
            'CHANT-004': space_types.get('gaine_ascenseur', []),
            'CHANT-005': space_types.get('local_technique', []),
        }
        return mapping.get(rule, [])
