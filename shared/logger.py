"""
============================================================================
LOGGER - Système de Logging Centralisé
============================================================================
Gère tous les logs du système avec niveaux, couleurs et traçabilité.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
import coloredlogs


class SecurityLogger:
    """Logger centralisé pour l'analyse de sécurité"""

    def __init__(self, name: str = "SecurityAnalyzer", level: str = "INFO"):
        """
        Initialise le logger

        Args:
            name: Nom du logger
            level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))

        # Empêcher duplication des handlers
        if not self.logger.handlers:
            self._setup_console_handler()
            self._setup_file_handler()

    def _setup_console_handler(self):
        """Configure le handler console avec couleurs"""
        console_format = '%(asctime)s | %(levelname)-8s | %(message)s'

        coloredlogs.install(
            level=self.logger.level,
            logger=self.logger,
            fmt=console_format,
            datefmt='%H:%M:%S',
            level_styles={
                'debug': {'color': 'cyan'},
                'info': {'color': 'green'},
                'warning': {'color': 'yellow', 'bold': True},
                'error': {'color': 'red', 'bold': True},
                'critical': {'color': 'red', 'bold': True, 'background': 'white'}
            },
            field_styles={
                'asctime': {'color': 'white'},
                'levelname': {'color': 'white', 'bold': True}
            }
        )

    def _setup_file_handler(self):
        """Configure le handler fichier"""
        # Créer dossier logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Nom fichier avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"analysis_{timestamp}.log"

        # Handler fichier
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Toujours DEBUG dans fichier

        file_format = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)

        self.logger.addHandler(file_handler)
        self.logger.info(f"  Log file: {log_file}")

    # === MÉTHODES DE LOGGING ===

    def debug(self, message: str):
        """Log niveau DEBUG"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log niveau INFO"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log niveau WARNING"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log niveau ERROR"""
        self.logger.error(message)

    def critical(self, message: str):
        """Log niveau CRITICAL"""
        self.logger.critical(message)

    def rule_violation(self, rule_id: str, space_name: str, details: str):
        """Log spécifique pour violation de règle"""
        self.logger.warning(f"[{rule_id}] Violation détectée | {space_name} | {details}")

    def rule_passed(self, rule_id: str, space_name: str):
        """Log pour règle respectée"""
        self.logger.debug(f"  [{rule_id}] Conforme | {space_name}")

    def extraction_progress(self, current: int, total: int, item_type: str):
        """Log progression extraction"""
        percentage = (current / total * 100) if total > 0 else 0
        self.logger.info(f"   Extraction {item_type}: {current}/{total} ({percentage:.1f}%)")

    def analysis_start(self, rule_id: str):
        """Log début analyse règle"""
        self.logger.info(f" Analyse {rule_id} démarrée")

    def analysis_complete(self, rule_id: str, violations: int):
        """Log fin analyse règle"""
        if violations == 0:
            self.logger.info(f"  {rule_id} terminée - Aucune violation")
        else:
            self.logger.warning(f"   {rule_id} terminée - {violations} violation(s)")

    def section_header(self, title: str):
        """Log pour séparer les sections"""
        separator = "=" * 70
        self.logger.info(f"\n{separator}")
        self.logger.info(f"  {title}")
        self.logger.info(f"{separator}\n")


# === INSTANCE GLOBALE ===
# Permet d'importer: from shared.logger import logger
logger = SecurityLogger()
