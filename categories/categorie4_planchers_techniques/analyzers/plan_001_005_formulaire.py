"""
============================================================================
PLAN-001 à PLAN-005 - Formulaire de vérification des risques
============================================================================
Formulaire interactif CLI pour l'évaluation des risques sur les
planchers techniques.

Questions:
  PLAN-001: Y a-t-il des planchers techniques ? (+ liste déroulante types)
  PLAN-002: Les câbles sont-ils protégés ? (Oui/Non)
  PLAN-003: Y a-t-il des risques d'humidité ? (Oui/Non)
  PLAN-004: Y a-t-il des risques d'écrasement des doigts ? (Oui/Non)
  PLAN-005: Synthèse automatique des risques

Interface: Formulaire avec champs conditionnels
Priorité: HAUTE
"""

import json
from typing import List, Dict
from pathlib import Path
from datetime import datetime

import click

from shared.logger import logger


class PLAN001005FormulaireChecker:
    """Analyseur PLAN-001 à PLAN-005 - Formulaire interactif de vérification des risques"""

    RULE_ID = "PLAN-001-005"
    RULE_NAME = "Formulaire de vérification des risques planchers techniques"

    PLANCHER_TYPES = [
        "Plancher surélevé (faux-plancher)",
        "Plancher technique accessible",
        "Caillebotis métallique",
        "Dalle amovible",
        "Plancher collaborant",
        "Autre"
    ]

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []
        self.responses = {}

        self.load_config()
        logger.info(f" {self.RULE_ID} Formulaire Checker initialisé")

    def load_config(self):
        """Charge configuration règles"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")
            self.config = {}

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """
        Lance le formulaire interactif et génère les violations.

        Le formulaire pose les questions PLAN-001 à PLAN-004 pour chaque
        espace concerné, puis génère la synthèse PLAN-005.
        """
        logger.analysis_start(self.RULE_ID)

        self.violations = []

        # Espaces concernés
        concerned_spaces = []
        concerned_spaces.extend(space_types.get('plancher_technique', []))
        concerned_spaces.extend(space_types.get('local_technique', []))
        concerned_spaces.extend(space_types.get('gaine_technique', []))

        if not concerned_spaces:
            logger.info(f"    Aucun espace concerné pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(concerned_spaces)} espaces avec planchers techniques détectés")

        # Lancer le formulaire interactif
        self._run_interactive_form(concerned_spaces)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _run_interactive_form(self, spaces: List[Dict]):
        """Exécute le formulaire interactif CLI"""

        print("\n" + "=" * 70)
        print("  ZONE 4 - FORMULAIRE DE VÉRIFICATION DES RISQUES")
        print("  PLANCHERS TECHNIQUES")
        print("=" * 70)
        print(f"\n  {len(spaces)} espaces concernés détectés dans la maquette.")
        print("  Répondez aux questions suivantes pour chaque vérification.\n")

        # ===== PLAN-001: Présence de planchers techniques =====
        self._ask_plan_001(spaces)

        # Si pas de planchers techniques, on s'arrête
        if not self.responses.get('plan_001_has_plancher', False):
            logger.info("   Pas de plancher technique déclaré - fin du formulaire")
            return

        # ===== PLAN-002: Protection des câbles =====
        self._ask_plan_002(spaces)

        # ===== PLAN-003: Risques d'humidité =====
        self._ask_plan_003(spaces)

        # ===== PLAN-004: Risques d'écrasement =====
        self._ask_plan_004(spaces)

        # ===== PLAN-005: Synthèse =====
        self._generate_plan_005_synthese(spaces)

    def _ask_plan_001(self, spaces: List[Dict]):
        """PLAN-001: Y a-t-il des planchers techniques ?"""
        print("-" * 70)
        print("  PLAN-001 : Présence de planchers techniques")
        print("-" * 70)

        has_plancher = click.confirm(
            "\n  Y a-t-il des planchers techniques ?",
            default=True
        )

        self.responses['plan_001_has_plancher'] = has_plancher

        if has_plancher:
            # Liste déroulante conditionnelle
            print("\n  Types de planchers disponibles:")
            for i, ptype in enumerate(self.PLANCHER_TYPES, 1):
                print(f"    {i}. {ptype}")

            type_index = click.prompt(
                "\n  Sélectionnez le type de plancher",
                type=click.IntRange(1, len(self.PLANCHER_TYPES)),
                default=1
            )

            selected_type = self.PLANCHER_TYPES[type_index - 1]
            self.responses['plan_001_type'] = selected_type

            print(f"\n  -> Plancher technique: OUI")
            print(f"  -> Type: {selected_type}")
            logger.info(f"   PLAN-001: Plancher technique détecté - Type: {selected_type}")

            # Pas une violation, c'est informatif
        else:
            print(f"\n  -> Plancher technique: NON")
            logger.info("   PLAN-001: Pas de plancher technique")

    def _ask_plan_002(self, spaces: List[Dict]):
        """PLAN-002: Les câbles sont-ils protégés ?"""
        print("\n" + "-" * 70)
        print("  PLAN-002 : Protection des câbles")
        print("-" * 70)

        cables_protected = click.confirm(
            "\n  Les câbles sont-ils protégés ?",
            default=None
        )

        self.responses['plan_002_cables_protected'] = cables_protected

        if not cables_protected:
            plan_002_config = self.config.get('PLAN-002', {}).get('parameters', {})
            alert = plan_002_config.get('conditional', {}).get('if_no', {}).get(
                'alert', "ATTENTION : Câbles non protégés")
            recommendation = plan_002_config.get('conditional', {}).get('if_no', {}).get(
                'recommendation', "Installer des protections mécaniques")

            print(f"\n  ⚠  {alert}")
            print(f"  → Recommandation: {recommendation}")

            # Créer violation pour chaque espace concerné
            for space in spaces:
                violation = {
                    "rule_id": "PLAN-002",
                    "severity": "HAUTE",
                    "space_name": space.get('name', 'Inconnu'),
                    "space_global_id": space.get('global_id', ''),
                    "description": alert,
                    "details": {
                        "question": "Les câbles sont-ils protégés ?",
                        "response": "Non",
                        "mode": "formulaire_interactif"
                    },
                    "location": space.get('centroid', (0, 0, 0)),
                    "recommendation": recommendation
                }
                self.violations.append(violation)

            logger.warning(f"  PLAN-002: Câbles NON protégés - {len(spaces)} violations")
        else:
            print(f"\n  ✓ Câbles protégés - Conforme")
            logger.info("   PLAN-002: Câbles protégés - OK")

    def _ask_plan_003(self, spaces: List[Dict]):
        """PLAN-003: Y a-t-il des risques d'humidité ?"""
        print("\n" + "-" * 70)
        print("  PLAN-003 : Risques d'humidité")
        print("-" * 70)

        has_humidity = click.confirm(
            "\n  Y a-t-il des risques d'humidité ?",
            default=None
        )

        self.responses['plan_003_humidity'] = has_humidity

        if has_humidity:
            plan_003_config = self.config.get('PLAN-003', {}).get('parameters', {})
            alert = plan_003_config.get('conditional', {}).get('if_yes', {}).get(
                'alert', "ATTENTION : Risque d'humidité détecté")
            recommendation = plan_003_config.get('conditional', {}).get('if_yes', {}).get(
                'recommendation', "Prévoir étanchéité et protection IP adaptée")

            print(f"\n  ⚠  {alert}")
            print(f"  → Recommandation: {recommendation}")

            for space in spaces:
                violation = {
                    "rule_id": "PLAN-003",
                    "severity": "HAUTE",
                    "space_name": space.get('name', 'Inconnu'),
                    "space_global_id": space.get('global_id', ''),
                    "description": alert,
                    "details": {
                        "question": "Y a-t-il des risques d'humidité ?",
                        "response": "Oui",
                        "mode": "formulaire_interactif"
                    },
                    "location": space.get('centroid', (0, 0, 0)),
                    "recommendation": recommendation
                }
                self.violations.append(violation)

            logger.warning(f"  PLAN-003: Risques d'humidité - {len(spaces)} violations")
        else:
            print(f"\n  ✓ Pas de risque d'humidité - Conforme")
            logger.info("   PLAN-003: Pas de risque d'humidité - OK")

    def _ask_plan_004(self, spaces: List[Dict]):
        """PLAN-004: Y a-t-il des risques d'écrasement des doigts ?"""
        print("\n" + "-" * 70)
        print("  PLAN-004 : Risques d'écrasement des doigts")
        print("-" * 70)

        has_crush_risk = click.confirm(
            "\n  Y a-t-il des risques d'écrasement des doigts ?",
            default=None
        )

        self.responses['plan_004_crush_risk'] = has_crush_risk

        if has_crush_risk:
            plan_004_config = self.config.get('PLAN-004', {}).get('parameters', {})
            alert = plan_004_config.get('conditional', {}).get('if_yes', {}).get(
                'alert', "ATTENTION : Risque d'écrasement des doigts")
            recommendation = plan_004_config.get('conditional', {}).get('if_yes', {}).get(
                'recommendation', "Installer des systèmes de levage assisté")

            print(f"\n  ⚠  {alert}")
            print(f"  → Recommandation: {recommendation}")

            for space in spaces:
                violation = {
                    "rule_id": "PLAN-004",
                    "severity": "HAUTE",
                    "space_name": space.get('name', 'Inconnu'),
                    "space_global_id": space.get('global_id', ''),
                    "description": alert,
                    "details": {
                        "question": "Y a-t-il des risques d'écrasement des doigts ?",
                        "response": "Oui",
                        "mode": "formulaire_interactif"
                    },
                    "location": space.get('centroid', (0, 0, 0)),
                    "recommendation": recommendation
                }
                self.violations.append(violation)

            logger.warning(f"  PLAN-004: Risques d'écrasement - {len(spaces)} violations")
        else:
            print(f"\n  ✓ Pas de risque d'écrasement - Conforme")
            logger.info("   PLAN-004: Pas de risque d'écrasement - OK")

    def _generate_plan_005_synthese(self, spaces: List[Dict]):
        """PLAN-005: Synthèse automatique des résultats"""
        print("\n" + "=" * 70)
        print("  PLAN-005 : SYNTHÈSE DES RISQUES")
        print("=" * 70)

        risks_found = []
        risks_ok = []

        # Résumé PLAN-001
        if self.responses.get('plan_001_has_plancher'):
            ptype = self.responses.get('plan_001_type', 'Non spécifié')
            print(f"\n  PLAN-001 | Plancher technique  : OUI ({ptype})")
        else:
            print(f"\n  PLAN-001 | Plancher technique  : NON")

        # Résumé PLAN-002
        if not self.responses.get('plan_002_cables_protected', True):
            print(f"  PLAN-002 | Protection câbles   : ⚠ NON CONFORME")
            risks_found.append("Câbles non protégés")
        else:
            print(f"  PLAN-002 | Protection câbles   : ✓ CONFORME")
            risks_ok.append("Protection câbles")

        # Résumé PLAN-003
        if self.responses.get('plan_003_humidity', False):
            print(f"  PLAN-003 | Risques humidité    : ⚠ RISQUE DÉTECTÉ")
            risks_found.append("Risques d'humidité")
        else:
            print(f"  PLAN-003 | Risques humidité    : ✓ CONFORME")
            risks_ok.append("Humidité")

        # Résumé PLAN-004
        if self.responses.get('plan_004_crush_risk', False):
            print(f"  PLAN-004 | Risques écrasement  : ⚠ RISQUE DÉTECTÉ")
            risks_found.append("Risques d'écrasement des doigts")
        else:
            print(f"  PLAN-004 | Risques écrasement  : ✓ CONFORME")
            risks_ok.append("Écrasement")

        # Bilan
        print(f"\n  {'─' * 60}")
        if risks_found:
            print(f"  BILAN: {len(risks_found)} risque(s) identifié(s)")
            for risk in risks_found:
                print(f"    ⚠  {risk}")

            # Violation synthèse
            for space in spaces:
                violation = {
                    "rule_id": "PLAN-005",
                    "severity": "HAUTE",
                    "space_name": space.get('name', 'Inconnu'),
                    "space_global_id": space.get('global_id', ''),
                    "description": f"Synthèse: {len(risks_found)} risque(s) détecté(s) sur plancher technique",
                    "details": {
                        "plancher_type": self.responses.get('plan_001_type', 'N/A'),
                        "risks_found": risks_found,
                        "risks_ok": risks_ok,
                        "total_risks": len(risks_found),
                        "responses": {
                            "PLAN-001": self.responses.get('plan_001_has_plancher', False),
                            "PLAN-001_type": self.responses.get('plan_001_type', 'N/A'),
                            "PLAN-002": self.responses.get('plan_002_cables_protected', True),
                            "PLAN-003": self.responses.get('plan_003_humidity', False),
                            "PLAN-004": self.responses.get('plan_004_crush_risk', False)
                        },
                        "mode": "formulaire_interactif",
                        "timestamp": datetime.now().isoformat()
                    },
                    "location": space.get('centroid', (0, 0, 0)),
                    "recommendation": f"Actions requises: {'; '.join(risks_found)}"
                }
                self.violations.append(violation)
        else:
            print(f"  BILAN: Aucun risque identifié - Tous les points sont conformes ✓")
            logger.info("   PLAN-005: Synthèse - Tous les points conformes")

        print("=" * 70 + "\n")
