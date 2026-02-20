using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Structure;
using Autodesk.Revit.UI;
using CHU_SecurityAnalyzer.Core;
using Color = Autodesk.Revit.DB.Color;

namespace CHU_SecurityAnalyzer.Commands
{
    [Transaction(TransactionMode.Manual)]
    public class ExtractAndAnalyzeCommand : IExternalCommand
    {
        private static readonly string PROJECT_DIR = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            @"CHU_Ibn Sina\4-CODE\zone1_locaux_electriques_v2\zone1_locaux_electriques"
        );

        private const string VIEW_PREFIX = "ZONES RISQUES - ";
        private const string RISK_FAMILY_RFA = "Famille_TEST.rfa";
        private const string RISK_FAMILY_NAME = "Famille_TEST";

        private class VisualizationResult
        {
            public int ColoredTotal;
            public int AnnotationTotal;
            public int ViewCount;
            public ViewPlan FirstView;
        }

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIApplication uiApp = commandData.Application;
            UIDocument uiDoc = uiApp.ActiveUIDocument;
            Document doc = uiDoc.Document;

            try
            {
                // === Etape 1 : Selection de la zone ===
                string zone = ShowZoneSelectionDialog();
                if (zone == null) return Result.Cancelled;

                // === Etape 2 : Detecter ARCHI et ELEC ===
                Document docArchi = null;
                Document docElec = null;
                string statusMsg;

                DetectArchiAndElec(doc, out docArchi, out docElec, out statusMsg);

                // === Etape 3 : Extraction BIM ===
                TaskDialog.Show("Extraction en cours",
                    $"{statusMsg}\n\nExtraction des donnees BIM en cours...\nZone selectionnee: {zone}");

                var extractor = new BIMDataExtractor(docArchi, docElec);
                ExtractedData data = extractor.ExtractAll();

                // === Etape 4 : Export JSON ===
                string pythonExe = PythonBridge.FindPythonExe(PROJECT_DIR);
                if (pythonExe == null)
                {
                    TaskDialog.Show("Erreur", "Python introuvable.\n\n" +
                        "Verifiez que Python est installe et accessible.\n" +
                        $"Projet: {PROJECT_DIR}");
                    return Result.Failed;
                }

                var bridge = new PythonBridge(pythonExe, PROJECT_DIR);
                string jsonPath = bridge.ExportDataToJson(data);

                // === Etape 5 : Lancer analyse Python ===
                string resultPath = bridge.RunAnalysis(zone, jsonPath);

                // === Etape 6 : Lire resultats ===
                AnalysisResults results = bridge.ReadResults(resultPath);

                // === Etape 7 : Dupliquer vues + appliquer coloration et symboles ===
                var vizResult = ApplyVisualizationsToAllViews(doc, uiDoc, results, data);

                // === Etape 8 : Naviguer vers la vue risques + afficher resume ===
                if (vizResult.FirstView != null)
                {
                    try { uiDoc.ActiveView = vizResult.FirstView; }
                    catch { }
                }

                ShowResultsSummary(zone, data, results,
                    vizResult.ColoredTotal, vizResult.AnnotationTotal,
                    vizResult.ViewCount, resultPath);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                message = ex.Message;
                TaskDialog.Show("CHU Security Analyzer - Erreur",
                    $"Erreur lors de l'analyse:\n\n{ex.Message}\n\n{ex.StackTrace}");
                return Result.Failed;
            }
        }

        // =====================================================================
        //  ORCHESTRATION VUES DUPLIQUEES "ZONES RISQUES"
        // =====================================================================

        private VisualizationResult ApplyVisualizationsToAllViews(
            Document doc, UIDocument uiDoc,
            AnalysisResults results, ExtractedData data)
        {
            var result = new VisualizationResult();

            if (results.Violations == null || results.Violations.Count == 0)
                return result;

            // Determiner quels niveaux ont des violations
            HashSet<double> violationLevels = GetLevelsWithViolations(doc, results, data);
            if (violationLevels.Count == 0)
                return result;

            // Collecter les vues en plan eligibles
            List<ViewPlan> eligibleViews = CollectEligibleFloorPlans(doc);
            if (eligibleViews.Count == 0)
                return result;

            int maxAnnotations = 0;

            using (TransactionGroup txGroup = new TransactionGroup(doc, "CHU Security - Zones Risques"))
            {
                txGroup.Start();

                // Sous-transaction : creer les styles de ligne + charger famille (une seule fois)
                // + nettoyer TOUTES les anciennes instances de famille risque dans le projet
                Dictionary<string, GraphicsStyle> lineStyles;
                FamilySymbol riskSymbol = null;
                using (Transaction txStyles = new Transaction(doc, "CHU Security - Styles et famille"))
                {
                    txStyles.Start();
                    lineStyles = GetOrCreateLineStyles(doc);
                    riskSymbol = LoadOrGetRiskFamily(doc);

                    // Supprimer toutes les anciennes instances de famille risque (elements de modele)
                    var oldRiskInstances = new FilteredElementCollector(doc)
                        .OfClass(typeof(FamilyInstance))
                        .Cast<FamilyInstance>()
                        .Where(fi => fi.Symbol.FamilyName == RISK_FAMILY_NAME
                                  || fi.Symbol.FamilyName.Contains("Famille_TEST")
                                  || fi.Symbol.FamilyName.Contains("renamed"))
                        .Select(fi => fi.Id)
                        .ToList();
                    if (oldRiskInstances.Count > 0)
                        doc.Delete(oldRiskInstances);

                    // Placer les familles 3D ELEC-002 une seule fois par espace
                    if (riskSymbol != null)
                    {
                        var levels = new FilteredElementCollector(doc)
                            .OfClass(typeof(Level))
                            .Cast<Level>()
                            .OrderBy(l => l.Elevation)
                            .ToList();

                        var placedSpaces = new HashSet<string>();
                        foreach (var v in results.Violations)
                        {
                            if (v.RuleId != "ELEC-002") continue;
                            // Cle unique par global_id pour eviter les doublons
                            string spaceKey = v.SpaceGlobalId ?? v.SpaceName ?? "";
                            if (string.IsNullOrEmpty(spaceKey) || placedSpaces.Contains(spaceKey)) continue;
                            placedSpaces.Add(spaceKey);

                            double[] loc = FindSpaceLocation(data, v.SpaceName ?? "");
                            if (loc == null || loc.Length < 3) continue;

                            double xFt = loc[0] / 0.3048;
                            double yFt = loc[1] / 0.3048;
                            double zFt = loc[2] / 0.3048;

                            // Trouver le niveau le plus proche
                            Level bestLevel = null;
                            double bestDist = double.MaxValue;
                            foreach (var lvl in levels)
                            {
                                double dist = Math.Abs(lvl.Elevation - zFt);
                                if (dist < bestDist)
                                {
                                    bestDist = dist;
                                    bestLevel = lvl;
                                }
                            }

                            if (bestLevel != null)
                            {
                                // Z = 0 car NewFamilyInstance avec Level place au niveau automatiquement
                                XYZ pt = new XYZ(xFt, yFt, 0);
                                doc.Create.NewFamilyInstance(
                                    pt, riskSymbol, bestLevel,
                                    StructuralType.NonStructural);
                            }
                        }
                    }

                    txStyles.Commit();
                }

                // Pour chaque vue eligible dont le niveau a des violations
                foreach (ViewPlan originalView in eligibleViews)
                {
                    if (originalView.GenLevel == null) continue;
                    double levelElev = originalView.GenLevel.Elevation;

                    // Verifier si ce niveau a des violations
                    if (!violationLevels.Contains(levelElev)) continue;

                    using (Transaction txView = new Transaction(doc,
                        "CHU Security - " + VIEW_PREFIX + originalView.Name))
                    {
                        txView.Start();
                        try
                        {
                            // Dupliquer ou reutiliser la vue
                            ViewPlan riskView = GetOrReuseDuplicatedView(doc, originalView);

                            // Appliquer coloration + symboles sur la vue dupliquee
                            int colored = ApplyViolationColors(doc, riskView, results, data);
                            int annotations = PlaceViolationAnnotations(doc, riskView, results, data, lineStyles, riskSymbol);

                            result.ColoredTotal += colored;
                            result.AnnotationTotal += annotations;
                            result.ViewCount++;

                            // Retenir la vue avec le plus d'annotations
                            if (annotations > maxAnnotations || result.FirstView == null)
                            {
                                maxAnnotations = annotations;
                                result.FirstView = riskView;
                            }

                            txView.Commit();
                        }
                        catch
                        {
                            if (txView.HasStarted() && !txView.HasEnded())
                                txView.RollBack();
                        }
                    }
                }

                txGroup.Assimilate();
            }

            return result;
        }

        // =====================================================================
        //  COLLECTE DES VUES EN PLAN ELIGIBLES
        // =====================================================================

        /// <summary>
        /// Retourne UNE SEULE vue par niveau pour eviter les doublons.
        /// Priorite : vue contenant "Distribution" dans le nom, sinon la premiere trouvee.
        /// </summary>
        private List<ViewPlan> CollectEligibleFloorPlans(Document doc)
        {
            var allViews = new List<ViewPlan>();

            var collector = new FilteredElementCollector(doc)
                .OfClass(typeof(ViewPlan))
                .WhereElementIsNotElementType();

            foreach (ViewPlan vp in collector)
            {
                if (vp.ViewType != ViewType.FloorPlan) continue;
                if (vp.IsTemplate) continue;
                if (vp.Name.StartsWith(VIEW_PREFIX)) continue;
                if (vp.GenLevel == null) continue;
                allViews.Add(vp);
            }

            // Grouper par niveau (Level.Id) et garder une seule vue par niveau
            var byLevel = new Dictionary<int, ViewPlan>();
            foreach (ViewPlan vp in allViews)
            {
                int levelId = vp.GenLevel.Id.IntegerValue;

                if (!byLevel.ContainsKey(levelId))
                {
                    // Premiere vue pour ce niveau
                    byLevel[levelId] = vp;
                }
                else
                {
                    // Preferer une vue "Distribution" (plus complete pour l'analyse)
                    string currentName = byLevel[levelId].Name.ToLower();
                    string newName = vp.Name.ToLower();

                    if (!currentName.Contains("distribution") && newName.Contains("distribution"))
                    {
                        byLevel[levelId] = vp;
                    }
                }
            }

            return byLevel.Values.ToList();
        }

        // =====================================================================
        //  NIVEAUX AVEC VIOLATIONS
        // =====================================================================

        private HashSet<double> GetLevelsWithViolations(
            Document doc, AnalysisResults results, ExtractedData data)
        {
            var levelElevations = new HashSet<double>();

            // Collecter tous les niveaux du document
            var levels = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .Cast<Level>()
                .OrderBy(l => l.Elevation)
                .ToList();

            foreach (var v in results.Violations)
            {
                double[] location = FindSpaceLocation(data, v.SpaceName ?? "");
                if (location == null || location.Length < 3) continue;

                double zFeet = location[2] / 0.3048;

                // Trouver le niveau correspondant (meme plage que PlaceViolationAnnotations)
                foreach (var level in levels)
                {
                    double levelZ = level.Elevation;
                    double zMin = levelZ - 1.0;
                    double zMax = levelZ + 16.4;
                    if (zFeet >= zMin && zFeet <= zMax)
                    {
                        levelElevations.Add(level.Elevation);
                        break;
                    }
                }
            }

            return levelElevations;
        }

        // =====================================================================
        //  DUPLICATION / REUTILISATION DES VUES
        // =====================================================================

        private ViewPlan GetOrReuseDuplicatedView(Document doc, ViewPlan originalView)
        {
            string targetName = VIEW_PREFIX + originalView.Name;

            // Chercher une vue existante avec ce nom
            var existingViews = new FilteredElementCollector(doc)
                .OfClass(typeof(ViewPlan))
                .WhereElementIsNotElementType()
                .Cast<ViewPlan>()
                .Where(v => v.Name == targetName)
                .ToList();

            if (existingViews.Count > 0)
            {
                // Reutiliser : nettoyer les annotations existantes
                ViewPlan existingView = existingViews[0];
                ClearViewAnnotations(doc, existingView);
                return existingView;
            }

            // Dupliquer la vue
            ElementId newViewId = originalView.Duplicate(ViewDuplicateOption.Duplicate);
            ViewPlan newView = doc.GetElement(newViewId) as ViewPlan;

            // Renommer
            try
            {
                newView.Name = targetName;
            }
            catch (Autodesk.Revit.Exceptions.ArgumentException)
            {
                newView.Name = targetName + " (" + DateTime.Now.ToString("HHmmss") + ")";
            }

            // Assigner au sous-projet "ZONES RISQUES" pour regrouper dans le navigateur
            AssignViewSubDiscipline(newView);

            return newView;
        }

        /// <summary>
        /// Modifie les parametres de la vue dupliquee pour la regrouper
        /// sous une section dediee dans le navigateur de projet.
        /// Essaie plusieurs strategies selon la configuration du projet.
        /// </summary>
        private void AssignViewSubDiscipline(ViewPlan view)
        {
            // === Strategie 1 : Sous-discipline (SUB_DISCIPLINE) ===
            // C'est le critere de groupement le plus courant dans les projets BIM francais
            try
            {
                Parameter subDisc = view.get_Parameter(BuiltInParameter.VIEWER_VOLUME_OF_INTEREST_CROP);
                // Essayer le vrai parametre Sous-discipline
                if (subDisc == null || subDisc.IsReadOnly)
                {
                    // Chercher par nom (FR et EN)
                    subDisc = view.LookupParameter("Sous-discipline");
                    if (subDisc == null) subDisc = view.LookupParameter("Sub Discipline");
                    if (subDisc == null) subDisc = view.LookupParameter("Sub-Discipline");
                }
                if (subDisc != null && !subDisc.IsReadOnly && subDisc.StorageType == StorageType.String)
                {
                    subDisc.Set("ZONES RISQUES");
                }
            }
            catch { }

            // === Strategie 2 : Parametre personnalise utilise pour le tri ===
            // Les projets CHU utilisent souvent des parametres de classement
            string[] sortParams = new string[]
            {
                "Classement",          // Parametre courant projets FR
                "Classification",      // Variante
                "Groupe de vues",      // Groupement explicite
                "View Group",          // EN
                "Categorie",           // Autre variante FR
                "Phase de projet",     // Parfois utilise pour le tri
            };

            foreach (string paramName in sortParams)
            {
                try
                {
                    Parameter p = view.LookupParameter(paramName);
                    if (p != null && !p.IsReadOnly && p.StorageType == StorageType.String)
                    {
                        p.Set("ZONES RISQUES");
                        break; // Un seul suffit
                    }
                }
                catch { }
            }

            // === Strategie 3 : VIEW_DESCRIPTION (Titre sur feuille) ===
            // Toujours accessible - sert d'identifiant meme si ne change pas le groupement
            try
            {
                Parameter titleOnSheet = view.get_Parameter(BuiltInParameter.VIEW_DESCRIPTION);
                if (titleOnSheet != null && !titleOnSheet.IsReadOnly)
                    titleOnSheet.Set("ZONES RISQUES");
            }
            catch { }
        }

        // =====================================================================
        //  NETTOYAGE DES VUES EXISTANTES
        // =====================================================================

        private void ClearViewAnnotations(Document doc, ViewPlan view)
        {
            // Supprimer les DetailCurves (symboles dessines)
            var detailCurves = new FilteredElementCollector(doc, view.Id)
                .OfClass(typeof(CurveElement))
                .ToElementIds()
                .ToList();

            if (detailCurves.Count > 0)
                doc.Delete(detailCurves);

            // Supprimer les TextNotes (labels)
            var textNotes = new FilteredElementCollector(doc, view.Id)
                .OfClass(typeof(TextNote))
                .ToElementIds()
                .ToList();

            if (textNotes.Count > 0)
                doc.Delete(textNotes);

            // Supprimer les instances de la famille de risque (dans tout le document,
            // car ce sont des elements de modele, pas des elements de vue)
            var riskInstances = new FilteredElementCollector(doc)
                .OfClass(typeof(FamilyInstance))
                .Cast<FamilyInstance>()
                .Where(fi => fi.Symbol.FamilyName == RISK_FAMILY_NAME
                          || fi.Symbol.FamilyName.Contains("Famille_TEST")
                          || fi.Symbol.FamilyName.Contains("renamed"))
                .Select(fi => fi.Id)
                .ToList();

            if (riskInstances.Count > 0)
                doc.Delete(riskInstances);

            // Reset les overrides graphiques
            var allElements = new FilteredElementCollector(doc, view.Id)
                .WhereElementIsNotElementType()
                .ToElementIds();

            var defaultOverride = new OverrideGraphicSettings();
            foreach (ElementId elemId in allElements)
            {
                try { view.SetElementOverrides(elemId, defaultOverride); }
                catch { }
            }
        }

        // =====================================================================
        //  AFFICHAGE RESUME PAR REGLE
        // =====================================================================

        private void ShowResultsSummary(string zone, ExtractedData data,
            AnalysisResults results, int coloredCount, int annotationCount,
            int viewCount, string resultPath)
        {
            // Compter violations par regle
            var byRule = new Dictionary<string, List<ViolationData>>();
            foreach (var v in results.Violations)
            {
                string ruleId = v.RuleId ?? "INCONNU";
                if (!byRule.ContainsKey(ruleId))
                    byRule[ruleId] = new List<ViolationData>();
                byRule[ruleId].Add(v);
            }

            int total = results.Violations.Count;
            int critical = results.Violations.Count(v =>
                v.Severity != null && (v.Severity.ToUpper() == "CRITICAL" || v.Severity.ToUpper() == "CRITIQUE"));
            int haute = results.Violations.Count(v =>
                v.Severity != null && v.Severity.ToUpper() == "HAUTE");
            int other = total - critical - haute;

            // Construire le resume
            string summary = $"ANALYSE TERMINEE - Zone {zone}\n" +
                "========================================\n\n" +
                $"Donnees extraites:\n" +
                $"  Pieces: {data.Summary.Spaces}\n" +
                $"  Equipements: {data.Summary.Equipment}\n" +
                $"  Portes: {data.Summary.Doors}\n" +
                $"  Dalles: {data.Summary.Slabs}\n\n" +
                "RESULTATS PAR REGLE:\n" +
                "----------------------------------------\n";

            // Noms descriptifs des regles
            var ruleNames = new Dictionary<string, string>
            {
                { "ELEC-001", "Poids equipements" },
                { "ELEC-002", "Ventilation" },
                { "ELEC-003", "Acces portes" },
                { "ELEC-004", "Zones humides IP65" },
                { "GAINE-001", "Chute objets" },
                { "GAINE-002", "Croisement CF/CFA" },
                { "GAINE-003", "Trappes acces" },
                { "GAINE-004", "Surcharge supports" },
                { "GAINE-005", "Calcul charge supports" }
            };

            // Afficher chaque regle presente dans les resultats
            foreach (var rule in byRule.Keys.OrderBy(k => k))
            {
                int ruleCount = byRule[rule].Count;
                string ruleName = ruleNames.ContainsKey(rule) ? ruleNames[rule] : rule;
                if (ruleCount > 0)
                    summary += $"\n[{rule}] {ruleName}: {ruleCount} violation(s)\n";
                else
                    summary += $"\n[{rule}] {ruleName}: OK\n";
            }

            summary += "\n----------------------------------------\n" +
                $"Total: {total} violation(s) ({critical} critiques, {haute} hautes, {other} autres)\n" +
                $"Vues \"ZONES RISQUES\" creees: {viewCount}\n" +
                $"Elements colores: {coloredCount}\n" +
                $"Symboles places: {annotationCount}\n\n" +
                "LEGENDE DES SYMBOLES SUR LE PLAN:\n";

            // Legende dynamique selon la zone
            if (zone == "1" || zone == "all")
                summary +=
                    "  O  Cercle bleu    = VENTILATION requise (ELEC-002)\n" +
                    "  /\\  Triangle orange = PORTE trop etroite (ELEC-003)\n" +
                    "  <>  Losange rouge  = ZONE HUMIDE IP65 (ELEC-004)\n";
            if (zone == "2" || zone == "all")
                summary +=
                    "  <>  Losange rouge  = CHUTE OBJETS (GAINE-001)\n" +
                    "  O  Cercle magenta = CROISEMENT CF/CFA (GAINE-002)\n" +
                    "  /\\  Triangle vert  = TRAPPE ACCES (GAINE-003)\n" +
                    "  /\\  Triangle marron = SURCHARGE SUPPORT (GAINE-004/005)\n";

            summary += "\nLes vues originales ne sont PAS modifiees.\n" +
                "Consultez les vues prefixees \"ZONES RISQUES -\" dans le navigateur.\n\n" +
                $"Rapport: {resultPath}";

            TaskDialog.Show("CHU Security Analyzer - Resultats", summary);
        }

        // =====================================================================
        //  SELECTION ZONE
        // =====================================================================

        private string ShowZoneSelectionDialog()
        {
            using (var form = new System.Windows.Forms.Form())
            {
                form.Text = "CHU Security Analyzer - Selection Zone";
                form.Size = new System.Drawing.Size(400, 320);
                form.StartPosition = FormStartPosition.CenterScreen;
                form.FormBorderStyle = FormBorderStyle.FixedDialog;
                form.MaximizeBox = false;
                form.MinimizeBox = false;

                var label = new Label
                {
                    Text = "Selectionnez la zone d'analyse :",
                    Location = new System.Drawing.Point(20, 20),
                    Size = new System.Drawing.Size(350, 25),
                    Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold)
                };

                var radioButtons = new RadioButton[]
                {
                    new RadioButton { Text = "Zone 1 - Locaux Electriques (ELEC-001 a 004)", Location = new System.Drawing.Point(30, 55), Size = new System.Drawing.Size(330, 25), Checked = true },
                    new RadioButton { Text = "Zone 2 - Gaines Techniques (GAINE-001 a 005)", Location = new System.Drawing.Point(30, 85), Size = new System.Drawing.Size(330, 25) },
                    new RadioButton { Text = "Zone 3 - Faux Plafonds Tech. (FPLAF-001 a 003)", Location = new System.Drawing.Point(30, 115), Size = new System.Drawing.Size(330, 25) },
                    new RadioButton { Text = "Zone 4 - Planchers Techniques (PLAN-001 a 005)", Location = new System.Drawing.Point(30, 145), Size = new System.Drawing.Size(330, 25) },
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

        // =====================================================================
        //  DETECTION ARCHI / ELEC
        // =====================================================================

        private void DetectArchiAndElec(Document hostDoc, out Document docArchi, out Document docElec, out string statusMsg)
        {
            docArchi = null;
            docElec = null;
            string hostTitle = hostDoc.Title.ToLower();

            bool hostIsElec = hostTitle.Contains("ele") || hostTitle.Contains("ceg") ||
                              hostTitle.Contains("cfo") || hostTitle.Contains("cfa") ||
                              hostTitle.Contains("elec");
            bool hostIsArchi = hostTitle.Contains("arc") || hostTitle.Contains("archi");

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

            if (hostIsElec && linkedArchi != null)
            {
                docArchi = linkedArchi;
                docElec = hostDoc;
                statusMsg = $"Configuration: ELEC hote + ARCHI en lien\n" +
                           $"  ARCHI (lien): {linkedArchi.Title}\n" +
                           $"  ELEC (hote): {hostDoc.Title}";
                return;
            }

            if ((hostIsArchi || !hostIsElec) && linkedElec != null)
            {
                docArchi = hostDoc;
                docElec = linkedElec;
                statusMsg = $"Configuration: ARCHI hote + ELEC en lien\n" +
                           $"  ARCHI (hote): {hostDoc.Title}\n" +
                           $"  ELEC (lien): {linkedElec.Title}";
                return;
            }

            docArchi = hostDoc;
            docElec = null;
            statusMsg = $"Maquette unique: {hostDoc.Title}\n(Pas de lien ARCHI/ELEC detecte)";
        }

        // =====================================================================
        //  COLORATION DES EQUIPEMENTS EN VIOLATION
        // =====================================================================

        private int ApplyViolationColors(Document doc, Autodesk.Revit.DB.View view, AnalysisResults results, ExtractedData data)
        {
            int count = 0;

            // Rouge = CRITICAL, Orange = IMPORTANT
            var overrideCritical = new OverrideGraphicSettings();
            overrideCritical.SetSurfaceForegroundPatternColor(new Color(255, 0, 0));
            overrideCritical.SetSurfaceForegroundPatternVisible(true);
            overrideCritical.SetProjectionLineColor(new Color(255, 0, 0));

            var overrideImportant = new OverrideGraphicSettings();
            overrideImportant.SetSurfaceForegroundPatternColor(new Color(255, 140, 0));
            overrideImportant.SetSurfaceForegroundPatternVisible(true);
            overrideImportant.SetProjectionLineColor(new Color(255, 140, 0));

            FillPatternElement solidPattern = GetSolidFillPattern(doc);
            if (solidPattern != null)
            {
                overrideCritical.SetSurfaceForegroundPatternId(solidPattern.Id);
                overrideImportant.SetSurfaceForegroundPatternId(solidPattern.Id);
            }

            // Construire un index: space_name -> severite la plus haute
            var spaceSeverity = new Dictionary<string, string>();
            foreach (var v in results.Violations)
            {
                string key = v.SpaceName ?? "";
                string sev = v.Severity?.ToUpper() ?? "";
                if (!spaceSeverity.ContainsKey(key) || sev == "CRITICAL")
                    spaceSeverity[key] = sev;
            }

            // Construire un index: space_name -> liste d'equipment revit_element_id
            var spaceEquipmentIds = new Dictionary<string, List<int>>();
            foreach (var space in data.Spaces)
            {
                string sName = space.Name;
                if (!spaceSeverity.ContainsKey(sName)) continue;

                var equipIds = new List<int>();
                double[] sMin = space.BboxMin;
                double[] sMax = space.BboxMax;

                foreach (var eq in data.Equipment)
                {
                    double[] c = eq.Centroid;
                    if (c[0] >= sMin[0] && c[0] <= sMax[0] &&
                        c[1] >= sMin[1] && c[1] <= sMax[1] &&
                        c[2] >= sMin[2] && c[2] <= sMax[2])
                    {
                        if (eq.RevitElementId > 0)
                            equipIds.Add(eq.RevitElementId);
                    }
                }
                spaceEquipmentIds[sName] = equipIds;
            }

            // Colorer les equipements (qui sont dans le doc hote ELEC)
            var coloredElements = new HashSet<int>();

            foreach (var kvp in spaceEquipmentIds)
            {
                string spaceName = kvp.Key;
                string sev = spaceSeverity.ContainsKey(spaceName) ? spaceSeverity[spaceName] : "";

                OverrideGraphicSettings overrideToApply =
                    (sev == "CRITICAL" || sev == "CRITIQUE" || sev == "HAUTE") ? overrideCritical : overrideImportant;

                foreach (int eqId in kvp.Value)
                {
                    if (coloredElements.Contains(eqId)) continue;
                    coloredElements.Add(eqId);

                    try
                    {
                        ElementId elemId = new ElementId(eqId);
                        view.SetElementOverrides(elemId, overrideToApply);
                        count++;
                    }
                    catch { }
                }
            }

            return count;
        }

        // =====================================================================
        //  STYLES DE LIGNE COLORES POUR LES SYMBOLES
        // =====================================================================

        private Dictionary<string, GraphicsStyle> GetOrCreateLineStyles(Document doc)
        {
            var styles = new Dictionary<string, GraphicsStyle>();

            // Couleurs par regle (Zone 1 + Zone 2)
            var ruleColors = new Dictionary<string, Color>
            {
                // Zone 1 - Locaux Electriques
                { "ELEC-002", new Color(0, 100, 255) },    // Bleu
                { "ELEC-003", new Color(255, 140, 0) },    // Orange
                { "ELEC-004", new Color(255, 0, 0) },      // Rouge
                // Zone 2 - Gaines Techniques
                { "GAINE-001", new Color(200, 0, 0) },     // Rouge fonce (chute objets)
                { "GAINE-002", new Color(255, 0, 255) },   // Magenta (croisement CF/CFA)
                { "GAINE-003", new Color(0, 150, 0) },     // Vert (trappes acces)
                { "GAINE-004", new Color(180, 100, 0) },   // Marron (surcharge supports)
                { "GAINE-005", new Color(180, 100, 0) }    // Marron (calcul charge)
            };

            // Chercher la categorie Lines
            Categories categories = doc.Settings.Categories;
            Category linesCat = categories.get_Item(BuiltInCategory.OST_Lines);

            foreach (var kvp in ruleColors)
            {
                string styleName = "CHU_" + kvp.Key;
                Color color = kvp.Value;

                // Chercher si le style existe deja
                GraphicsStyle existing = null;
                foreach (Category subCat in linesCat.SubCategories)
                {
                    if (subCat.Name == styleName)
                    {
                        existing = subCat.GetGraphicsStyle(GraphicsStyleType.Projection);
                        break;
                    }
                }

                if (existing != null)
                {
                    styles[kvp.Key] = existing;
                }
                else
                {
                    // Creer une nouvelle sous-categorie de ligne
                    Category newSubCat = categories.NewSubcategory(linesCat, styleName);
                    newSubCat.LineColor = color;
                    newSubCat.SetLineWeight(5, GraphicsStyleType.Projection);

                    GraphicsStyle gs = newSubCat.GetGraphicsStyle(GraphicsStyleType.Projection);
                    styles[kvp.Key] = gs;
                }
            }

            return styles;
        }

        // =====================================================================
        //  PLACEMENT DES SYMBOLES DETAILCURVE + TEXTE
        // =====================================================================

        private const double SYMBOL_SPACING = 4.0; // espacement entre symboles en pieds

        private int PlaceViolationAnnotations(Document doc, Autodesk.Revit.DB.View view,
            AnalysisResults results, ExtractedData data,
            Dictionary<string, GraphicsStyle> lineStyles,
            FamilySymbol riskSymbol = null)
        {
            int count = 0;

            // Determiner la plage Z de la vue active (en pieds)
            double viewZMin = double.MinValue;
            double viewZMax = double.MaxValue;

            ViewPlan viewPlan = view as ViewPlan;
            if (viewPlan != null && viewPlan.GenLevel != null)
            {
                double levelZ = viewPlan.GenLevel.Elevation;
                viewZMin = levelZ - 1.0;
                viewZMax = levelZ + 16.4;
            }

            // Chercher un TextNoteType pour les labels
            TextNoteType noteType = GetSmallestNoteType(doc);

            // Regrouper violations par espace
            var violationsBySpace = new Dictionary<string, List<ViolationData>>();
            foreach (var v in results.Violations)
            {
                string key = v.SpaceName ?? "INCONNU";
                if (!violationsBySpace.ContainsKey(key))
                    violationsBySpace[key] = new List<ViolationData>();
                violationsBySpace[key].Add(v);
            }

            foreach (var kvp in violationsBySpace)
            {
                string spaceName = kvp.Key;
                List<ViolationData> violations = kvp.Value;

                // Trouver les coordonnees de l'espace
                double[] location = FindSpaceLocation(data, spaceName);
                if (location == null || location.Length < 3) continue;

                double x = location[0] / 0.3048;
                double y = location[1] / 0.3048;
                double z = location[2] / 0.3048;

                if (z < viewZMin || z > viewZMax) continue;

                // Identifier les regles distinctes
                var rulesInSpace = new HashSet<string>();
                foreach (var v in violations)
                {
                    if (v.RuleId != null) rulesInSpace.Add(v.RuleId);
                }

                int symbolIndex = 0;
                foreach (string ruleId in rulesInSpace)
                {
                    double offsetX = symbolIndex * SYMBOL_SPACING;
                    XYZ center = new XYZ(x + offsetX, y, 0);

                    int ruleCount = violations.Count(v => v.RuleId == ruleId);
                    string label = GetSymbolLabel(ruleId, ruleCount);

                    GraphicsStyle gs = lineStyles.ContainsKey(ruleId) ? lineStyles[ruleId] : null;

                    try
                    {
                        // Dessiner le symbole geometrique
                        double s = 1.5; // taille du symbole en pieds (~45cm)

                        switch (ruleId)
                        {
                            // === Zone 1 - Locaux Electriques ===
                            case "ELEC-002": // Cercle 2D sur plan (famille 3D placee separement)
                                DrawCircleSymbol(doc, view, center, s, gs);
                                break;
                            case "ELEC-003": // Triangle
                                DrawTriangleSymbol(doc, view, center, s, gs);
                                break;
                            case "ELEC-004": // Losange
                                DrawDiamondSymbol(doc, view, center, s, gs);
                                break;

                            // === Zone 2 - Gaines Techniques ===
                            case "GAINE-001": // Losange rouge (chute objets)
                                DrawDiamondSymbol(doc, view, center, s, gs);
                                break;
                            case "GAINE-002": // Cercle magenta (croisement CF/CFA)
                                DrawCircleSymbol(doc, view, center, s, gs);
                                break;
                            case "GAINE-003": // Triangle vert (trappes acces)
                                DrawTriangleSymbol(doc, view, center, s, gs);
                                break;
                            case "GAINE-004": // Triangle marron (surcharge)
                            case "GAINE-005":
                                DrawTriangleSymbol(doc, view, center, s, gs);
                                break;
                        }

                        // Placer le texte a cote
                        if (noteType != null)
                        {
                            XYZ textPt = new XYZ(center.X + s + 0.5, center.Y, 0);
                            TextNoteOptions opts = new TextNoteOptions();
                            opts.TypeId = noteType.Id;
                            opts.HorizontalAlignment = HorizontalTextAlignment.Left;
                            TextNote.Create(doc, view.Id, textPt, label, opts);
                        }

                        count++;
                    }
                    catch { }

                    symbolIndex++;
                }
            }

            return count;
        }

        // =====================================================================
        //  CHARGEMENT FAMILLE .RFA SYMBOLE DE RISQUE
        // =====================================================================

        /// <summary>
        /// Charge la famille .rfa du symbole de risque dans le document Revit.
        /// Retourne le FamilySymbol pret a etre instancie, ou null si echec.
        /// </summary>
        private FamilySymbol LoadOrGetRiskFamily(Document doc)
        {
            // 1. Verifier si Famille_TEST est deja chargee
            FamilySymbol existingSymbol = new FilteredElementCollector(doc)
                .OfClass(typeof(FamilySymbol))
                .Cast<FamilySymbol>()
                .FirstOrDefault(fs => fs.FamilyName == RISK_FAMILY_NAME);

            if (existingSymbol != null)
            {
                if (!existingSymbol.IsActive) existingSymbol.Activate();
                return existingSymbol;
            }

            // 2. Trouver le fichier .rfa
            string dllDir = Path.GetDirectoryName(
                System.Reflection.Assembly.GetExecutingAssembly().Location);
            string rfaPath = Path.Combine(dllDir, RISK_FAMILY_RFA);

            if (!File.Exists(rfaPath))
            {
                string familiesDir = Path.Combine(PROJECT_DIR, "RevitPlugin", "Families");
                rfaPath = Path.Combine(familiesDir, RISK_FAMILY_RFA);
            }

            if (!File.Exists(rfaPath)) return null;

            // 3. Charger la famille
            Family family = null;
            bool loaded = doc.LoadFamily(rfaPath, out family);

            if (!loaded || family == null)
            {
                // Si LoadFamily retourne false, la famille est peut-etre deja chargee
                // sous le meme nom - re-essayer la recherche par nom exact uniquement
                existingSymbol = new FilteredElementCollector(doc)
                    .OfClass(typeof(FamilySymbol))
                    .Cast<FamilySymbol>()
                    .FirstOrDefault(fs => fs.FamilyName == RISK_FAMILY_NAME
                                       || fs.FamilyName.Contains("Famille_TEST"));

                if (existingSymbol != null)
                {
                    if (!existingSymbol.IsActive) existingSymbol.Activate();
                    return existingSymbol;
                }
                return null;
            }

            // 4. Recuperer le premier FamilySymbol (type) de la famille
            ISet<ElementId> typeIds = family.GetFamilySymbolIds();
            if (typeIds.Count == 0) return null;

            FamilySymbol symbol = doc.GetElement(typeIds.First()) as FamilySymbol;
            if (symbol != null && !symbol.IsActive) symbol.Activate();
            return symbol;
        }

        // =====================================================================
        //  DESSIN DES SYMBOLES GEOMETRIQUES (DetailCurve)
        // =====================================================================

        private void DrawCircleSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double radius, GraphicsStyle gs)
        {
            int segments = 16;
            for (int i = 0; i < segments; i++)
            {
                double a1 = 2 * Math.PI * i / segments;
                double a2 = 2 * Math.PI * (i + 1) / segments;
                XYZ p1 = new XYZ(center.X + radius * Math.Cos(a1), center.Y + radius * Math.Sin(a1), 0);
                XYZ p2 = new XYZ(center.X + radius * Math.Cos(a2), center.Y + radius * Math.Sin(a2), 0);
                DrawLineInView(doc, view, p1, p2, gs);
            }
            // Lettre V au centre
            DrawLineInView(doc, view,
                new XYZ(center.X - radius * 0.3, center.Y + radius * 0.4, 0),
                new XYZ(center.X, center.Y - radius * 0.4, 0), gs);
            DrawLineInView(doc, view,
                new XYZ(center.X, center.Y - radius * 0.4, 0),
                new XYZ(center.X + radius * 0.3, center.Y + radius * 0.4, 0), gs);
        }

        private void DrawTriangleSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
        {
            double s = size;
            XYZ top = new XYZ(center.X, center.Y + s, 0);
            XYZ bottomLeft = new XYZ(center.X - s * 0.866, center.Y - s * 0.5, 0);
            XYZ bottomRight = new XYZ(center.X + s * 0.866, center.Y - s * 0.5, 0);

            DrawLineInView(doc, view, top, bottomLeft, gs);
            DrawLineInView(doc, view, bottomLeft, bottomRight, gs);
            DrawLineInView(doc, view, bottomRight, top, gs);

            // Point d'exclamation
            DrawLineInView(doc, view,
                new XYZ(center.X, center.Y + s * 0.4, 0),
                new XYZ(center.X, center.Y - s * 0.15, 0), gs);
            DrawLineInView(doc, view,
                new XYZ(center.X, center.Y - s * 0.25, 0),
                new XYZ(center.X, center.Y - s * 0.35, 0), gs);
        }

        private void DrawDiamondSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
        {
            double s = size;
            XYZ top = new XYZ(center.X, center.Y + s, 0);
            XYZ right = new XYZ(center.X + s, center.Y, 0);
            XYZ bottom = new XYZ(center.X, center.Y - s, 0);
            XYZ left = new XYZ(center.X - s, center.Y, 0);

            DrawLineInView(doc, view, top, right, gs);
            DrawLineInView(doc, view, right, bottom, gs);
            DrawLineInView(doc, view, bottom, left, gs);
            DrawLineInView(doc, view, left, top, gs);

            // Point d'exclamation
            DrawLineInView(doc, view,
                new XYZ(center.X, center.Y + s * 0.5, 0),
                new XYZ(center.X, center.Y - s * 0.2, 0), gs);
            DrawLineInView(doc, view,
                new XYZ(center.X, center.Y - s * 0.35, 0),
                new XYZ(center.X, center.Y - s * 0.45, 0), gs);
        }

        private void DrawLineInView(Document doc, Autodesk.Revit.DB.View view, XYZ start, XYZ end, GraphicsStyle gs)
        {
            Line line = Line.CreateBound(start, end);
            DetailCurve dc = doc.Create.NewDetailCurve(view, line);
            if (gs != null)
            {
                dc.LineStyle = gs;
            }
        }

        // =====================================================================
        //  LABELS DES SYMBOLES
        // =====================================================================

        private string GetSymbolLabel(string ruleId, int count)
        {
            switch (ruleId)
            {
                // Zone 1
                case "ELEC-002":
                    return "VENTILATION";
                case "ELEC-003":
                    return "PORTE (" + count + ")";
                case "ELEC-004":
                    return "IP65 (" + count + ")";
                // Zone 2
                case "GAINE-001":
                    return "CHUTE (" + count + ")";
                case "GAINE-002":
                    return "CF/CFA (" + count + ")";
                case "GAINE-003":
                    return "TRAPPE (" + count + ")";
                case "GAINE-004":
                    return "SURCHARGE (" + count + ")";
                case "GAINE-005":
                    return "CHARGE (" + count + ")";
                default:
                    return ruleId + " (" + count + ")";
            }
        }

        private double[] FindSpaceLocation(ExtractedData data, string spaceName)
        {
            foreach (var space in data.Spaces)
            {
                if (space.Name == spaceName)
                    return space.Centroid;
            }
            return null;
        }

        private TextNoteType GetSmallestNoteType(Document doc)
        {
            var collector = new FilteredElementCollector(doc)
                .OfClass(typeof(TextNoteType));

            TextNoteType smallest = null;
            double smallestSize = double.MaxValue;

            foreach (TextNoteType tnt in collector)
            {
                Parameter textSize = tnt.get_Parameter(BuiltInParameter.TEXT_SIZE);
                if (textSize != null && textSize.HasValue)
                {
                    double size = textSize.AsDouble();
                    if (size < smallestSize)
                    {
                        smallestSize = size;
                        smallest = tnt;
                    }
                }
            }

            return smallest;
        }

        // =====================================================================
        //  UTILITAIRES
        // =====================================================================

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
