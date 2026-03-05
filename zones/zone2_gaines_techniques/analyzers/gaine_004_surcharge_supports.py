"""
============================================================================
GAINE-004 - Espacement supports chemins de câbles
============================================================================
Règle: Tout chemin de câbles de longueur > 2m doit être fixé sur un support
physique (console, étrier, tige filetée...).

Contexte CHU Ibn Sina:
- Les chemins de câbles sont modélisés comme "Chemin de câbles avec raccords"
  (famille Revit OST_CableTray → IfcCableCarrierSegment)
- Types de service : CDC CFO, CDC CFA, CDC Incendie
- Aucun support physique n'est modélisé dans la maquette
→ Toute section > 2m génère une alerte avec estimation de charge

Sévérité: HAUTE
"""

import json
from typing import List, Dict, Optional
from pathlib import Path

from shared.logger import logger


class GAINE004SurchargeSupportsChecker:
    """Analyseur règle GAINE-004 - Espacement supports chemins de câbles"""

    RULE_ID = "GAINE-004"
    RULE_NAME = "Espacement supports chemins de câbles"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "rules_config.json")
        self.config_path = Path(config_path)
        self.config = {}
        self.violations = []

        # Valeurs par défaut
        self.max_span_m = 2.0
        self.safety_margin = 0.15
        self.default_support_capacity = 50.0
        self.cf_weight_per_m = 1.4
        self.cfa_weight_per_m = 0.6
        self.default_weight_per_m = 1.0
        self.cable_tray_ifc_type = "IfcCableCarrierSegment"
        self.cf_keywords = ["cfo", "cdc cfo", "courant fort"]
        self.cfa_keywords = ["cfa", "cdc cfa", "cdc incendie", "courant faible"]

        self.load_config()
        logger.info(f" {self.RULE_ID} Checker initialisé")

    def load_config(self):
        """Charge configuration règle"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_full = json.load(f)
            self.config = config_full.get(self.RULE_ID, {})
            params = self.config.get('parameters', {})

            self.max_span_m = float(params.get('max_span_m', 2.0))
            self.safety_margin = float(params.get('safety_margin_percent', 15)) / 100
            self.default_support_capacity = float(params.get('default_support_capacity_kg', 50))
            self.cf_weight_per_m = float(params.get('courant_fort_weight_kg_per_m', 1.4))
            self.cfa_weight_per_m = float(params.get('courant_faible_weight_kg_per_m', 0.6))
            self.default_weight_per_m = float(params.get('default_weight_kg_per_m', 1.0))
            self.cable_tray_ifc_type = params.get('cable_tray_ifc_type', 'IfcCableCarrierSegment')
            self.cf_keywords = [k.lower() for k in params.get('courant_fort_keywords',
                                                               ["cfo", "cdc cfo", "courant fort"])]
            self.cfa_keywords = [k.lower() for k in params.get('courant_faible_keywords',
                                                                ["cfa", "cdc cfa", "cdc incendie", "courant faible"])]
        except Exception as e:
            logger.error(f"  Erreur config {self.RULE_ID}: {str(e)}")

    def analyze(self, spaces: List[Dict], equipment: List[Dict],
                slabs: List[Dict], space_types: Dict) -> List[Dict]:
        """Lance analyse GAINE-004"""
        logger.analysis_start(self.RULE_ID)
        self.violations = []

        # Extraire tous les chemins de câbles depuis la liste equipment
        cable_trays = [eq for eq in equipment if self._is_cable_tray(eq)]

        if not cable_trays:
            logger.info(f"    Aucun chemin de câbles trouvé (IfcCableCarrierSegment) pour {self.RULE_ID}")
            logger.info(f"    Vérifier que OST_CableTray est bien extrait dans BIMDataExtractor")
            return self.violations

        logger.info(f"   {len(cable_trays)} chemins de câbles détectés — seuil espacement: {self.max_span_m}m")

        for tray in cable_trays:
            self._check_cable_tray(tray)

        logger.analysis_complete(self.RULE_ID, len(self.violations))
        return self.violations

    def _check_cable_tray(self, tray: Dict):
        """
        Vérifie si un chemin de câbles dépasse la portée max sans support.
        Puisque aucun support n'est modélisé, toute section > max_span_m est en violation.
        """
        tray_name = tray.get('name', 'Inconnu')
        length_m = tray.get('max_dimension_m', 0.0)

        if length_m <= 0:
            logger.debug(f"  {tray_name}: longueur non disponible, ignoré")
            return

        if length_m <= self.max_span_m:
            logger.rule_passed(self.RULE_ID, tray_name)
            return

        # Longueur > 2m sans support → violation
        service_type = self._get_service_type(tray)
        weight_per_m = self._select_weight_per_meter(tray)
        estimated_load = round(length_m * weight_per_m, 1)
        safe_capacity = round(self.default_support_capacity * (1 - self.safety_margin), 1)
        nb_supports_requis = int(length_m / self.max_span_m)

        violation = {
            "rule_id": self.RULE_ID,
            "severity": "HAUTE",
            "space_name": tray_name,
            "space_global_id": tray.get('global_id', ''),
            "description": f"Chemin de câbles sans support physique sur {length_m:.2f}m "
                           f"(max autorisé: {self.max_span_m}m)",
            "details": {
                "tray_name": tray_name,
                "service_type": service_type,
                "length_m": round(length_m, 2),
                "max_span_m": self.max_span_m,
                "estimated_load_kg": estimated_load,
                "weight_per_m_kg": weight_per_m,
                "supports_required": nb_supports_requis,
                "safe_capacity_kg": safe_capacity,
            },
            "location": tray.get('centroid', (0, 0, 0)),
            "recommendation": (
                f"Installer {nb_supports_requis} support(s) tous les {self.max_span_m}m. "
                f"Charge estimée: {estimated_load}kg "
                f"(capacité admissible: {safe_capacity}kg)."
            )
        }

        self.violations.append(violation)
        logger.rule_violation(
            self.RULE_ID, tray_name,
            f"Portée {length_m:.2f}m > {self.max_span_m}m — charge estimée {estimated_load}kg"
        )

    def _is_cable_tray(self, equipment: Dict) -> bool:
        """Vérifie si un équipement est un chemin de câbles"""
        ifc_type = equipment.get('ifc_type', '')
        if ifc_type == self.cable_tray_ifc_type:
            return True
        # Fallback par nom (si IFC type non disponible)
        name = equipment.get('name', '').lower()
        return 'chemin de c' in name or 'cable tray' in name

    def _get_service_type(self, tray: Dict) -> str:
        """Extrait le type de service (CDC CFO / CDC CFA / CDC Incendie)"""
        props = self._props_to_dict(tray.get('properties', {}))
        service = props.get('Type de service', '') or props.get('Service Type', '') or ''
        if service:
            return service
        # Fallback depuis le nom
        name = tray.get('name', '').lower()
        if 'incendie' in name:
            return 'CDC Incendie'
        if any(k in name for k in self.cfa_keywords):
            return 'CDC CFA'
        if any(k in name for k in self.cf_keywords):
            return 'CDC CFO'
        return 'Inconnu'

    def _select_weight_per_meter(self, tray: Dict) -> float:
        """Sélectionne le poids/m selon le type de service"""
        service = self._get_service_type(tray).lower()
        name = tray.get('name', '').lower()
        combined = f"{service} {name}"
        # CFA d'abord (évite que 'cf' matche 'cfa')
        for kw in self.cfa_keywords:
            if kw in combined:
                return self.cfa_weight_per_m
        for kw in self.cf_keywords:
            if kw in combined:
                return self.cf_weight_per_m
        return self.default_weight_per_m

    @staticmethod
    def _props_to_dict(props) -> Dict:
        """Convertit les propriétés en dict (gère le format list de DataContractJsonSerializer)."""
        if isinstance(props, dict):
            return props
        if isinstance(props, list):
            result = {}
            for item in props:
                if isinstance(item, dict) and 'Key' in item:
                    result[item['Key']] = item.get('Value', '')
            return result
        return {}
