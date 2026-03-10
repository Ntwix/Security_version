#!/usr/bin/env python3
"""
============================================================================
MAIN - Système Multi-Zones d'Analyse de Conformité Sécurité
============================================================================
Point d'entrée principal du système d'analyse automatique des maquettes 3D
pour la détection des non-conformités de sécurité.

Catégories supportées:
  Catégorie 1 - Locaux Électriques (ELEC-001 à ELEC-004)
  Catégorie 2 - Gaines Techniques (GAINE-001 à GAINE-005)
  Catégorie 3 - Faux Plafonds Techniques (FPLAF-001 à FPLAF-003)
  Catégorie 4 - Planchers Techniques (PLAN-001 à PLAN-005) [Formulaire interactif]
  Catégorie 5 - Risques Chantier (CHANT-001 à CHANT-005)

Usage:
    python main.py --zone 1 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc
    python main.py --zone 2 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc
    python main.py --zone 3 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc
    python main.py --zone 4 --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc
    python main.py --zone all --ifc-archi maquettes/Ibn_Sina_ARCHI.ifc --ifc-elec maquettes/Ibn_Sina_ELEC.ifc
"""

import sys
import json
import click
from pathlib import Path

# Imports partagés
from shared.logger import logger
from shared.annotation_generator import AnnotationGenerator


def _load_extracted_json(json_path: str) -> dict:
    """Charge des données pré-extraites depuis un JSON (mode Revit Plugin)."""
    logger.info(f"  Mode: Données pré-extraites (JSON)")
    logger.info(f"  Fichier: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convertir les tuples bbox si nécessaire (JSON les stocke en listes)
    for key in ['spaces', 'equipment', 'doors', 'slabs']:
        for item in data.get(key, []):
            if 'bbox_min' in item and isinstance(item['bbox_min'], list):
                item['bbox_min'] = tuple(item['bbox_min'])
            if 'bbox_max' in item and isinstance(item['bbox_max'], list):
                item['bbox_max'] = tuple(item['bbox_max'])
            if 'centroid' in item and isinstance(item['centroid'], list):
                item['centroid'] = tuple(item['centroid'])

    # Ajouter summary si absent
    if 'summary' not in data:
        data['summary'] = {
            "spaces": len(data.get('spaces', [])),
            "equipment": len(data.get('equipment', [])),
            "doors": len(data.get('doors', [])),
            "slabs": len(data.get('slabs', []))
        }

    logger.info(f"   - Spaces: {data['summary']['spaces']}")
    logger.info(f"   - Equipment: {data['summary']['equipment']}")
    logger.info(f"   - Doors: {data['summary']['doors']}")
    logger.info(f"   - Slabs: {data['summary']['slabs']}")

    return data


def run_zone1(extracted_data, output_dir, rules, format_choice):
    """Exécute l'analyse Catégorie 1 - Locaux Électriques"""
    from categories.categorie1_locaux_electriques.space_identifier import SpaceIdentifier
    from categories.categorie1_locaux_electriques.analyzers import (
        ELEC001WeightChecker,
        ELEC002VentilationChecker,
        ELEC003DoorWidthChecker,
        ELEC004ShowerZoneChecker
    )

    logger.section_header("CATÉGORIE 1 - LOCAUX ÉLECTRIQUES")

    # Classification des espaces
    logger.section_header("CLASSIFICATION DES ESPACES PAR CATEGORIE")
    identifier = SpaceIdentifier()
    space_types = identifier.classify_all_spaces(extracted_data['spaces'])

    # Afficher résumé classification
    logger.info(f"   Espaces par règle de conformité:")
    for rule in ['ELEC-001', 'ELEC-002', 'ELEC-003', 'ELEC-004']:
        concerned = identifier.get_spaces_for_rule(space_types, rule)
        logger.info(f"     {rule}: {len(concerned)} espaces concernés")

    # Analyse règles
    logger.section_header("ANALYSE RÈGLES DE SÉCURITÉ - ZONE 1")

    violations_by_rule = {}

    if rules:
        rules_to_analyze = [r for r in rules if r.startswith('ELEC')]
    else:
        rules_to_analyze = ['ELEC-001', 'ELEC-002', 'ELEC-003', 'ELEC-004']

    if not rules_to_analyze:
        logger.info("   Aucune règle ELEC à analyser pour Catégorie 1")
        return {}

    logger.info(f" Règles à analyser: {', '.join(rules_to_analyze)}")

    if 'ELEC-001' in rules_to_analyze:
        checker_001 = ELEC001WeightChecker()
        violations_by_rule['ELEC-001'] = checker_001.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )

    if 'ELEC-002' in rules_to_analyze:
        checker_002 = ELEC002VentilationChecker()
        violations_by_rule['ELEC-002'] = checker_002.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )

    if 'ELEC-003' in rules_to_analyze:
        checker_003 = ELEC003DoorWidthChecker()
        violations_by_rule['ELEC-003'] = checker_003.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types, extracted_data['doors']
        )

    if 'ELEC-004' in rules_to_analyze:
        checker_004 = ELEC004ShowerZoneChecker()
        violations_by_rule['ELEC-004'] = checker_004.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )

    # Génération rapports
    logger.section_header("GÉNÉRATION RAPPORTS - ZONE 1")
    ifc_name = "Catégorie 1 - Locaux Électriques"
    generator = AnnotationGenerator()
    generator.compile_results(violations_by_rule, ifc_name, extracted_data['summary'])

    output_path = Path(output_dir)
    if format_choice in ['json', 'both']:
        generator.save_json(str(output_path / 'analysis_results.json'))
    if format_choice in ['excel', 'both']:
        try:
            generator.save_excel(str(output_path / 'analysis_results.xlsx'))
        except PermissionError:
            logger.warning("  Impossible d'ecrire le fichier Excel (fichier ouvert ?). JSON sauvegarde.")

    generator.print_summary()

    return violations_by_rule


def run_zone2(extracted_data, output_dir, rules, format_choice):
    """Exécute l'analyse Catégorie 2 - Gaines Techniques"""
    from categories.categorie2_gaines_techniques.gaine_identifier import GaineIdentifier
    from categories.categorie2_gaines_techniques.analyzers import (
        GAINE001ChuteObjetsChecker,
        GAINE002CroisementReseauxChecker,
        GAINE003TrappesAccesChecker,
        GAINE004SurchargeSupportsChecker,
        GAINE005CalculChargeSupportsChecker
    )

    logger.section_header("CATÉGORIE 2 - GAINES TECHNIQUES")

    # Identification des gaines techniques
    logger.section_header("IDENTIFICATION DES GAINES TECHNIQUES")
    identifier = GaineIdentifier()
    gaine_types = identifier.classify_all_spaces(extracted_data['spaces'])

    # Afficher résumé classification
    logger.info(f"   Espaces par règle de conformité:")
    for rule in ['GAINE-001', 'GAINE-002', 'GAINE-003', 'GAINE-004', 'GAINE-005']:
        concerned = identifier.get_spaces_for_rule(gaine_types, rule)
        logger.info(f"     {rule}: {len(concerned)} espaces concernés")

    # Analyse règles
    logger.section_header("ANALYSE RÈGLES DE SÉCURITÉ - ZONE 2")

    violations_by_rule = {}

    if rules:
        rules_to_analyze = [r for r in rules if r.startswith('GAINE')]
    else:
        rules_to_analyze = ['GAINE-001', 'GAINE-002', 'GAINE-003', 'GAINE-004', 'GAINE-005']

    if not rules_to_analyze:
        logger.info("   Aucune règle GAINE à analyser pour Catégorie 2")
        return {}

    logger.info(f" Règles à analyser: {', '.join(rules_to_analyze)}")

    if 'GAINE-001' in rules_to_analyze:
        checker = GAINE001ChuteObjetsChecker()
        violations_by_rule['GAINE-001'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], gaine_types
        )

    if 'GAINE-002' in rules_to_analyze:
        checker = GAINE002CroisementReseauxChecker()
        violations_by_rule['GAINE-002'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], gaine_types
        )

    if 'GAINE-003' in rules_to_analyze:
        checker = GAINE003TrappesAccesChecker()
        violations_by_rule['GAINE-003'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], gaine_types,
            doors=extracted_data.get('doors', [])
        )
        
    if 'GAINE-004' in rules_to_analyze:
         checker = GAINE004SurchargeSupportsChecker()
         violations_by_rule['GAINE-004'] = checker.analyze(
             extracted_data['spaces'], extracted_data['equipment'],
             extracted_data['slabs'], gaine_types
        )
    if 'GAINE-005' in rules_to_analyze:
        checker = GAINE005CalculChargeSupportsChecker()
        violations_by_rule['GAINE-005'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], gaine_types
        )


    # Génération rapports
    logger.section_header("GÉNÉRATION RAPPORTS - ZONE 2")
    ifc_name = "Catégorie 2 - Gaines Techniques"
    generator = AnnotationGenerator()
    generator.compile_results(violations_by_rule, ifc_name, extracted_data['summary'])

    output_path = Path(output_dir)
    if format_choice in ['json', 'both']:
        generator.save_json(str(output_path / 'analysis_results.json'))
    if format_choice in ['excel', 'both']:
        generator.save_excel(str(output_path / 'analysis_results.xlsx'))

    generator.print_summary()

    return violations_by_rule


def run_zone3(extracted_data, output_dir, rules, format_choice):
    """Exécute l'analyse Catégorie 3 - Faux Plafonds Techniques"""
    from categories.categorie3_faux_plafonds_techniques.fplaf_identifier import FPlafIdentifier
    from categories.categorie3_faux_plafonds_techniques.analyzers import (
        FPLAF001ChuteHauteurChecker,
        FPLAF002SurchargePlafondChecker,
        FPLAF003PoussieresChecker
    )

    logger.section_header("CATÉGORIE 3 - FAUX PLAFONDS TECHNIQUES")

    # Identification des espaces faux-plafonds
    logger.section_header("IDENTIFICATION DES FAUX-PLAFONDS")
    identifier = FPlafIdentifier()
    fplaf_types = identifier.classify_all_spaces(extracted_data['spaces'])

    # Afficher résumé classification
    logger.info(f"   Espaces par règle de conformité:")
    for rule in ['FPLAF-001', 'FPLAF-002', 'FPLAF-003']:
        concerned = identifier.get_spaces_for_rule(fplaf_types, rule)
        logger.info(f"     {rule}: {len(concerned)} espaces concernés")

    # Analyse règles
    logger.section_header("ANALYSE RÈGLES DE SÉCURITÉ - ZONE 3")

    violations_by_rule = {}

    if rules:
        rules_to_analyze = [r for r in rules if r.startswith('FPLAF')]
    else:
        rules_to_analyze = ['FPLAF-001', 'FPLAF-002', 'FPLAF-003']

    if not rules_to_analyze:
        logger.info("   Aucune règle FPLAF à analyser pour Catégorie 3")
        return {}

    logger.info(f" Règles à analyser: {', '.join(rules_to_analyze)}")

    if 'FPLAF-001' in rules_to_analyze:
        checker = FPLAF001ChuteHauteurChecker()
        violations_by_rule['FPLAF-001'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], fplaf_types
        )

    if 'FPLAF-002' in rules_to_analyze:
        checker = FPLAF002SurchargePlafondChecker()
        violations_by_rule['FPLAF-002'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], fplaf_types
        )

    if 'FPLAF-003' in rules_to_analyze:
        checker = FPLAF003PoussieresChecker()
        violations_by_rule['FPLAF-003'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], fplaf_types
        )

    # Génération rapports
    logger.section_header("GÉNÉRATION RAPPORTS - ZONE 3")
    ifc_name = "Catégorie 3 - Faux Plafonds Techniques"
    generator = AnnotationGenerator()
    generator.compile_results(violations_by_rule, ifc_name, extracted_data['summary'])

    output_path = Path(output_dir)
    if format_choice in ['json', 'both']:
        generator.save_json(str(output_path / 'analysis_results.json'))
    if format_choice in ['excel', 'both']:
        generator.save_excel(str(output_path / 'analysis_results.xlsx'))

    generator.print_summary()

    return violations_by_rule


def run_zone5(extracted_data, output_dir, rules, format_choice):
    """Exécute l'analyse Catégorie 5 - Risques Chantier"""
    from categories.categorie5_risques_chantier.chantier_identifier import ChantierIdentifier
    from categories.categorie5_risques_chantier.analyzers import (
        CHANT001ManutentionChecker,
        CHANT002AccessibiliteChecker,
        CHANT003TravailHauteurChecker,
        CHANT004GaineAscenseurChecker,
        CHANT005VentilationChecker
    )

    logger.section_header("CATÉGORIE 5 - RISQUES CHANTIER")

    identifier = ChantierIdentifier()
    space_types = identifier.classify_all_spaces(extracted_data['spaces'])

    logger.info(f"   Espaces par règle de conformité:")
    for rule in ['CHANT-001', 'CHANT-002', 'CHANT-003', 'CHANT-004', 'CHANT-005']:
        concerned = identifier.get_spaces_for_rule(space_types, rule)
        logger.info(f"     {rule}: {len(concerned)} espaces concernés")

    violations_by_rule = {}

    if rules:
        rules_to_analyze = [r for r in rules if r.startswith('CHANT')]
    else:
        rules_to_analyze = ['CHANT-001', 'CHANT-002', 'CHANT-003', 'CHANT-004', 'CHANT-005']

    if not rules_to_analyze:
        logger.info("   Aucune règle CHANT à analyser pour Catégorie 5")
        return {}

    if 'CHANT-001' in rules_to_analyze:
        checker = CHANT001ManutentionChecker()
        violations_by_rule['CHANT-001'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types,
            doors=extracted_data.get('doors', [])
        )
    if 'CHANT-002' in rules_to_analyze:
        checker = CHANT002AccessibiliteChecker()
        violations_by_rule['CHANT-002'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )
    if 'CHANT-003' in rules_to_analyze:
        checker = CHANT003TravailHauteurChecker()
        violations_by_rule['CHANT-003'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )
    if 'CHANT-004' in rules_to_analyze:
        checker = CHANT004GaineAscenseurChecker()
        violations_by_rule['CHANT-004'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )
    if 'CHANT-005' in rules_to_analyze:
        checker = CHANT005VentilationChecker()
        violations_by_rule['CHANT-005'] = checker.analyze(
            extracted_data['spaces'], extracted_data['equipment'],
            extracted_data['slabs'], space_types
        )

    logger.section_header("GÉNÉRATION RAPPORTS - CATÉGORIE 5")
    generator = AnnotationGenerator()
    generator.compile_results(violations_by_rule, "Catégorie 5 - Risques Chantier", extracted_data['summary'])

    output_path = Path(output_dir)
    if format_choice in ['json', 'both']:
        generator.save_json(str(output_path / 'analysis_results.json'))
    if format_choice in ['excel', 'both']:
        try:
            generator.save_excel(str(output_path / 'analysis_results.xlsx'))
        except PermissionError:
            logger.warning("  Impossible d'ecrire le fichier Excel. JSON sauvegarde.")

    generator.print_summary()
    return violations_by_rule


def run_zone4(extracted_data, output_dir, rules, format_choice):
    """Exécute l'analyse Catégorie 4 - Planchers Techniques (Formulaire interactif)"""
    from categories.categorie4_planchers_techniques.plancher_identifier import PlancherIdentifier
    from categories.categorie4_planchers_techniques.analyzers import PLAN001005FormulaireChecker

    logger.section_header("CATÉGORIE 4 - PLANCHERS TECHNIQUES")

    # Identification des espaces planchers techniques
    logger.section_header("IDENTIFICATION DES PLANCHERS TECHNIQUES")
    identifier = PlancherIdentifier()
    plancher_types = identifier.classify_all_spaces(extracted_data['spaces'])

    # Afficher résumé classification
    logger.info(f"   Espaces par règle de conformité:")
    for rule in ['PLAN-001', 'PLAN-002', 'PLAN-003', 'PLAN-004', 'PLAN-005']:
        concerned = identifier.get_spaces_for_rule(plancher_types, rule)
        logger.info(f"     {rule}: {len(concerned)} espaces concernés")

    # Analyse via formulaire interactif
    logger.section_header("ANALYSE RÈGLES DE SÉCURITÉ - ZONE 4 (FORMULAIRE)")

    violations_by_rule = {}

    checker = PLAN001005FormulaireChecker()
    all_violations = checker.analyze(
        extracted_data['spaces'], extracted_data['equipment'],
        extracted_data['slabs'], plancher_types
    )

    # Répartir les violations par règle
    for v in all_violations:
        rule_id = v['rule_id']
        if rule_id not in violations_by_rule:
            violations_by_rule[rule_id] = []
        violations_by_rule[rule_id].append(v)

    # Ajouter les règles vides pour le rapport
    for rule in ['PLAN-001', 'PLAN-002', 'PLAN-003', 'PLAN-004', 'PLAN-005']:
        if rule not in violations_by_rule:
            violations_by_rule[rule] = []

    # Génération rapports
    logger.section_header("GÉNÉRATION RAPPORTS - ZONE 4")
    ifc_name = "Catégorie 4 - Planchers Techniques"
    generator = AnnotationGenerator()
    generator.compile_results(violations_by_rule, ifc_name, extracted_data['summary'])

    output_path = Path(output_dir)
    if format_choice in ['json', 'both']:
        generator.save_json(str(output_path / 'analysis_results.json'))
    if format_choice in ['excel', 'both']:
        generator.save_excel(str(output_path / 'analysis_results.xlsx'))

    generator.print_summary()

    return violations_by_rule


@click.command()
@click.option('--zone', type=click.Choice(['1', '2', '3', '4', '5', 'all']), default='1',
              help='Catégorie à analyser (1=Locaux Élec, 2=Gaines Tech, 3=Faux Plafonds, 4=Planchers Tech, 5=Risques Chantier, all=toutes)')
@click.option('--ifc', type=click.Path(exists=True),
              help='Chemin vers fichier IFC unique (si pas de séparation archi/elec)')
@click.option('--ifc-archi', type=click.Path(exists=True),
              help='Chemin vers fichier IFC Architecture (pièces, portes, dalles)')
@click.option('--ifc-elec', type=click.Path(exists=True),
              help='Chemin vers fichier IFC Électrique (équipements)')
@click.option('--input', 'input_json', type=click.Path(exists=True),
              help='JSON pré-extrait (mode Revit Plugin, remplace --ifc)')
@click.option('--output', default=None,
              help='Dossier de sortie (défaut: resultats/categorieN/)')
@click.option('--rules', multiple=True,
              help='Règles spécifiques à analyser (ex: ELEC-001 GAINE-002)')
@click.option('--format', 'format_choice', type=click.Choice(['json', 'excel', 'both']), default='both',
              help='Format de sortie')
@click.option('--verbose', is_flag=True,
              help='Mode verbeux (logs DEBUG)')
@click.option('--extract-only', is_flag=True,
              help="Extraction uniquement (pas d'analyse)")
def main(zone, ifc, ifc_archi, ifc_elec, input_json, output, rules, format_choice, verbose, extract_only):
    """
    Système Multi-Zones d'Analyse de Conformité Sécurité

    Extrait données IFC, identifie types d'espaces, applique règles de sécurité,
    et génère rapports d'annotations.
    """

    # Configuration logger
    if verbose:
        logger.logger.setLevel('DEBUG')

    # Banner
    print_banner()

    try:
        # Vérifier qu'au moins une source de données est fournie
        if not input_json and not ifc and not (ifc_archi and ifc_elec):
            logger.error("  Vous devez fournir soit --input, soit --ifc, soit --ifc-archi ET --ifc-elec")
            sys.exit(1)

        # Déterminer zones à analyser
        zones_to_run = []

        if zone == 'all':
            zones_to_run = [1, 2, 3, 4, 5]
        else:
            zones_to_run = [int(zone)]

        logger.info(f" Zones à analyser: {', '.join(str(z) for z in zones_to_run)}")

        # === PHASE 1: EXTRACTION ===
        logger.section_header("PHASE 1: EXTRACTION DONNÉES")

        if input_json:
            # Mode Revit Plugin : données pré-extraites en JSON
            extracted_data = _load_extracted_json(input_json)
        else:
            from shared.ifc_extractor import IFCExtractor
            if ifc:
                logger.info("  Mode: Fichier IFC unique")
                extractor = IFCExtractor(ifc)
            else:
                logger.info("  Mode: 2 fichiers IFC (Architecture + Électrique)")
                extractor = IFCExtractor(ifc_archi, ifc_elec)

            extracted_data = extractor.extract_all()

        if not extracted_data:
            logger.error("  Échec extraction données")
            sys.exit(1)

        # Si extraction seulement
        if extract_only:
            logger.info("  Extraction terminée (--extract-only activé)")
            return

        # === PHASE 2+: ANALYSE PAR ZONE ===
        for zone_num in zones_to_run:
            # Déterminer dossier de sortie
            if output:
                output_dir = output
            else:
                output_dir = f"resultats/categorie{zone_num}"

            if zone_num == 1:
                run_zone1(extracted_data, output_dir, list(rules), format_choice)
            elif zone_num == 2:
                run_zone2(extracted_data, output_dir, list(rules), format_choice)
            elif zone_num == 3:
                run_zone3(extracted_data, output_dir, list(rules), format_choice)
            elif zone_num == 4:
                run_zone4(extracted_data, output_dir, list(rules), format_choice)
            elif zone_num == 5:
                run_zone5(extracted_data, output_dir, list(rules), format_choice)

        logger.info("  ANALYSE TERMINÉE AVEC SUCCÈS")

    except Exception as e:
        logger.error(f"  ERREUR CRITIQUE: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


def print_banner():
    """Affiche banner du programme"""
    banner = """
    ==================================================================
    |                                                                |
    |  SYSTÈME MULTI-ZONES D'ANALYSE DE CONFORMITÉ SÉCURITÉ         |
    |                                                                |
    |  Projet: CHU IBN SINA                                          |
    |  Version: 3.0 (multi-zones)                                    |
    |                                                                |
    |  Catégorie 1: Locaux Électriques    (ELEC-001 à ELEC-004)     |
    |  Catégorie 2: Gaines Techniques    (GAINE-001 à GAINE-005)    |
    |  Catégorie 3: Faux Plafonds Tech.  (FPLAF-001 à FPLAF-003)   |
    |  Catégorie 4: Planchers Techniques (PLAN-001 à PLAN-005)      |
    |  Catégorie 5: Risques Chantier     (CHANT-001 à CHANT-005)    |
    |                                                                |
    ==================================================================
    """
    print(banner)
    
    


if __name__ == "__main__":
    main()
