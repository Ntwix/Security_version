using System;
using System.IO;
using System.Windows.Forms;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using CHU_SecurityAnalyzer.Core;

namespace CHU_SecurityAnalyzer.Commands
{
    /// <summary>
    /// Commande principale : Extraction BIM + Analyse Python + Affichage résultats.
    /// Accessible via le bouton dans le ruban Revit.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    public class ExtractAndAnalyzeCommand : IExternalCommand
    {
        // Chemin vers le projet Python (à configurer)
        private static readonly string PROJECT_DIR = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            @"CHU_Ibn Sina\4-CODE\zone1_locaux_electriques_v2\zone1_locaux_electriques"
        );

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIApplication uiApp = commandData.Application;
            UIDocument uiDoc = uiApp.ActiveUIDocument;
            Document doc = uiDoc.Document;

            try
            {
                // === Étape 1 : Sélection de la zone ===
                string zone = ShowZoneSelectionDialog();
                if (zone == null) return Result.Cancelled;

                // === Étape 2 : Détecter ARCHI et ELEC (peu importe lequel est hôte) ===
                Document docArchi = null;
                Document docElec = null;
                string statusMsg;

                DetectArchiAndElec(doc, out docArchi, out docElec, out statusMsg);

                // === Étape 3 : Extraction BIM ===
                TaskDialog.Show("Extraction en cours",
                    $"{statusMsg}\n\nExtraction des données BIM en cours...\nZone sélectionnée: {zone}");

                var extractor = new BIMDataExtractor(docArchi, docElec);
                ExtractedData data = extractor.ExtractAll();

                // === Étape 4 : Export JSON ===
                string pythonExe = PythonBridge.FindPythonExe(PROJECT_DIR);
                if (pythonExe == null)
                {
                    TaskDialog.Show("Erreur", "Python introuvable.\n\n" +
                        "Vérifiez que Python est installé et accessible.\n" +
                        $"Projet: {PROJECT_DIR}");
                    return Result.Failed;
                }

                var bridge = new PythonBridge(pythonExe, PROJECT_DIR);
                string jsonPath = bridge.ExportDataToJson(data);

                // === Étape 5 : Lancer analyse Python ===
                string resultPath = bridge.RunAnalysis(zone, jsonPath);

                // === Étape 6 : Lire résultats ===
                AnalysisResults results = bridge.ReadResults(resultPath);

                // === Étape 7 : Appliquer coloration dans Revit ===
                int coloredCount = 0;
                using (Transaction tx = new Transaction(doc, "CHU Security - Coloration violations"))
                {
                    tx.Start();
                    coloredCount = ApplyViolationColors(doc, uiDoc.ActiveView, results, data);
                    tx.Commit();
                }

                // === Étape 8 : Afficher résumé ===
                int total = results.Metadata?.Statistics?.TotalViolations ?? results.Violations.Count;
                int critical = results.Metadata?.Statistics?.Critical ?? 0;

                string summary = $"ANALYSE TERMINÉE - Zone {zone}\n\n" +
                    $"Données extraites:\n" +
                    $"  - Pièces: {data.Summary.Spaces}\n" +
                    $"  - Équipements: {data.Summary.Equipment}\n" +
                    $"  - Portes: {data.Summary.Doors}\n" +
                    $"  - Dalles: {data.Summary.Slabs}\n\n" +
                    $"Résultats:\n" +
                    $"  - Total violations: {total}\n" +
                    $"  - Critiques: {critical}\n" +
                    $"  - Éléments colorés: {coloredCount}\n\n" +
                    $"Rapport: {resultPath}";

                TaskDialog.Show("CHU Security Analyzer", summary);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                message = ex.Message;
                TaskDialog.Show("Erreur", $"Erreur lors de l'analyse:\n\n{ex.Message}");
                return Result.Failed;
            }
        }

        /// <summary>
        /// Dialogue de sélection de zone
        /// </summary>
        private string ShowZoneSelectionDialog()
        {
            using (var form = new System.Windows.Forms.Form())
            {
                form.Text = "CHU Security Analyzer - Sélection Zone";
                form.Size = new System.Drawing.Size(400, 320);
                form.StartPosition = FormStartPosition.CenterScreen;
                form.FormBorderStyle = FormBorderStyle.FixedDialog;
                form.MaximizeBox = false;
                form.MinimizeBox = false;

                var label = new Label
                {
                    Text = "Sélectionnez la zone d'analyse :",
                    Location = new System.Drawing.Point(20, 20),
                    Size = new System.Drawing.Size(350, 25),
                    Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold)
                };

                var radioButtons = new RadioButton[]
                {
                    new RadioButton { Text = "Zone 1 - Locaux Électriques (ELEC-001 à 004)", Location = new System.Drawing.Point(30, 55), Size = new System.Drawing.Size(330, 25), Checked = true },
                    new RadioButton { Text = "Zone 2 - Gaines Techniques (GAINE-001 à 005)", Location = new System.Drawing.Point(30, 85), Size = new System.Drawing.Size(330, 25) },
                    new RadioButton { Text = "Zone 3 - Faux Plafonds Tech. (FPLAF-001 à 003)", Location = new System.Drawing.Point(30, 115), Size = new System.Drawing.Size(330, 25) },
                    new RadioButton { Text = "Zone 4 - Planchers Techniques (PLAN-001 à 005)", Location = new System.Drawing.Point(30, 145), Size = new System.Drawing.Size(330, 25) },
                    new RadioButton { Text = "Toutes les zones", Location = new System.Drawing.Point(30, 175), Size = new System.Drawing.Size(330, 25) }
                };

                var btnOk = new Button
                {
                    Text = "Analyser",
                    DialogResult = DialogResult.OK,
                    Location = new System.Drawing.Point(170, 220),
                    Size = new System.Drawing.Size(90, 35),
                    Font = new System.Drawing.Font("Segoe UI", 9, System.Drawing.FontStyle.Bold)
                };

                var btnCancel = new Button
                {
                    Text = "Annuler",
                    DialogResult = DialogResult.Cancel,
                    Location = new System.Drawing.Point(270, 220),
                    Size = new System.Drawing.Size(90, 35)
                };

                form.Controls.Add(label);
                foreach (var rb in radioButtons) form.Controls.Add(rb);
                form.Controls.Add(btnOk);
                form.Controls.Add(btnCancel);
                form.AcceptButton = btnOk;
                form.CancelButton = btnCancel;

                if (form.ShowDialog() == DialogResult.OK)
                {
                    for (int i = 0; i < radioButtons.Length; i++)
                    {
                        if (radioButtons[i].Checked)
                        {
                            return i < 4 ? (i + 1).ToString() : "all";
                        }
                    }
                }

                return null;
            }
        }

        /// <summary>
        /// Détecte automatiquement quelle maquette est ARCHI et laquelle est ELEC.
        /// Fonctionne dans les 2 sens :
        ///   - ARCHI hôte + ELEC en lien
        ///   - ELEC hôte + ARCHI en lien (votre configuration actuelle)
        /// </summary>
        private void DetectArchiAndElec(Document hostDoc, out Document docArchi, out Document docElec, out string statusMsg)
        {
            docArchi = null;
            docElec = null;
            string hostTitle = hostDoc.Title.ToLower();

            // Mots-clés pour identifier les maquettes
            bool hostIsElec = hostTitle.Contains("ele") || hostTitle.Contains("ceg") ||
                              hostTitle.Contains("cfo") || hostTitle.Contains("cfa") ||
                              hostTitle.Contains("elec");
            bool hostIsArchi = hostTitle.Contains("arc") || hostTitle.Contains("archi");

            // Chercher dans les liens
            Document linkedArchi = null;
            Document linkedElec = null;

            var collector = new FilteredElementCollector(hostDoc)
                .OfClass(typeof(RevitLinkInstance));

            foreach (RevitLinkInstance link in collector)
            {
                Document linkDoc = link.GetLinkDocument();
                if (linkDoc == null) continue;

                string linkTitle = linkDoc.Title.ToLower();

                if (linkedArchi == null && (linkTitle.Contains("arc") || linkTitle.Contains("archi")))
                    linkedArchi = linkDoc;

                if (linkedElec == null && (linkTitle.Contains("ele") || linkTitle.Contains("ceg") ||
                    linkTitle.Contains("cfo") || linkTitle.Contains("cfa") || linkTitle.Contains("elec")))
                    linkedElec = linkDoc;
            }

            // Cas 1 : ELEC hôte + ARCHI en lien (votre cas)
            if (hostIsElec && linkedArchi != null)
            {
                docArchi = linkedArchi;
                docElec = hostDoc;
                statusMsg = $"Configuration détectée: ELEC hôte + ARCHI en lien\n" +
                           $"  ARCHI (lien): {linkedArchi.Title}\n" +
                           $"  ELEC (hôte): {hostDoc.Title}";
                return;
            }

            // Cas 2 : ARCHI hôte + ELEC en lien
            if ((hostIsArchi || !hostIsElec) && linkedElec != null)
            {
                docArchi = hostDoc;
                docElec = linkedElec;
                statusMsg = $"Configuration détectée: ARCHI hôte + ELEC en lien\n" +
                           $"  ARCHI (hôte): {hostDoc.Title}\n" +
                           $"  ELEC (lien): {linkedElec.Title}";
                return;
            }

            // Cas 3 : Maquette unique (pas de lien correspondant)
            docArchi = hostDoc;
            docElec = null;
            statusMsg = $"Maquette unique: {hostDoc.Title}\n(Pas de lien ARCHI/ELEC détecté)";
        }

        /// <summary>
        /// Applique la coloration des éléments en violation dans la vue active
        /// </summary>
        private int ApplyViolationColors(Document doc, Autodesk.Revit.DB.View view, AnalysisResults results, ExtractedData data)
        {
            int count = 0;

            // Créer les override graphics par sévérité
            var overrideCritique = new OverrideGraphicSettings();
            overrideCritique.SetSurfaceForegroundPatternColor(new Color(255, 0, 0)); // Rouge
            overrideCritique.SetSurfaceForegroundPatternVisible(true);

            var overrideHaute = new OverrideGraphicSettings();
            overrideHaute.SetSurfaceForegroundPatternColor(new Color(255, 140, 0)); // Orange

            var overrideMoyenne = new OverrideGraphicSettings();
            overrideMoyenne.SetSurfaceForegroundPatternColor(new Color(255, 255, 0)); // Jaune

            // Trouver un FillPatternElement solide
            FillPatternElement solidPattern = GetSolidFillPattern(doc);
            if (solidPattern != null)
            {
                overrideCritique.SetSurfaceForegroundPatternId(solidPattern.Id);
                overrideHaute.SetSurfaceForegroundPatternId(solidPattern.Id);
                overrideMoyenne.SetSurfaceForegroundPatternId(solidPattern.Id);
            }

            foreach (var violation in results.Violations)
            {
                // Trouver l'ElementId correspondant au space_name
                ElementId elemId = FindElementByName(data, violation.SpaceName);
                if (elemId == null || elemId == ElementId.InvalidElementId) continue;

                // Appliquer la couleur selon sévérité
                OverrideGraphicSettings overrideToApply;
                switch (violation.Severity?.ToUpper())
                {
                    case "CRITIQUE":
                        overrideToApply = overrideCritique;
                        break;
                    case "HAUTE":
                        overrideToApply = overrideHaute;
                        break;
                    default:
                        overrideToApply = overrideMoyenne;
                        break;
                }

                try
                {
                    view.SetElementOverrides(elemId, overrideToApply);
                    count++;
                }
                catch { }
            }

            return count;
        }

        private ElementId FindElementByName(ExtractedData data, string spaceName)
        {
            foreach (var space in data.Spaces)
            {
                if (space.Name == spaceName && space.RevitElementId > 0)
                    return new ElementId(space.RevitElementId);
            }
            return ElementId.InvalidElementId;
        }

        private FillPatternElement GetSolidFillPattern(Document doc)
        {
            var collector = new FilteredElementCollector(doc)
                .OfClass(typeof(FillPatternElement));

            foreach (FillPatternElement fpe in collector)
            {
                FillPattern fp = fpe.GetFillPattern();
                if (fp != null && fp.IsSolidFill)
                    return fpe;
            }
            return null;
        }
    }
}
