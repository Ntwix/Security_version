"""
============================================================================
CHANT-002 - Accessibilité des locaux techniques électriques
============================================================================
Règle: Les locaux techniques électriques (Poste Transfo, Groupe Électrogène,
TGBT, TGS, Onduleur) contiennent des équipements sous tension ou dangereux.
L'accès est INTERDIT sauf au personnel habilité, avec mode opératoire,
EPI obligatoires et respect des procédures de consignation.

Instructions obligatoires :
  1. Interdiction d'accès aux locaux techniques
  2. Interdiction de travailler sans mode opératoire
  3. Accès réservé uniquement au personnel habilité
  4. Port obligatoire des EPI
  5. Respect des procédures de consignation

Logique: Violation SYSTÉMATIQUE — chaque local technique = 1 violation,
avec description et recommandations adaptées au type de local.

Sévérité: CRITIQUE
"""

from typing import List, Dict
from shared.logger import logger


# ── Catalogue des types de locaux techniques ─────────────────────────────────
# Chaque entrée : (mots-clés à chercher dans le nom, label affiché, risques spécifiques)
LOCAL_TYPES = [
    {
        "keywords": ["transfo", "transformateur", "poste ht", "poste hta", "poste htb",
                     "poste haute tension", "hta", "htb"],
        "label": "Poste Transformateur",
        "risques": "Haute tension (HTA/HTB), arc électrique, champs électromagnétiques intenses",
        "epi": "casque isolant HT, gants isolants cl.4, écran facial anti-arc, combinaison ignifugée",
        "consigne_extra": "Vérifier la mise hors tension et la mise à la terre avant toute intervention. "
                          "Respecter les distances de sécurité HTA/HTB réglementaires."
    },
    {
        "keywords": ["ge ", "g.e", "groupe electro", "groupe électro", "generatrice",
                     "génératrice", "groupe electrogene", "groupe électrogène", "GE"],
        "label": "Local Groupe Électrogène",
        "risques": "Gaz d'échappement (CO), risque d'incendie (carburant), vibrations, niveau sonore élevé",
        "epi": "masque anti-gaz CO, bouchons d'oreilles, gants résistants aux hydrocarbures",
        "consigne_extra": "Arrêter et consigner le groupe avant intervention. "
                          "Assurer une ventilation forcée. Vérifier l'absence de fuite de carburant."
    },
    {
        "keywords": ["tgbt", "tableau général basse tension", "tableau general basse tension",
                     "t.g.b.t", "general bt"],
        "label": "LT TGBT (Tableau Général Basse Tension)",
        "risques": "Risque d'arc électrique BT, coupure alimentation générale, brûlures",
        "epi": "gants isolants BT, écran facial anti-arc, vêtement anti-arc cat.2",
        "consigne_extra": "Appliquer la procédure de consignation complète (5 étapes NF C 18-510). "
                          "Ne jamais intervenir seul sur un TGBT sous tension."
    },
    {
        "keywords": ["tgs", "tableau général de sécurité", "tableau general de securite",
                     "t.g.s", "general securite", "sécurité incendie"],
        "label": "LT TGS (Tableau Général de Sécurité)",
        "risques": "Alimentation sécurité incendie/désenfumage — toute erreur entraîne une coupure critique",
        "epi": "gants isolants BT, écran facial anti-arc, vêtement anti-arc cat.2",
        "consigne_extra": "Intervention soumise à autorisation du responsable sécurité incendie. "
                          "Coordonner obligatoirement avec le SSI avant toute consignation."
    },
    {
        "keywords": ["onduleur", "ups", "alimentation sans coupure", "asc ",
                     "batterie onduleur", "salle onduleur"],
        "label": "Local Onduleur / ASC",
        "risques": "Batteries acide (H2SO4), dégagement d'hydrogène (explosif), risque chimique et électrique",
        "epi": "gants résistants aux acides, lunettes de protection, tablier anti-acide, détecteur H2",
        "consigne_extra": "Ventiler le local avant intervention. Interdire toute flamme ou étincelle. "
                          "Avoir un kit de neutralisation acide à portée."
    },
]

# Type générique si aucun mot-clé ne correspond
LOCAL_TYPE_GENERIQUE = {
    "label": "Local Technique Électrique",
    "risques": "Équipements sous tension, risque électrique",
    "epi": "gants isolants, casque de protection, chaussures de sécurité isolantes",
    "consigne_extra": "Identifier précisément le type d'équipement avant toute intervention."
}

# Instructions communes à tous les locaux techniques (5 points obligatoires)
INSTRUCTIONS_COMMUNES = (
    "1. INTERDICTION D'ACCÈS sans autorisation écrite du responsable électrique\n"
    "2. INTERDICTION de travailler sans mode opératoire validé\n"
    "3. ACCÈS RÉSERVÉ au personnel habilité (habilitation électrique en cours de validité)\n"
    "4. PORT OBLIGATOIRE des EPI adaptés au type de local\n"
    "5. RESPECT des procédures de consignation (NF C 18-510)"
)


def _detect_local_type(local_name: str, equipment_in_space: list = None) -> dict:
    """
    Détecte le type de local technique.
    1. Par mots-clés dans le nom (ex: "Salle TGBT", "Local Transfo")
    2. Sinon par types d'équipements IFC présents dans le local (fallback pour
       maquettes avec noms génériques comme "Local Technique" / "DOM-ITEC-xxx")
    """
    # 1) Détection par nom
    name_lower = local_name.lower()
    for lt in LOCAL_TYPES:
        for kw in lt["keywords"]:
            if kw.lower() in name_lower:
                return lt

    # 2) Fallback : détection par équipements IFC contenus dans le local
    if equipment_in_space:
        ifc_types = [eq.get('ifc_type', '').lower() for eq in equipment_in_space]
        names_eq  = [eq.get('name', '').lower() for eq in equipment_in_space]
        all_text  = ' '.join(ifc_types + names_eq)

        if any(t in all_text for t in ['transformer', 'ifctransformer', 'transfo', 'hta', 'htb']):
            return LOCAL_TYPES[0]  # Poste Transformateur
        if any(t in all_text for t in ['generator', 'ifcelectricgenerator', 'groupe electro',
                                        'groupe électro', 'generatrice', 'génératrice']):
            return LOCAL_TYPES[1]  # Groupe Électrogène
        if any(t in all_text for t in ['tgbt', 'tableau général bt', 'tableau general bt',
                                        'basse tension', 'switchgear']):
            return LOCAL_TYPES[2]  # TGBT
        if any(t in all_text for t in ['tgs', 'securite incendie', 'sécurité incendie',
                                        'tableau securite', 'tableau sécurité']):
            return LOCAL_TYPES[3]  # TGS
        if any(t in all_text for t in ['ups', 'onduleur', 'batterie', 'uninterruptible']):
            return LOCAL_TYPES[4]  # Onduleur

    return LOCAL_TYPE_GENERIQUE


class CHANT002AccessibiliteChecker:
    """Analyseur CHANT-002 - Accessibilité locaux techniques électriques"""

    RULE_ID = "CHANT-002"
    RULE_NAME = "Accessibilité des locaux techniques électriques"

    def __init__(self):
        self.violations = []
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict,
                doors: List[Dict] = None) -> List[Dict]:
        """Violation systématique pour chaque local technique détecté."""
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        locaux_techniques = space_types.get('local_technique', [])

        if not locaux_techniques:
            logger.info(f"    Aucun local technique trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(locaux_techniques)} locaux techniques — signalement accès restreint...")

        # Index des équipements par espace (global_id) pour la détection par équipements
        equip_by_space = {}
        for eq in (equipment or []):
            sid = eq.get('space_id') or eq.get('space_global_id', '')
            if sid:
                equip_by_space.setdefault(sid, []).append(eq)

        for local in locaux_techniques:
            local_name = local.get('name', 'Inconnu')
            local_gid  = local.get('global_id', '')
            equip_in   = equip_by_space.get(local_gid, [])
            local_type = _detect_local_type(local_name, equip_in)
            label      = local_type["label"]
            risques    = local_type["risques"]
            epi        = local_type["epi"]
            consigne   = local_type["consigne_extra"]

            description = (
                f"{label} — Accès interdit sans habilitation. "
                f"Risques : {risques}."
            )

            recommendation = (
                f"[{label}] — Consignes obligatoires :\n"
                f"{INSTRUCTIONS_COMMUNES}\n\n"
                f"EPI requis : {epi}\n\n"
                f"Consigne spécifique : {consigne}"
            )

            self.violations.append({
                "rule_id":          self.RULE_ID,
                "severity":         "CRITIQUE",
                "space_name":       local_name,
                "space_global_id":  local.get('global_id', ''),
                "description":      description,
                "details": {
                    "local_type":   label,
                    "risques":      risques,
                    "epi_requis":   epi,
                    "height_m":     round(local.get('height_m') or 0, 2),
                    "area_m2":      round(local.get('floor_area_m2') or 0, 2),
                },
                "location":         list(local.get('centroid', [0, 0, 0])),
                "recommendation":   recommendation
            })
            logger.rule_violation(self.RULE_ID, local_name,
                                  f"{label} — accès restreint requis")

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations
