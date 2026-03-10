"""
============================================================================
GAINE-005 - Calcul de charge des supports de chemins de câbles
============================================================================
Règle: La charge totale portée par chaque support de chemin de câbles
ne doit pas dépasser la capacité admissible (avec marge sécurité 20%).

Fonctionnement:
- Python extrait les CDC de la maquette et les groupe par type de service
  (CDC CFO / CDC CFA / CDC Incendie)
- Calcule la longueur totale de chaque type dans la maquette
- Génère un JSON "cdc_summary" avec ces infos
- Le plugin Revit C# affiche un formulaire interactif (ChargeSupportsDialog)
- L'utilisateur déclare les câbles (matériau CU/AL, conducteurs×section, quantité)
  qui passent sur chaque type de CDC
- Les masses viennent de la norme NF C 32-321 (tableau fourni par l'encadrant)
- Le C# calcule le poids total par mètre et génère les violations

Sévérité: HAUTE
"""

import json
from typing import List, Dict, Optional
from pathlib import Path

from shared.logger import logger

DEFAULT_LENGTH_KEYS = ["Length", "Longueur", "Length_m", "Longueur_m"]


class GAINE005CalculChargeSupportsChecker:
    RULE_ID = "GAINE-005"
    RULE_NAME = "Calcul charge supports câbles"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        self.default_support_capacity = 90.0
        self.safety_margin = 0.20
        self.length_keys = list(DEFAULT_LENGTH_KEYS)

        self.cf_keywords  = ["cfo", "cdc cfo", "courant fort", "power", "ht", "bt", "tgbt"]
        self.cfa_keywords = ["cfa", "cdc cfa", "courant faible", "data", "vdi", "rj45", "fibre", "fiber"]
        self.inc_keywords = ["incendie", "fire", "sprinkler"]

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
            self.config = config_full.get(self.RULE_ID, {})
            params = self.config.get('parameters', {})
            self.default_support_capacity = float(params.get('default_support_capacity_kg', 90.0))
            self.safety_margin = float(params.get('safety_margin_percent', 20)) / 100
            self.length_keys = list(params.get('length_property_keys', DEFAULT_LENGTH_KEYS))
        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """
        Extraction des CDC par type de service.
        Produit une violation marker avec le champ 'cdc_summary'
        que le C# lira pour afficher le formulaire de saisie.
        """
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        cable_trays = [eq for eq in equipment if self._is_cable_tray(eq)]

        if not cable_trays:
            logger.info(f"    Aucun chemin de câbles trouvé pour {self.RULE_ID}")
            return self.violations

        logger.info(f"   {len(cable_trays)} chemins de câbles — extraction par type...")

        # Grouper par type de service
        groups = {"CFO": [], "CFA": [], "Incendie": [], "Autre": []}
        for tray in cable_trays:
            t = self._get_service_type(tray)
            groups[t].append(tray)

        # Construire le résumé par type
        cdc_summary = []
        for service_type, trays in groups.items():
            if not trays:
                continue
            total_length = sum(self._extract_length(t) for t in trays)
            cdc_summary.append({
                "service_type": service_type,
                "segment_count": len(trays),
                "total_length_m": round(total_length, 2),
            })

        if not cdc_summary:
            return self.violations

        # Violation marker — sera lue par le C# pour ouvrir le formulaire
        self.violations.append({
            "rule_id": self.RULE_ID,
            "severity": "HAUTE",
            "space_name": "CDC — en attente de saisie utilisateur",
            "space_global_id": "",
            "description": f"Vérification de charge requise pour {len(cable_trays)} chemins de câbles",
            "details": {
                "cdc_summary": cdc_summary,
                "support_capacity_kg": self.default_support_capacity,
                "safety_margin_percent": int(self.safety_margin * 100),
            },
            "location": [0, 0, 0],
            "recommendation": "Saisir les types de câbles dans le formulaire GAINE-005."
        })

        logger.info(f"   Résumé CDC : {cdc_summary}")
        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    # =========================================================================
    #  HELPERS
    # =========================================================================

    def _is_cable_tray(self, equipment: Dict) -> bool:
        if equipment.get('ifc_type') == 'IfcCableCarrierSegment':
            return True
        name = equipment.get('name', '').lower()
        return 'chemin de c' in name or 'cable tray' in name or 'cdc ' in name

    def _get_service_type(self, tray: Dict) -> str:
        props = self._props_to_dict(tray.get('properties', {}))
        service = (props.get('Type de service', '') or props.get('Service Type', '') or '').lower()
        name = tray.get('name', '').lower()
        combined = f"{service} {name}"

        for kw in self.inc_keywords:
            if kw in combined:
                return "Incendie"
        for kw in self.cfa_keywords:
            if kw in combined:
                return "CFA"
        for kw in self.cf_keywords:
            if kw in combined:
                return "CFO"
        return "Autre"

    def _extract_length(self, tray: Dict) -> float:
        props = self._props_to_dict(tray.get('properties', {}))
        for key in self.length_keys:
            if key in props:
                value = self._safe_float(props[key])
                if value and value > 0:
                    return value
        fallback = tray.get('max_dimension_m')
        return fallback if fallback and fallback > 0 else 1.0

    @staticmethod
    def _props_to_dict(props) -> Dict:
        if isinstance(props, dict):
            return props
        if isinstance(props, list):
            result = {}
            for item in props:
                if isinstance(item, dict) and 'Key' in item:
                    result[item['Key']] = item.get('Value', '')
            return result
        return {}

    @staticmethod
    def _safe_float(value, default: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default
        try:
            text = str(value).strip().replace(',', '.')
            return float(text) if text else default
        except Exception:
            return default
