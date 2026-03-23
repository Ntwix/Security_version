"""
============================================================================
PDF Generator - Plan d'Identification et d'Évaluation des Risques
Catégorie 5 - Risques Chantier
============================================================================
Génère un PDF professionnel à partir des violations JSON CHANT-001 à CHANT-005.
Structure :
  - Page 1 : Tableau des violations par espace + légende visuelle
  - Page 2 : Fiches détaillées par règle avec recommandations
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─── Couleurs ────────────────────────────────────────────────────────────────
ROUGE     = colors.HexColor("#C0392B")
ORANGE    = colors.HexColor("#E67E22")
JAUNE     = colors.HexColor("#F1C40F")
VERT      = colors.HexColor("#27AE60")
BLEU_FOND = colors.HexColor("#1A3A5C")
GRIS_FOND = colors.HexColor("#F2F3F4")
GRIS_BORD = colors.HexColor("#BDC3C7")
BLANC     = colors.white
NOIR      = colors.HexColor("#2C3E50")

# ─── Sévérité → couleur + label ──────────────────────────────────────────────
SEVERITY_CONFIG = {
    "CRITIQUE": {"color": ROUGE,  "label": "CRITIQUE", "icon": "●"},
    "HAUTE":    {"color": ORANGE, "label": "HAUTE",    "icon": "▲"},
    "MOYENNE":  {"color": JAUNE,  "label": "MOYENNE",  "icon": "■"},
    "FAIBLE":   {"color": VERT,   "label": "FAIBLE",   "icon": "◆"},
}

# ─── Description des règles CHANT ─────────────────────────────────────────────
RULES_INFO = {
    "CHANT-001": {
        "name": "Manutention des équipements lourds",
        "domaine": "Risque hors lot électrique",
        "description": (
            "Lors de l'installation d'équipements électriques lourds (tableaux, armoires, TGBT...), "
            "le chemin d'accès doit permettre le passage. Toute porte ou couloir insuffisant "
            "représente un risque de blessure et d'endommagement du matériel."
        ),
        "recommandation": (
            "• Tout tourret de câble doit être posé sur un support de déroulage.\n"
            "• Charge les mâts en tronçons pour faciliter la manutention.\n"
            "• Vérifier les largeurs de portes avant livraison du matériel."
        ),
        "color": ORANGE,
        "icon": "■",
    },
    "CHANT-002": {
        "name": "Accessibilité locaux techniques",
        "domaine": "Risque électrique",
        "description": (
            "Aucune personne non habilitée ne doit accéder aux locaux techniques électriques. "
            "L'accès est réservé au personnel habilité H1/H2/HC conformément à la norme NF C 18-510."
        ),
        "recommandation": (
            "• Habilitation H1/H2/HC obligatoire.\n"
            "• Consignation obligatoire avant toute intervention.\n"
            "• Afficher les panneaux d'avertissement électrique à chaque accès."
        ),
        "color": ROUGE,
        "icon": "●",
    },
    "CHANT-003": {
        "name": "Travail en hauteur",
        "domaine": "Risque hors lot électrique",
        "description": (
            "L'installation d'équipements en hauteur expose les ouvriers à un risque de chute. "
            "Selon la hauteur : < 2m OK, 2–3m escabeau, 3–4.5m PIR/PIRL, "
            "4.5–6m échafaudage roulant, 6–20m échafaudage fixe, ≥ 20m nacelle PEMP."
        ),
        "recommandation": (
            "• Formation obligatoire aux travaux en hauteur et antichute.\n"
            "• Charge les mâts en tronçons pour faciliter la manutention.\n"
            "• Vérifier la stabilité du sol et dégager la zone de travail."
        ),
        "color": ORANGE,
        "icon": "▲",
    },
    "CHANT-004": {
        "name": "Gaine ascenseur",
        "domaine": "Risque hors lot électrique",
        "description": (
            "Avant installation de l'ascenseur, la gaine est vide et représente un risque "
            "de chute critique pour les intervenants. Zone de travail confinée et dangereuse."
        ),
        "recommandation": (
            "• Jamais travailler seul dans la gaine ascenseur.\n"
            "• Balisage obligatoire de la zone.\n"
            "• Obligation de faire le mode opératoire zone confinée."
        ),
        "color": ROUGE,
        "icon": "●",
    },
    "CHANT-005": {
        "name": "Ventilation des locaux techniques",
        "domaine": "Risque électrique",
        "description": (
            "Les locaux techniques sans ventilation présentent un risque d'accumulation de chaleur "
            "et de gaz pouvant endommager les équipements et mettre en danger le personnel."
        ),
        "recommandation": (
            "• Installer un système de ventilation avant mise en service.\n"
            "• Vérifier le renouvellement d'air minimum selon la surface du local.\n"
            "• EPI respiratoire obligatoire lors des interventions en local non ventilé."
        ),
        "color": JAUNE,
        "icon": "■",
    },
}


def load_violations(json_path: str) -> List[Dict]:
    """Charge les violations depuis le fichier JSON résultat."""
    path = Path(json_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    violations = []
    # Supporte les formats : liste directe, ou dict avec clé "violations"
    if isinstance(data, list):
        violations = data
    elif isinstance(data, dict):
        for key in ["violations", "results", "CHANT-001", "CHANT-002",
                    "CHANT-003", "CHANT-004", "CHANT-005"]:
            if key in data:
                v = data[key]
                if isinstance(v, list):
                    violations.extend(v)
    return violations


def _severity_color(severity: str) -> colors.Color:
    return SEVERITY_CONFIG.get(severity, {}).get("color", GRIS_BORD)


def _severity_icon(severity: str) -> str:
    return SEVERITY_CONFIG.get(severity, {}).get("icon", "?")


def generate_pdf(json_path: str, output_path: str, project_name: str = "CHU Ibn Sina"):
    """
    Génère le PDF Plan d'Identification et d'Évaluation des Risques.

    Args:
        json_path: Chemin vers le JSON résultat categorie5
        output_path: Chemin de sortie du PDF
        project_name: Nom du projet
    """
    violations = load_violations(json_path)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Styles personnalisés ──────────────────────────────────────────────────
    style_titre = ParagraphStyle(
        "titre", fontSize=16, textColor=BLANC, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=2
    )
    style_sous_titre = ParagraphStyle(
        "sous_titre", fontSize=9, textColor=BLANC, alignment=TA_CENTER,
        fontName="Helvetica", spaceAfter=0
    )
    style_section = ParagraphStyle(
        "section", fontSize=11, textColor=BLANC, alignment=TA_LEFT,
        fontName="Helvetica-Bold", leftIndent=6
    )
    style_body = ParagraphStyle(
        "body", fontSize=8, textColor=NOIR, fontName="Helvetica",
        leading=12, spaceAfter=2
    )
    style_small = ParagraphStyle(
        "small", fontSize=7, textColor=NOIR, fontName="Helvetica", leading=10
    )
    style_bold = ParagraphStyle(
        "bold", fontSize=8, textColor=NOIR, fontName="Helvetica-Bold", leading=11
    )

    # ── EN-TÊTE ───────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"Plan d'Identification et d'Évaluation des Risques", style_titre),
    ]]
    header_sub = [[
        Paragraph(
            f"{project_name}  |  Catégorie 5 — Risques Chantier  |  "
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            style_sous_titre
        ),
    ]]

    t_header = Table(header_data, colWidths=[18*cm])
    t_header.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLEU_FOND),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("ROUNDEDCORNERS", [6]),
    ]))
    t_sub = Table(header_sub, colWidths=[18*cm])
    t_sub.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU_FOND),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))

    story.append(t_header)
    story.append(t_sub)
    story.append(Spacer(1, 0.4*cm))

    # ── STATISTIQUES ─────────────────────────────────────────────────────────
    counts = {"CRITIQUE": 0, "HAUTE": 0, "MOYENNE": 0, "FAIBLE": 0}
    for v in violations:
        sev = v.get("severity", "FAIBLE")
        counts[sev] = counts.get(sev, 0) + 1

    stats_data = [
        [
            Paragraph("Total violations", style_bold),
            Paragraph(f"<font color='#C0392B'><b>CRITIQUE</b></font>", style_bold),
            Paragraph(f"<font color='#E67E22'><b>HAUTE</b></font>", style_bold),
            Paragraph(f"<font color='#B7950B'><b>MOYENNE</b></font>", style_bold),
        ],
        [
            Paragraph(f"<b>{len(violations)}</b>", ParagraphStyle("v", fontSize=20,
                fontName="Helvetica-Bold", textColor=BLEU_FOND, alignment=TA_CENTER)),
            Paragraph(f"<b>{counts['CRITIQUE']}</b>", ParagraphStyle("v2", fontSize=20,
                fontName="Helvetica-Bold", textColor=ROUGE, alignment=TA_CENTER)),
            Paragraph(f"<b>{counts['HAUTE']}</b>", ParagraphStyle("v3", fontSize=20,
                fontName="Helvetica-Bold", textColor=ORANGE, alignment=TA_CENTER)),
            Paragraph(f"<b>{counts['MOYENNE']}</b>", ParagraphStyle("v4", fontSize=20,
                fontName="Helvetica-Bold", textColor=colors.HexColor("#B7950B"), alignment=TA_CENTER)),
        ],
    ]
    t_stats = Table(stats_data, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    t_stats.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GRIS_FOND),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("GRID",          (0,0), (-1,-1), 0.5, GRIS_BORD),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(t_stats)
    story.append(Spacer(1, 0.4*cm))

    # ── TABLEAU DES VIOLATIONS ────────────────────────────────────────────────
    section_violations = Table(
        [[Paragraph("  LISTE DES VIOLATIONS DÉTECTÉES", style_section)]],
        colWidths=[18*cm]
    )
    section_violations.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU_FOND),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(section_violations)
    story.append(Spacer(1, 0.2*cm))

    if violations:
        # En-tête tableau
        viol_header = [
            Paragraph("<b>Règle</b>", style_bold),
            Paragraph("<b>Sévérité</b>", style_bold),
            Paragraph("<b>Espace / Équipement</b>", style_bold),
            Paragraph("<b>Description</b>", style_bold),
        ]
        viol_rows = [viol_header]

        for v in violations:
            rule_id  = v.get("rule_id", "")
            severity = v.get("severity", "FAIBLE")
            space    = v.get("space_name", "—")
            desc     = v.get("description", "—")
            sev_color = _severity_color(severity)
            sev_icon  = _severity_icon(severity)

            viol_rows.append([
                Paragraph(f"<b>{rule_id}</b>", style_small),
                Paragraph(
                    f'<font color="{sev_color.hexval() if hasattr(sev_color, "hexval") else "#000000"}">'
                    f'<b>{sev_icon} {severity}</b></font>',
                    style_small
                ),
                Paragraph(space[:60] + ("..." if len(space) > 60 else ""), style_small),
                Paragraph(desc[:120] + ("..." if len(desc) > 120 else ""), style_small),
            ])

        t_viol = Table(viol_rows, colWidths=[2.5*cm, 2.5*cm, 5*cm, 8*cm])
        style_viol = TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#2E4057")),
            ("TEXTCOLOR",     (0,0), (-1,0), BLANC),
            ("ALIGN",         (0,0), (-1,-1), "LEFT"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("GRID",          (0,0), (-1,-1), 0.3, GRIS_BORD),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [BLANC, GRIS_FOND]),
        ])
        t_viol.setStyle(style_viol)
        story.append(t_viol)
    else:
        story.append(Paragraph("Aucune violation détectée.", style_body))

    story.append(Spacer(1, 0.5*cm))

    # ── LÉGENDE ───────────────────────────────────────────────────────────────
    section_legende = Table(
        [[Paragraph("  LÉGENDE — TYPES DE RISQUES", style_section)]],
        colWidths=[18*cm]
    )
    section_legende.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLEU_FOND),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(section_legende)
    story.append(Spacer(1, 0.2*cm))

    # En-tête colonnes
    s_lh = ParagraphStyle("lh",  fontSize=9, fontName="Helvetica-Bold",
                          textColor=ROUGE,  alignment=TA_CENTER)
    s_lh2 = ParagraphStyle("lh2", fontSize=9, fontName="Helvetica-Bold",
                           textColor=ORANGE, alignment=TA_CENTER)
    s_rname = ParagraphStyle("rname", fontSize=8, textColor=BLEU_FOND,
                             fontName="Helvetica-Bold", leading=11)
    s_rdesc = ParagraphStyle("rdesc", fontSize=7, textColor=NOIR,
                             fontName="Helvetica", leading=10, spaceAfter=2)
    s_rreco = ParagraphStyle("rreco", fontSize=7, textColor=colors.HexColor("#555555"),
                             fontName="Helvetica-Oblique", leading=10)

    def leg_cell(rule_id: str) -> Paragraph:
        info = RULES_INFO.get(rule_id, {})
        c    = info.get("color", GRIS_BORD)
        # Convertir couleur en hex string
        if hasattr(c, 'hexval'):
            hex_c = c.hexval()
        else:
            hex_c = "#888888"
        icon = info.get("icon", "?")
        name = info.get("name", rule_id)
        desc = info.get("description", "").replace("\n", "<br/>")
        reco = info.get("recommandation", "").replace("\n", "<br/>")
        text = (
            f'<font color="{hex_c}" size="13"><b>{icon}</b></font>  '
            f'<font color="#1A3A5C"><b>{rule_id} — {name}</b></font><br/>'
            f'<font size="7">{desc}</font><br/>'
            f'<font size="7" color="#555555"><i>{reco}</i></font>'
        )
        return Paragraph(text, ParagraphStyle(
            f"lc_{rule_id}", fontSize=7, fontName="Helvetica",
            leading=11, spaceAfter=4
        ))

    elec_rules = ["CHANT-002", "CHANT-005"]
    hors_rules = ["CHANT-001", "CHANT-003", "CHANT-004"]

    leg_rows = [[
        Paragraph("<b>Type de risque électrique</b>", s_lh),
        Paragraph("<b>Type de risque hors lot électrique</b>", s_lh2),
    ]]
    max_rows = max(len(elec_rules), len(hors_rules))
    for i in range(max_rows):
        left  = leg_cell(elec_rules[i]) if i < len(elec_rules) else Paragraph("", style_small)
        right = leg_cell(hors_rules[i]) if i < len(hors_rules) else Paragraph("", style_small)
        leg_rows.append([left, right])

    t_leg = Table(leg_rows, colWidths=[9*cm, 9*cm])
    t_leg.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), GRIS_FOND),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("GRID",          (0,0), (-1,-1), 0.5, GRIS_BORD),
        ("LINEBELOW",     (0,0), (-1,0),  1, BLEU_FOND),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [BLANC, GRIS_FOND]),
    ]))
    story.append(t_leg)

    story.append(Spacer(1, 0.4*cm))

    # ── PIED DE PAGE ─────────────────────────────────────────────────────────
    footer_data = [[
        Paragraph(
            f"Document généré automatiquement par CHU BIM Security Analyzer  |  "
            f"Stage 2026 — {project_name}  |  Confidentiel",
            ParagraphStyle("footer", fontSize=7, textColor=colors.HexColor("#7F8C8D"),
                           alignment=TA_CENTER, fontName="Helvetica-Oblique")
        )
    ]]
    t_footer = Table(footer_data, colWidths=[18*cm])
    t_footer.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("LINEABOVE",     (0,0), (-1,0),  0.5, GRIS_BORD),
    ]))
    story.append(t_footer)

    # ── GÉNÉRATION ────────────────────────────────────────────────────────────
    doc.build(story)
    print(f"PDF généré : {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pdf_generator.py <violations.json> <output.pdf>")
        sys.exit(1)
    generate_pdf(sys.argv[1], sys.argv[2])
