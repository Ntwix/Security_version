"""
============================================================================
CHANT-004 - Risque de chute en gaine ascenseur
============================================================================
Règle: Avant l'installation de l'ascenseur, la gaine est un espace vide
vertical présentant un risque de chute mortelle.
Toute gaine d'ascenseur identifiée dans la maquette doit être signalée
comme zone dangereuse nécessitant des protections collectives
(garde-corps, filet, balisage).

Logique: Violation SYSTÉMATIQUE — chaque gaine ascenseur = 1 violation.

Sévérité: CRITIQUE
"""

from typing import List, Dict
from shared.logger import logger

# Mots-clés pour détecter les ascenseurs dans les équipements
ASCENSEUR_KEYWORDS = [
    "asc", "ascenseur", "elevator", "lift", "monte-charge", "monte charge",
    "eqs_ape", "eqs_asc"
]


def _is_ascenseur(eq: Dict) -> bool:
    name = (eq.get('name', '') or '').lower()
    ifc  = (eq.get('ifc_type', '') or '').lower()
    for kw in ASCENSEUR_KEYWORDS:
        if kw in name:
            return True
    if 'transport' in ifc:
        return True
    return False


class CHANT004GaineAscenseurChecker:
    """Analyseur CHANT-004 - Gaine ascenseur (systématique)"""

    RULE_ID = "CHANT-004"
    RULE_NAME = "Risque de chute en gaine ascenseur"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """
        Violation systématique pour chaque ascenseur détecté.
        Détection : espaces nommés 'ascenseur' OU équipements spécialisés (EQS_APE).
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        # 1) Depuis les espaces (autres maquettes avec rooms nommés)
        gaines_espaces = space_types.get('gaine_ascenseur', [])

        # 2) Depuis les équipements spécialisés (maquette ARCHI CHU : EQS_APE ASC 1...)
        ascenseurs_eq = [eq for eq in (equipment or []) if _is_ascenseur(eq)]

        # Dédoublonner par global_id
        seen = set()
        tous = []
        for item in gaines_espaces:
            gid = item.get('global_id', '')
            if gid not in seen:
                seen.add(gid)
                tous.append(('espace', item))
        for item in ascenseurs_eq:
            gid = item.get('global_id', '')
            if gid not in seen:
                seen.add(gid)
                tous.append(('equipment', item))

        if not tous:
            logger.info(f"    Aucun ascenseur trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(tous)} ascenseurs — signalement risque chute ({len(gaines_espaces)} espaces, {len(ascenseurs_eq)} équipements)...")

        for source, item in tous:
            name   = item.get('name', 'Inconnu')
            height = item.get('height_m') or 0

            self.violations.append({
                "rule_id":         self.RULE_ID,
                "severity":        "CRITIQUE",
                "space_name":      name,
                "space_global_id": item.get('global_id', ''),
                "description":     "Ascenseur — gaine vide avant installation, risque de chute mortelle",
                "details": {
                    "hauteur_m": round(height, 2),
                    "source":    source,
                },
                "location": list(item.get('centroid', [0, 0, 0])),
                "recommendation": (
                    f"Ascenseur '{name}' : gaine vide pendant la phase chantier. "
                    f"Mettre en place impérativement des protections collectives "
                    f"(garde-corps, filet de sécurité, balisage) avant tout accès. "
                    f"Interdire l'accès sans EPI. Poser des panneaux d'interdiction d'accès."
                )
            })
            logger.rule_violation(self.RULE_ID, name, "Ascenseur — gaine vide risque chute")

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations
