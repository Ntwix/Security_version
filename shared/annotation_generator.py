"""ANNOTATION GENERATOR - Génération Rapports d'Annotations/ Compile les résultats de toutes les règles et génère rapports JSON/Excel."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import pandas as pd

from shared.logger import logger


class AnnotationGenerator:
    """Générateur de rapports d'annotations"""

    def __init__(self):
        """Initialise le générateur"""
        self.all_violations = []
        self.metadata = {}

        logger.info("   Annotation Generator initialisé")

    def compile_results(self, violations_by_rule: Dict[str, List[Dict]],
                       ifc_path: str, extraction_summary: Dict):
        """
        Compile tous les résultats
        Args:
            violations_by_rule: {rule_id: [violations]}
            ifc_path: Chemin fichier IFC analysé
            extraction_summary: Résumé extraction
        """
        logger.section_header("COMPILATION RÉSULTATS")

        # Métadonnées
        self.metadata = {
            "timestamp": datetime.now().isoformat(),
            "ifc_file": Path(ifc_path).name,
            "rules_analyzed": list(violations_by_rule.keys()),
            "extraction_summary": extraction_summary
        }

        # Compiler violations
        self.all_violations = []
        for rule_id, violations in violations_by_rule.items():
            self.all_violations.extend(violations)

        # Statistiques
        stats = self._calculate_statistics(violations_by_rule)
        self.metadata["statistics"] = stats

        logger.info(f"  Compilation terminée:")
        logger.info(f"   - Total violations: {stats['total_violations']}")
        logger.info(f"   - Critiques: {stats['critical']}")
        logger.info(f"   - Importantes: {stats['important']}")

    def _calculate_statistics(self, violations_by_rule: Dict) -> Dict:
        """Calcule statistiques"""
        stats = {
            "total_violations": 0,
            "critical": 0,
            "important": 0,
            "by_rule": {}
        }

        for rule_id, violations in violations_by_rule.items():
            count = len(violations)
            stats["total_violations"] += count
            stats["by_rule"][rule_id] = count

            # Compter par sévérité
            for violation in violations:
                severity = violation.get('severity', 'UNKNOWN')
                if severity == 'CRITICAL':
                    stats["critical"] += 1
                elif severity == 'IMPORTANT':
                    stats["important"] += 1

        return stats

    def save_json(self, output_path: str):
        """
        Sauvegarde résultats en JSON
        Args:
            output_path: Chemin fichier sortie
        """
        output = {
            "metadata": self.metadata,
            "violations": self.all_violations
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"   Rapport JSON sauvegardé: {output_file}")

    def save_excel(self, output_path: str):
        """
        Sauvegarde résultats en Excel
        Args:
            output_path: Chemin fichier sortie .xlsx
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Préparer données pour DataFrame
        rows = []
        for violation in self.all_violations:
            row = {
                "Règle": violation.get('rule_id', ''),
                "Sévérité": violation.get('severity', ''),
                "Espace": violation.get('space_name', ''),
                "Description": violation.get('description', ''),
                "Recommandation": violation.get('recommendation', ''),
                "Position X": violation.get('location', [0, 0, 0])[0],
                "Position Y": violation.get('location', [0, 0, 0])[1],
                "Position Z": violation.get('location', [0, 0, 0])[2]
            }

            # Ajouter détails spécifiques
            details = violation.get('details', {})
            for key, value in details.items():
                # Ignorer listes complexes
                if not isinstance(value, (list, dict)):
                    row[key] = value

            rows.append(row)

        # Créer DataFrame
        if rows:
            df = pd.DataFrame(rows)

            # Sauvegarder avec style
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Violations', index=False)

                # Feuille statistiques
                stats_data = {
                    "Métrique": [
                        "Fichier IFC",
                        "Date analyse",
                        "Total violations",
                        "Critiques",
                        "Importantes"
                    ],
                    "Valeur": [
                        self.metadata.get('ifc_file', ''),
                        self.metadata.get('timestamp', ''),
                        self.metadata['statistics']['total_violations'],
                        self.metadata['statistics']['critical'],
                        self.metadata['statistics']['important']
                    ]
                }
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='Statistiques', index=False)

                # Feuille par règle
                by_rule_data = {
                    "Règle": list(self.metadata['statistics']['by_rule'].keys()),
                    "Nombre violations": list(self.metadata['statistics']['by_rule'].values())
                }
                df_by_rule = pd.DataFrame(by_rule_data)
                df_by_rule.to_excel(writer, sheet_name='Par Règle', index=False)

            logger.info(f"   Rapport Excel sauvegardé: {output_file}")
        else:
            logger.warning("   Aucune violation à exporter en Excel")

    def print_summary(self):
        """Affiche résumé dans console"""
        print("\n" + "="*70)
        print("RÉSUMÉ ANALYSE")
        print("="*70)

        print(f"\n Fichier analysé: {self.metadata.get('ifc_file', 'N/A')}")
        print(f"   Date: {self.metadata.get('timestamp', 'N/A')}")

        stats = self.metadata.get('statistics', {})

        print(f"\n   VIOLATIONS:")
        print(f"   Total: {stats.get('total_violations', 0)}")
        print(f"      Critiques: {stats.get('critical', 0)}")
        print(f"     Importantes: {stats.get('important', 0)}")

        print(f"\n PAR RÈGLE:")
        by_rule = stats.get('by_rule', {})
        for rule_id, count in by_rule.items():
            print(f"   {rule_id}: {count} violation(s)")

        print("\n" + "="*70)

        if stats.get('total_violations', 0) == 0:
            print("  AUCUNE VIOLATION DÉTECTÉE - Maquette conforme")
        else:
            print("   VIOLATIONS DÉTECTÉES - Voir rapports pour détails")

        print("="*70 + "\n")
