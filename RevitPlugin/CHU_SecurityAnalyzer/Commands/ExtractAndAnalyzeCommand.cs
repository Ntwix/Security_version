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
using CHU_SecurityAnalyzer.UI;
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
        private const string RISK_FAMILY_RFA = "ELEC-002.rfa";
        private const string RISK_FAMILY_NAME = "ELEC-002";
        private const string FAMILIES_ELEC_DIR = "ELEC";

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

                // === Etape 6b : GAINE-003 — Formulaire trappes d'accès (Zone 2 uniquement) ===
                if (zone == "2")
                    results = HandleGaine003TrappesForm(results, doc, resultPath);

                // === Etape 6c : GAINE-005 — Formulaire charge supports (Zone 2 uniquement) ===
                if (zone == "2")
                    results = HandleGaine005ChargeForm(results, resultPath);

                // === Etape 6d : CHANT-001 — Formulaire chemin d'accès manutention (Catégorie 5) ===
                if (zone == "5")
                    results = HandleChant001ManutentionForm(results, resultPath);

                // === Etape 7 : Dupliquer vues + appliquer coloration et symboles ===
                var vizResult = ApplyVisualizationsToAllViews(doc, uiDoc, results, data);

                // === Etape 8 : Mettre a jour le panneau dockable ===
                try { RiskDockablePane.UpdateResults(uiApp, results, zone); }
                catch { }

                // === Etape 9 : Naviguer vers la vue risques + afficher resume ===
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
        //  GAINE-003 — FORMULAIRE TRAPPES D'ACCES
        // =====================================================================

        /// <summary>
        /// Détecte la violation GAINE-003 en lisant directement le JSON brut,
        /// ouvre le formulaire WPF, puis remplace la violation générique par
        /// une violation par équipement sélectionné.
        /// DataContractJsonSerializer ne peut pas désérialiser Dictionary[string,object]
        /// avec des valeurs complexes — on lit donc le JSON résultat directement.
        /// </summary>
        private AnalysisResults HandleGaine003TrappesForm(AnalysisResults results, Document doc, string resultJsonPath)
        {
            if (results?.Violations == null) return results;

            // Vérifier qu'il y a une violation GAINE-003 dans les résultats
            var gaine003Marker = results.Violations.FirstOrDefault(v => v.RuleId == "GAINE-003");
            if (gaine003Marker == null) return results;

            // Lire le JSON brut pour extraire les détails (contournement limitation DataContractJsonSerializer)
            var equipmentList = new List<CHU_SecurityAnalyzer.UI.EquipmentItem>();
            double minW = 0.60, minH = 0.60;

            try
            {
                string rawJson = File.ReadAllText(resultJsonPath, System.Text.Encoding.UTF8);
                equipmentList = ParseEquipmentListFromRawJson(rawJson, out minW, out minH);
            }
            catch { }

            if (equipmentList == null || equipmentList.Count == 0) return results;

            // Ouvrir formulaire WPF
            var dialog = new CHU_SecurityAnalyzer.UI.TrappesFormDialog(equipmentList, minW, minH);
            bool? dialogResult = dialog.ShowDialog();

            // Supprimer la violation générique GAINE-003
            results.Violations.Remove(gaine003Marker);

            if (dialogResult != true || dialog.SelectedEquipment == null
                || dialog.SelectedEquipment.Count == 0)
                return results;

            // Créer une violation par équipement sélectionné
            foreach (var eq in dialog.SelectedEquipment)
            {
                results.Violations.Add(new ViolationData
                {
                    RuleId      = "GAINE-003",
                    Severity    = "MOYENNE",
                    SpaceName   = eq.GaineName ?? eq.Name,
                    SpaceGlobalId = eq.GaineGlobalId ?? "",
                    Description = $"Trappe de visite requise pour : {eq.Name}",
                    Location    = eq.Location,
                    Recommendation =
                        $"Prévoir une trappe {(int)(minW*100)}×{(int)(minH*100)} cm " +
                        $"à proximité de {eq.Name} dans {eq.GaineName}."
                });
            }

            return results;
        }

        // =====================================================================
        //  GAINE-005 — FORMULAIRE CHARGE SUPPORTS
        // =====================================================================

        /// <summary>
        /// Lit le cdc_summary du JSON Python, ouvre ChargeSupportsDialog,
        /// puis remplace la violation marker par une violation par type de CDC dépassant la capacité.
        /// </summary>
        private AnalysisResults HandleGaine005ChargeForm(AnalysisResults results, string resultJsonPath)
        {
            if (results?.Violations == null) return results;

            var marker = results.Violations.FirstOrDefault(v => v.RuleId == "GAINE-005");
            if (marker == null) return results;

            // Lire cdc_summary depuis le JSON brut
            var cdcTypes       = new List<CHU_SecurityAnalyzer.UI.CdcTypeInfo>();
            double capacity    = 90.0;
            double marginPct   = 20.0;

            try
            {
                string rawJson = File.ReadAllText(resultJsonPath, System.Text.Encoding.UTF8);
                ParseGaine005Details(rawJson, out cdcTypes, out capacity, out marginPct);
            }
            catch { }

            if (cdcTypes == null || cdcTypes.Count == 0)
            {
                results.Violations.Remove(marker);
                return results;
            }

            // Ouvrir formulaire WPF
            var dialog = new CHU_SecurityAnalyzer.UI.ChargeSupportsDialog(cdcTypes, capacity, marginPct);
            bool? dialogResult = dialog.ShowDialog();

            // Supprimer la violation marker générique
            results.Violations.Remove(marker);

            if (dialogResult != true || dialog.Results == null || dialog.Results.Count == 0)
                return results;

            // Créer une violation par type de CDC qui dépasse la capacité
            foreach (var res in dialog.Results)
            {
                if (!res.IsViolation) continue;

                double excess = res.TotalWeightKg - res.SafeCapacityKg;
                results.Violations.Add(new ViolationData
                {
                    RuleId        = "GAINE-005",
                    Severity      = "HAUTE",
                    SpaceName     = $"CDC {res.ServiceType}",
                    SpaceGlobalId = "",
                    Description   = $"CDC {res.ServiceType} : charge totale {res.TotalWeightKg:F1} kg > capacité admissible {res.SafeCapacityKg:F0} kg",
                    Location      = new double[] { 0, 0, 0 },
                    Recommendation =
                        $"Renforcer les supports ou réduire le nombre de câbles sur CDC {res.ServiceType}. " +
                        $"Excès : {excess:F1} kg. Câbles déclarés : {res.Breakdown}"
                });
            }

            return results;
        }

        // =====================================================================
        //  CHANT-001 — FORMULAIRE CHEMIN D'ACCES MANUTENTION
        // =====================================================================

        /// <summary>
        /// Détecte la violation CHANT-001, ouvre le formulaire chemin d'accès,
        /// puis remplace la violation générique par des violations par obstacle bloquant.
        /// </summary>
        private AnalysisResults HandleChant001ManutentionForm(AnalysisResults results, string resultJsonPath)
        {
            if (results?.Violations == null) return results;

            var marker = results.Violations.FirstOrDefault(v => v.RuleId == "CHANT-001");
            if (marker == null) return results;

            // Parser les données depuis le JSON brut
            var equipements = new List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd>();
            var obstacles   = new List<CHU_SecurityAnalyzer.UI.Chant001Obstacle>();

            try
            {
                string rawJson = File.ReadAllText(resultJsonPath, System.Text.Encoding.UTF8);
                ParseChant001Details(rawJson, out equipements, out obstacles);
            }
            catch { }

            // Supprimer la violation marker
            results.Violations.Remove(marker);

            if (equipements == null || equipements.Count == 0)
                return results;

            // Ouvrir le formulaire WPF
            var dialog = new CHU_SecurityAnalyzer.UI.Chant001ManutentionDialog(equipements, obstacles);
            bool? dialogResult = dialog.ShowDialog();

            if (dialogResult != true || dialog.ViolationResults == null
                || dialog.ViolationResults.Count == 0)
                return results;

            // Créer une violation par obstacle bloquant détecté
            foreach (var v in dialog.ViolationResults)
            {
                string typeLabel = v.ObstacleType == "escalier" ? "Escalier"
                                 : v.ObstacleType == "ascenseur" ? "Ascenseur"
                                 : "Porte";
                results.Violations.Add(new ViolationData
                {
                    RuleId        = "CHANT-001",
                    Severity      = "HAUTE",
                    SpaceName     = v.LocalName ?? v.EquipementName,
                    SpaceGlobalId = v.LocalGlobalId ?? "",
                    Description   = $"{typeLabel} \"{v.ObstacleName}\" ({v.ObstacleWidthM:F2} m) trop étroit(e) pour {v.EquipementName} ({v.EquipDimMaxM:F2} m)",
                    Location      = v.Location,
                    Recommendation =
                        $"Élargir {typeLabel.ToLower()} \"{v.ObstacleName}\" à au moins {v.EquipDimMaxM:F2} m " +
                        $"pour permettre le passage de {v.EquipementName} vers {v.LocalName}."
                });
            }

            return results;
        }

        /// <summary>
        /// Parse les équipements lourds et obstacles CHANT-001 depuis le JSON brut.
        /// </summary>
        private void ParseChant001Details(string rawJson,
            out List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd> equipements,
            out List<CHU_SecurityAnalyzer.UI.Chant001Obstacle> obstacles)
        {
            equipements = new List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd>();
            obstacles   = new List<CHU_SecurityAnalyzer.UI.Chant001Obstacle>();

            try
            {
                // Extraire "equipements_lourds"
                string eq = ExtractJsonArray(rawJson, "equipements_lourds");
                if (!string.IsNullOrEmpty(eq))
                {
                    using (var ms = new System.IO.MemoryStream(System.Text.Encoding.UTF8.GetBytes(eq)))
                    {
                        var ser = new System.Runtime.Serialization.Json.DataContractJsonSerializer(
                            typeof(List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd>));
                        equipements = (List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd>)ser.ReadObject(ms);
                    }
                }

                // Extraire "obstacles_disponibles"
                string obs = ExtractJsonArray(rawJson, "obstacles_disponibles");
                if (!string.IsNullOrEmpty(obs))
                {
                    using (var ms = new System.IO.MemoryStream(System.Text.Encoding.UTF8.GetBytes(obs)))
                    {
                        var ser = new System.Runtime.Serialization.Json.DataContractJsonSerializer(
                            typeof(List<CHU_SecurityAnalyzer.UI.Chant001Obstacle>));
                        obstacles = (List<CHU_SecurityAnalyzer.UI.Chant001Obstacle>)ser.ReadObject(ms);
                    }
                }
            }
            catch { }

            if (equipements == null) equipements = new List<CHU_SecurityAnalyzer.UI.Chant001EquipementLourd>();
            if (obstacles   == null) obstacles   = new List<CHU_SecurityAnalyzer.UI.Chant001Obstacle>();
        }

        /// <summary>Extrait un tableau JSON par clé depuis le JSON brut.</summary>
        private static string ExtractJsonArray(string json, string key)
        {
            string marker = $"\"{key}\"";
            int markerIdx = json.IndexOf(marker);
            if (markerIdx < 0) return null;

            int arrStart = json.IndexOf('[', markerIdx + marker.Length);
            if (arrStart < 0) return null;

            int depth = 0, arrEnd = -1;
            for (int i = arrStart; i < json.Length; i++)
            {
                if (json[i] == '[') depth++;
                else if (json[i] == ']') { depth--; if (depth == 0) { arrEnd = i; break; } }
            }
            if (arrEnd < 0) return null;

            return json.Substring(arrStart, arrEnd - arrStart + 1);
        }

        /// <summary>
        /// Extrait le tableau cdc_summary et les paramètres de capacité
        /// depuis le JSON brut du résultat Python GAINE-005.
        /// </summary>
        private void ParseGaine005Details(string rawJson,
            out List<CHU_SecurityAnalyzer.UI.CdcTypeInfo> cdcTypes,
            out double capacity, out double marginPct)
        {
            cdcTypes  = new List<CHU_SecurityAnalyzer.UI.CdcTypeInfo>();
            capacity  = 90.0;
            marginPct = 20.0;

            try
            {
                // Extraire support_capacity_kg
                ExtractJsonDouble(rawJson, "support_capacity_kg",    ref capacity);
                ExtractJsonDouble(rawJson, "safety_margin_percent",  ref marginPct);

                // Trouver le tableau cdc_summary
                string marker = "\"cdc_summary\"";
                int markerIdx = rawJson.IndexOf(marker);
                if (markerIdx < 0) return;

                int arrStart = rawJson.IndexOf('[', markerIdx + marker.Length);
                if (arrStart < 0) return;

                // Trouver fin du tableau
                int depth = 0, arrEnd = -1;
                for (int i = arrStart; i < rawJson.Length; i++)
                {
                    if (rawJson[i] == '[') depth++;
                    else if (rawJson[i] == ']') { depth--; if (depth == 0) { arrEnd = i; break; } }
                }
                if (arrEnd < 0) return;

                string arrJson = rawJson.Substring(arrStart, arrEnd - arrStart + 1);
                using (var ms = new System.IO.MemoryStream(System.Text.Encoding.UTF8.GetBytes(arrJson)))
                {
                    var ser = new System.Runtime.Serialization.Json.DataContractJsonSerializer(
                        typeof(List<CHU_SecurityAnalyzer.UI.CdcTypeInfo>));
                    cdcTypes = (List<CHU_SecurityAnalyzer.UI.CdcTypeInfo>)ser.ReadObject(ms);
                }
            }
            catch { }

            if (cdcTypes == null) cdcTypes = new List<CHU_SecurityAnalyzer.UI.CdcTypeInfo>();
        }

        /// <summary>
        /// Parse la liste d'équipements GAINE-003 directement depuis le JSON brut
        /// en localisant le bloc "equipment_list" avec une recherche de texte simple.
        /// </summary>
        private List<CHU_SecurityAnalyzer.UI.EquipmentItem> ParseEquipmentListFromRawJson(
            string rawJson, out double minW, out double minH)
        {
            minW = 0.60;
            minH = 0.60;
            var list = new List<CHU_SecurityAnalyzer.UI.EquipmentItem>();

            try
            {
                // Extraire min_trappe_width_m et min_trappe_height_m
                ExtractJsonDouble(rawJson, "min_trappe_width_m", ref minW);
                ExtractJsonDouble(rawJson, "min_trappe_height_m", ref minH);

                // Trouver le tableau equipment_list
                string marker = "\"equipment_list\"";
                int markerIdx = rawJson.IndexOf(marker);
                if (markerIdx < 0) return list;

                int arrStart = rawJson.IndexOf('[', markerIdx + marker.Length);
                if (arrStart < 0) return list;

                // Trouver la fin du tableau en comptant les crochets
                int depth = 0;
                int arrEnd = -1;
                for (int i = arrStart; i < rawJson.Length; i++)
                {
                    if (rawJson[i] == '[') depth++;
                    else if (rawJson[i] == ']') { depth--; if (depth == 0) { arrEnd = i; break; } }
                }
                if (arrEnd < 0) return list;

                string arrJson = rawJson.Substring(arrStart, arrEnd - arrStart + 1);

                using (var ms = new System.IO.MemoryStream(System.Text.Encoding.UTF8.GetBytes(arrJson)))
                {
                    var ser = new System.Runtime.Serialization.Json.DataContractJsonSerializer(
                        typeof(List<CHU_SecurityAnalyzer.UI.EquipmentItem>));
                    list = (List<CHU_SecurityAnalyzer.UI.EquipmentItem>)ser.ReadObject(ms);
                }
            }
            catch { }

            return list ?? new List<CHU_SecurityAnalyzer.UI.EquipmentItem>();
        }

        private static void ExtractJsonDouble(string json, string key, ref double value)
        {
            string marker = $"\"{key}\"";
            int idx = json.IndexOf(marker);
            if (idx < 0) return;
            int colon = json.IndexOf(':', idx + marker.Length);
            if (colon < 0) return;
            int start = colon + 1;
            while (start < json.Length && (json[start] == ' ' || json[start] == '\t')) start++;
            int end = start;
            while (end < json.Length && (char.IsDigit(json[end]) || json[end] == '.' || json[end] == '-')) end++;
            if (end > start)
                double.TryParse(json.Substring(start, end - start),
                    System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out value);
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

                Dictionary<string, GraphicsStyle> lineStyles;
                var ruleSymbols = new Dictionary<string, FamilySymbol>();

                // === Transaction 1 : styles de ligne ===
                using (Transaction txStyles = new Transaction(doc, "CHU Security - Styles"))
                {
                    txStyles.Start();
                    lineStyles = GetOrCreateLineStyles(doc);
                    txStyles.Commit();
                }


                // === Transaction 2a : charger familles manquantes seulement ===
                string elecDir = Path.Combine(PROJECT_DIR, "RevitPlugin", "Families", FAMILIES_ELEC_DIR);
                var elecRuleIds = new[] { "ELEC-001", "ELEC-002", "ELEC-003", "ELEC-004" };

                // D'abord recuperer celles deja chargees (sans transaction)
                foreach (string ruleId in elecRuleIds)
                {
                    FamilySymbol existing = new FilteredElementCollector(doc)
                        .OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>()
                        .FirstOrDefault(fs => fs.FamilyName == ruleId);
                    if (existing != null)
                    {
                        if (!existing.IsActive)
                        {
                            using (Transaction txAct = new Transaction(doc, "Activate " + ruleId))
                            {
                                txAct.Start();
                                existing.Activate();
                                txAct.Commit();
                            }
                        }
                        ruleSymbols[ruleId] = existing;
                    }
                }

                // Charger seulement les familles manquantes (une transaction par famille)
                foreach (string ruleId in elecRuleIds)
                {
                    if (ruleSymbols.ContainsKey(ruleId)) continue; // deja chargee
                    string rfaPath = Path.Combine(elecDir, ruleId + ".rfa");
                    if (!File.Exists(rfaPath)) continue;

                    using (Transaction txLoad = new Transaction(doc, "Charger " + ruleId))
                    {
                        txLoad.Start();
                        Family family = null;
                        doc.LoadFamily(rfaPath, new SilentFamilyLoadOptions(), out family);
                        if (family != null)
                        {
                            var typeIds = family.GetFamilySymbolIds();
                            if (typeIds.Count > 0)
                            {
                                FamilySymbol sym = doc.GetElement(typeIds.First()) as FamilySymbol;
                                if (sym != null) { sym.Activate(); ruleSymbols[ruleId] = sym; }
                            }
                        }
                        txLoad.Commit();
                    }
                }

                // Zone 3 - Faux Plafonds : réutiliser symboles ELEC existants
                // FPLAF-001 (HAUTE=critique) -> losange ELEC-004
                // FPLAF-001 (MOYENNE=élevé)  -> triangle ELEC-003
                // FPLAF-002 (surcharge)      -> croix ELEC-001
                // FPLAF-003 (poussières)     -> cercle ELEC-002
                var fplafMapping = new Dictionary<string, string>
                {
                    { "FPLAF-001", "ELEC-004" },
                    { "FPLAF-002", "ELEC-001" },
                    { "FPLAF-003", "ELEC-002" },
                };
                foreach (var kv in fplafMapping)
                {
                    if (ruleSymbols.ContainsKey(kv.Value))
                        ruleSymbols[kv.Key] = ruleSymbols[kv.Value];
                }

                // === Transaction 2b : supprimer anciennes instances ===
                using (Transaction txClean = new Transaction(doc, "CHU Security - Nettoyage"))
                {
                    txClean.Start();

                    var elecSymIds = new FilteredElementCollector(doc)
                        .OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>()
                        .Where(fs => fs.FamilyName.StartsWith("ELEC-")
                                  || fs.FamilyName.Contains("Famille_TEST")
                                  || fs.FamilyName.Contains("renamed"))
                        .Select(fs => fs.Id).ToHashSet();

                    if (elecSymIds.Count > 0)
                    {
                        var oldInstances = new FilteredElementCollector(doc)
                            .OfClass(typeof(FamilyInstance)).Cast<FamilyInstance>()
                            .Where(fi => elecSymIds.Contains(fi.Symbol.Id))
                            .Select(fi => fi.Id).ToList();
                        if (oldInstances.Count > 0)
                            doc.Delete(oldInstances);
                    }

                    txClean.Commit();
                }

                // === Transaction 3 : placer les familles par espace selon la regle ===
                using (Transaction txPlace = new Transaction(doc, "CHU Security - Placement"))
                {
                    txPlace.Start();

                    var levels = new FilteredElementCollector(doc)
                        .OfClass(typeof(Level)).Cast<Level>()
                        .OrderBy(l => l.Elevation).ToList();

                    // Construire index revit_element_id -> SpaceData pour acces rapide
                    var spaceById = new Dictionary<int, SpaceData>();
                    foreach (var sp in data.Spaces)
                        if (sp.RevitElementId > 0) spaceById[sp.RevitElementId] = sp;

                    // Construire index name -> SpaceData
                    var spaceByName = new Dictionary<string, SpaceData>();
                    foreach (var sp in data.Spaces)
                        if (sp.Name != null && !spaceByName.ContainsKey(sp.Name)) spaceByName[sp.Name] = sp;

                    // Detecter le document ARCHI (contient les espaces/rooms)
                    Document docArchiLocal = null;
                    foreach (RevitLinkInstance li in new FilteredElementCollector(doc).OfClass(typeof(RevitLinkInstance)))
                    {
                        Document ld = li.GetLinkDocument();
                        if (ld == null) continue;
                        string lt = ld.Title.ToLower();
                        if (lt.Contains("arc") || lt.Contains("archi")) { docArchiLocal = ld; break; }
                    }

                    var placedKeys = new HashSet<string>();
                    foreach (var v in results.Violations)
                    {
                        if (!ruleSymbols.ContainsKey(v.RuleId)) continue;

                        string spaceKey = v.RuleId + "_" + (v.SpaceGlobalId ?? v.SpaceName ?? "");
                        if (placedKeys.Contains(spaceKey)) continue;
                        placedKeys.Add(spaceKey);

                        // Trouver la position depuis Revit via revit_element_id
                        XYZ pt = null;
                        Level bestLevel = null;

                        SpaceData spaceData = null;
                        if (v.SpaceName != null && spaceByName.ContainsKey(v.SpaceName))
                            spaceData = spaceByName[v.SpaceName];

                        // Essayer de recuperer la localisation depuis l'element Revit (ARCHI ou hote)
                        if (spaceData != null && spaceData.RevitElementId > 0)
                        {
                            ElementId eid = new ElementId(spaceData.RevitElementId);
                            Element elem = null;
                            if (docArchiLocal != null) elem = docArchiLocal.GetElement(eid);
                            if (elem == null) elem = doc.GetElement(eid);

                            if (elem != null)
                            {
                                LocationPoint lp = elem.Location as LocationPoint;
                                if (lp != null) pt = lp.Point;
                                else
                                {
                                    BoundingBoxXYZ bb = elem.get_BoundingBox(null);
                                    if (bb != null) pt = (bb.Min + bb.Max) / 2;
                                }
                                // Trouver le niveau de l'element
                                Parameter lvlParam = elem.get_Parameter(BuiltInParameter.ROOM_LEVEL_ID);
                                if (lvlParam != null)
                                    bestLevel = doc.GetElement(lvlParam.AsElementId()) as Level;
                            }
                        }

                        // Fallback : utiliser les coordonnees de la violation (location en metres IFC)
                        // et chercher le niveau par nom
                        if (pt == null && v.Location != null && v.Location.Length >= 3)
                        {
                            // Les coordonnees IFC sont en metres mais avec une origine differente
                            // On utilise uniquement Z pour trouver le niveau, X/Y depuis l'element Revit
                            // Si pas d'element Revit disponible, skip
                            continue;
                        }

                        if (pt == null) continue;

                        // Trouver le niveau si pas encore trouve
                        if (bestLevel == null && levels.Count > 0)
                        {
                            double bestDist = double.MaxValue;
                            foreach (var lvl in levels)
                            {
                                double dist = Math.Abs(lvl.Elevation - pt.Z);
                                if (dist < bestDist) { bestDist = dist; bestLevel = lvl; }
                            }
                        }

                        if (bestLevel != null)
                        {
                            XYZ placePt = new XYZ(pt.X, pt.Y, 0);
                            doc.Create.NewFamilyInstance(placePt, ruleSymbols[v.RuleId], bestLevel,
                                StructuralType.NonStructural);
                        }
                    }

                    txPlace.Commit();
                }

                FamilySymbol riskSymbol = ruleSymbols.ContainsKey("ELEC-002") ? ruleSymbols["ELEC-002"] : null;

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
        //  PLAGES Z AUTOMATIQUES PAR NIVEAU (generique, tout projet)
        // =====================================================================

        /// <summary>
        /// Calcule automatiquement les plages Z (en metres) de chaque niveau
        /// en lisant les elevations depuis Revit.
        /// Plage niveau N = [elevation(N), elevation(N+1)[
        /// Dernier niveau = [elevation(N), elevation(N) + hauteur_mediane]
        /// </summary>
        private Dictionary<ElementId, (double zMin, double zMax)> BuildLevelRanges(Document doc)
        {
            var result = new Dictionary<ElementId, (double, double)>();

            // Recuperer tous les niveaux tries par elevation croissante
            var levels = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .Cast<Level>()
                .OrderBy(l => l.Elevation)
                .ToList();

            if (levels.Count == 0) return result;

            // Convertir elevations pieds -> metres
            var elevM = levels.Select(l => l.Elevation * 0.3048).ToList();

            // Calculer hauteur mediane entre niveaux consecutifs
            double medianHeight = 3.5; // valeur par defaut
            if (levels.Count >= 2)
            {
                var heights = new List<double>();
                for (int i = 1; i < levels.Count; i++)
                    heights.Add(elevM[i] - elevM[i - 1]);
                heights.Sort();
                medianHeight = heights[heights.Count / 2];
            }

            for (int i = 0; i < levels.Count; i++)
            {
                double zMin = elevM[i];
                double zMax = (i + 1 < levels.Count) ? elevM[i + 1] : elevM[i] + medianHeight;
                result[levels[i].Id] = (zMin, zMax);
            }

            return result;
        }

        // =====================================================================
        //  NIVEAUX AVEC VIOLATIONS
        // =====================================================================

        private HashSet<double> GetLevelsWithViolations(
            Document doc, AnalysisResults results, ExtractedData data)
        {
            var levelElevations = new HashSet<double>();

            // Plages Z automatiques depuis Revit (generique, tout projet)
            var levelRanges = BuildLevelRanges(doc);
            var levels = new FilteredElementCollector(doc)
                .OfClass(typeof(Level)).Cast<Level>()
                .OrderBy(l => l.Elevation).ToList();

            // Pour chaque violation, trouver quel niveau contient cet espace
            var spaceZCache = new Dictionary<string, double>();
            foreach (var v in results.Violations)
            {
                string sName = v.SpaceName ?? "";
                if (!spaceZCache.ContainsKey(sName))
                {
                    double[] loc = FindSpaceLocation(data, sName);
                    spaceZCache[sName] = (loc != null && loc.Length >= 3) ? loc[2] : double.NaN;
                }
                double zM = spaceZCache[sName];
                if (double.IsNaN(zM)) continue;

                // Trouver le niveau dont la plage contient zM
                foreach (var level in levels)
                {
                    if (!levelRanges.ContainsKey(level.Id)) continue;
                    var range = levelRanges[level.Id];
                    if (zM >= range.zMin && zM < range.zMax)
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

            // Les instances ELEC sont des elements de modele (pas de vue) :
            // elles sont supprimees dans txClean avant chaque analyse, pas ici.
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
                { "GAINE-005", "Calcul charge supports" },
                { "FPLAF-001", "Chute de hauteur" },
                { "FPLAF-002", "Surcharge plafond" },
                { "FPLAF-003", "Poussieres" }
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
                    "  <>  Losange rouge   = CHUTE OBJETS (GAINE-001)\n" +
                    "  O   Cercle magenta  = CROISEMENT CF/CFA (GAINE-002)\n" +
                    "  /\\  Triangle vert   = TRAPPE ACCES (GAINE-003)\n" +
                    "  +   Croix marron    = SURCHARGE SUPPORT (GAINE-004)\n" +
                    "  []  Carre violet    = CALCUL CHARGE (GAINE-005)\n";
            if (zone == "3" || zone == "all")
                summary +=
                    "  <>  Losange rouge   = CHUTE HAUTEUR critique (FPLAF-001 HAUTE)\n" +
                    "  /\\  Triangle orange = CHUTE HAUTEUR elevee (FPLAF-001 MOYENNE)\n" +
                    "  +   Croix bleue     = SURCHARGE PLAFOND (FPLAF-002)\n" +
                    "  O   Cercle bleu     = POUSSIERES (FPLAF-003)\n";
            if (zone == "5" || zone == "all")
                summary +=
                    "  Cercle orange plein  = MANUTENTION equipement lourd (CHANT-001)\n" +
                    "  Carre rouge plein    = ACCES ELECTRIQUE habilitation requise (CHANT-002)\n" +
                    "  Triangle jaune plein = TRAVAIL EN HAUTEUR (CHANT-003)\n" +
                    "  Losange rouge plein  = GAINE ASCENSEUR danger chute (CHANT-004)\n" +
                    "  Pentagone cyan plein = VENTILATION locale requise (CHANT-005)\n";

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
                form.Text = "BIM Conformite - Analyse";
                form.Size = new System.Drawing.Size(420, 240);
                form.StartPosition = FormStartPosition.CenterScreen;
                form.FormBorderStyle = FormBorderStyle.FixedDialog;
                form.MaximizeBox = false;
                form.MinimizeBox = false;

                var label = new Label
                {
                    Text = "Selectionnez la categorie a analyser :",
                    Location = new System.Drawing.Point(20, 20),
                    Size = new System.Drawing.Size(370, 25),
                    Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold)
                };

                var radioButtons = new RadioButton[]
                {
                    new RadioButton { Text = "Risques Chantier (CHANT-001 a 005)", Location = new System.Drawing.Point(30, 60), Size = new System.Drawing.Size(350, 25), Checked = true },
                    new RadioButton { Text = "Autre (Locaux Elec, Gaines, Faux Plafonds, Planchers)", Location = new System.Drawing.Point(30, 95), Size = new System.Drawing.Size(350, 25) },
                };

                var btnOk = new Button
                {
                    Text = "Analyser",
                    DialogResult = DialogResult.OK,
                    Location = new System.Drawing.Point(170, 145),
                    Size = new System.Drawing.Size(90, 35),
                    Font = new System.Drawing.Font("Segoe UI", 9, System.Drawing.FontStyle.Bold)
                };

                var btnCancel = new Button
                {
                    Text = "Annuler",
                    DialogResult = DialogResult.Cancel,
                    Location = new System.Drawing.Point(270, 145),
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
                    // Radio 0 = Risques Chantier → zone "5"
                    // Radio 1 = Autre → ouvre une 2ème fenêtre avec les autres catégories
                    if (radioButtons[0].Checked) return "5";
                    if (radioButtons[1].Checked) return ShowOtherCategoriesDialog();
                }

                return null;
            }
        }

        private string ShowOtherCategoriesDialog()
        {
            using (var form = new System.Windows.Forms.Form())
            {
                form.Text = "BIM Conformite - Autre categorie";
                form.Size = new System.Drawing.Size(420, 310);
                form.StartPosition = FormStartPosition.CenterScreen;
                form.FormBorderStyle = FormBorderStyle.FixedDialog;
                form.MaximizeBox = false;
                form.MinimizeBox = false;

                var label = new Label
                {
                    Text = "Selectionnez la categorie a analyser :",
                    Location = new System.Drawing.Point(20, 20),
                    Size = new System.Drawing.Size(370, 25),
                    Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold)
                };

                var radioButtons = new RadioButton[]
                {
                    new RadioButton { Text = "Locaux Electriques (ELEC-001 a 004)",          Location = new System.Drawing.Point(30, 55),  Size = new System.Drawing.Size(350, 25), Checked = true },
                    new RadioButton { Text = "Gaines Techniques (GAINE-001 a 005)",           Location = new System.Drawing.Point(30, 85),  Size = new System.Drawing.Size(350, 25) },
                    new RadioButton { Text = "Faux Plafonds Techniques (FPLAF-001 a 003)",    Location = new System.Drawing.Point(30, 115), Size = new System.Drawing.Size(350, 25) },
                    new RadioButton { Text = "Planchers Techniques (PLAN-001 a 005)",         Location = new System.Drawing.Point(30, 145), Size = new System.Drawing.Size(350, 25) },
                    new RadioButton { Text = "Toutes les categories",                          Location = new System.Drawing.Point(30, 175), Size = new System.Drawing.Size(350, 25) },
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
                    if (radioButtons[0].Checked) return "1";
                    if (radioButtons[1].Checked) return "2";
                    if (radioButtons[2].Checked) return "3";
                    if (radioButtons[3].Checked) return "4";
                    if (radioButtons[4].Checked) return "all";
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
                { "GAINE-001", new Color(200, 0, 0) },     // Rouge fonce  - Losange  (chute objets)
                { "GAINE-002", new Color(255, 0, 255) },   // Magenta      - Cercle   (croisement CF/CFA)
                { "GAINE-003", new Color(0, 150, 0) },     // Vert         - Triangle (trappes acces)
                { "GAINE-004", new Color(180, 100, 0) },   // Marron       - Croix    (surcharge supports)
                { "GAINE-005", new Color(100, 0, 180) }    // Violet       - Carre    (calcul charge)
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

            // Determiner la plage Z (en metres) automatiquement depuis Revit
            double zMinM = double.MinValue;
            double zMaxM = double.MaxValue;

            var levelRangesAnnot = BuildLevelRanges(doc);
            ViewPlan vp2 = view as ViewPlan;
            if (vp2 != null && vp2.GenLevel != null)
            {
                if (levelRangesAnnot.ContainsKey(vp2.GenLevel.Id))
                {
                    var range = levelRangesAnnot[vp2.GenLevel.Id];
                    zMinM = range.zMin;
                    zMaxM = range.zMax;
                }
                else
                {
                    // Fallback si niveau non trouve
                    double elev = vp2.GenLevel.Elevation * 0.3048;
                    zMinM = elev - 1.5;
                    zMaxM = elev + 4.5;
                }
            }

            // Chercher un TextNoteType pour les labels
            TextNoteType noteType = GetSmallestNoteType(doc);

            // Detecter le document ARCHI (contient les rooms/espaces)
            Document docArchiAnnot = null;
            RevitLinkInstance archiLinkInst = null;
            foreach (RevitLinkInstance li in new FilteredElementCollector(doc).OfClass(typeof(RevitLinkInstance)))
            {
                Document ld = li.GetLinkDocument();
                if (ld == null) continue;
                string lt = ld.Title.ToLower();
                if (lt.Contains("arc") || lt.Contains("archi")) { docArchiAnnot = ld; archiLinkInst = li; break; }
            }

            // Construire index name -> SpaceData
            var spaceByNameAnnot = new Dictionary<string, SpaceData>();
            foreach (var sp in data.Spaces)
                if (sp.Name != null && !spaceByNameAnnot.ContainsKey(sp.Name)) spaceByNameAnnot[sp.Name] = sp;

            // Regrouper violations par espace (pour GAINE-001/002/003 basees sur les espaces)
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

                // GAINE-004 et GAINE-005 : dessiner chaque violation individuellement
                // (space_name = nom du cable, pas d'un espace => position directe)
                bool isPerViolation = violations.All(v =>
                    v.RuleId == "GAINE-004" || v.RuleId == "GAINE-005");

                if (isPerViolation)
                {
                    foreach (var v in violations)
                    {
                        double[] loc = v.Location;
                        if (loc == null || loc.Length < 2) continue;
                        if (loc[0] == 0 && loc[1] == 0) continue;

                        double zM = loc.Length >= 3 ? loc[2] : double.NaN;
                        if (double.IsNaN(zM) || zM < zMinM || zM > zMaxM) continue;

                        double x = loc[0] / 0.3048;
                        double y = loc[1] / 0.3048;
                        XYZ center = new XYZ(x, y, 0);

                        GraphicsStyle gs = lineStyles.ContainsKey(v.RuleId) ? lineStyles[v.RuleId] : null;
                        double s = 2.0; // plus grand pour mieux voir (~60cm)

                        try
                        {
                            if (v.RuleId == "GAINE-004")
                                DrawCrossSymbol(doc, view, center, s, gs);
                            else
                                DrawSquareSymbol(doc, view, center, s, gs);
                            count++;
                        }
                        catch { }
                    }
                    continue;
                }

                // Pour les autres règles : logique par espace (GAINE-001/002/003, ELEC-xxx)
                double zMspace = double.NaN;
                if (violations.Count > 0 && violations[0].Location != null && violations[0].Location.Length >= 3)
                    zMspace = violations[0].Location[2];
                else
                {
                    double[] loc0 = FindSpaceLocation(data, spaceName);
                    if (loc0 != null && loc0.Length >= 3) zMspace = loc0[2];
                }
                if (double.IsNaN(zMspace)) continue;
                if (zMspace < zMinM || zMspace > zMaxM) continue;

                // Trouver la position Revit reelle via revit_element_id
                double xs = double.NaN, ys = double.NaN;
                SpaceData spData = spaceByNameAnnot.ContainsKey(spaceName) ? spaceByNameAnnot[spaceName] : null;
                if (spData != null && spData.RevitElementId > 0)
                {
                    ElementId eid = new ElementId(spData.RevitElementId);
                    Element elem = null;
                    if (docArchiAnnot != null) elem = docArchiAnnot.GetElement(eid);
                    if (elem == null) elem = doc.GetElement(eid);
                    if (elem != null)
                    {
                        XYZ pos = null;
                        LocationPoint lp = elem.Location as LocationPoint;
                        if (lp != null) pos = lp.Point;
                        else { BoundingBoxXYZ bb = elem.get_BoundingBox(null); if (bb != null) pos = (bb.Min + bb.Max) / 2; }
                        if (pos != null) { xs = pos.X; ys = pos.Y; }
                    }
                }
                // Fallback location directe
                if ((double.IsNaN(xs) || double.IsNaN(ys)) && violations.Count > 0)
                {
                    double[] loc = violations[0].Location;
                    if (loc != null && loc.Length >= 2 && (loc[0] != 0 || loc[1] != 0))
                    {
                        xs = loc[0] / 0.3048;
                        ys = loc[1] / 0.3048;
                    }
                }
                if (double.IsNaN(xs) || double.IsNaN(ys)) continue;

                // Identifier les regles distinctes dans cet espace
                var rulesInSpace = new HashSet<string>();
                foreach (var v in violations)
                    if (v.RuleId != null) rulesInSpace.Add(v.RuleId);

                int symbolIndex = 0;
                foreach (string ruleId in rulesInSpace)
                {
                    double offsetX = symbolIndex * SYMBOL_SPACING;
                    XYZ center = new XYZ(xs + offsetX, ys, 0);

                    int ruleCount = violations.Count(v => v.RuleId == ruleId);
                    string label = GetSymbolLabel(ruleId, ruleCount);

                    GraphicsStyle gs = lineStyles.ContainsKey(ruleId) ? lineStyles[ruleId] : null;

                    try
                    {
                        double s = 1.5; // taille du symbole en pieds (~45cm)

                        switch (ruleId)
                        {
                            case "ELEC-001":
                            case "ELEC-002":
                            case "ELEC-003":
                            case "ELEC-004":
                                break;
                            case "GAINE-001":
                                DrawDiamondSymbol(doc, view, center, s, gs);
                                break;
                            case "GAINE-002":
                                DrawCircleSymbol(doc, view, center, s, gs);
                                break;
                            case "GAINE-003":
                                DrawTriangleSymbol(doc, view, center, s, gs);
                                break;
                            // ── Catégorie 5 — Risques Chantier ──────────────
                            case "CHANT-001":
                                DrawArrowSymbol(doc, view, center, s, gs);
                                break;
                            case "CHANT-002":
                                DrawLightningSymbol(doc, view, center, s, gs);
                                break;
                            case "CHANT-003":
                                DrawHelmetSymbol(doc, view, center, s, gs);
                                break;
                            case "CHANT-004":
                                DrawForbiddenSymbol(doc, view, center, s, gs);
                                break;
                            case "CHANT-005":
                                DrawVentSymbol(doc, view, center, s, gs);
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

        /// Accepte silencieusement le chargement de famille sans boite de dialogue
        private class SilentFamilyLoadOptions : IFamilyLoadOptions
        {
            public bool OnFamilyFound(bool familyInUse, out bool overwriteParameterValues)
            { overwriteParameterValues = false; return true; }
            public bool OnSharedFamilyFound(Family sharedFamily, bool familyInUse,
                out FamilySource source, out bool overwriteParameterValues)
            { source = FamilySource.Family; overwriteParameterValues = false; return true; }
        }

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

            // 2. Trouver le fichier .rfa dans le dossier ELEC/
            string rfaPath = Path.Combine(PROJECT_DIR, "RevitPlugin", "Families", FAMILIES_ELEC_DIR, RISK_FAMILY_RFA);

            if (!File.Exists(rfaPath)) return null;

            // 3. Charger la famille sans boite de dialogue (IFamilyLoadOptions)
            Family family = null;
            bool loaded = doc.LoadFamily(rfaPath, new SilentFamilyLoadOptions(), out family);

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

        // Charge ou recupere une famille par nom, depuis un chemin RFA
        private FamilySymbol LoadOrGetFamily(Document doc, string familyName, string rfaPath)
        {
            FamilySymbol existing = new FilteredElementCollector(doc)
                .OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>()
                .FirstOrDefault(fs => fs.FamilyName == familyName);
            if (existing != null)
            {
                if (!existing.IsActive) existing.Activate();
                return existing;
            }
            if (!File.Exists(rfaPath)) return null;
            Family family = null;
            doc.LoadFamily(rfaPath, new SilentFamilyLoadOptions(), out family);
            if (family == null)
            {
                existing = new FilteredElementCollector(doc)
                    .OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>()
                    .FirstOrDefault(fs => fs.FamilyName == familyName);
                if (existing != null && !existing.IsActive) existing.Activate();
                return existing;
            }
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

        /// <summary>Croix (+) avec cercle interieur — GAINE-004 Surcharge supports (marron)</summary>
        private void DrawCrossSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
        {
            double s = size;
            // Bras horizontaux et verticaux
            DrawLineInView(doc, view, new XYZ(center.X - s, center.Y, 0), new XYZ(center.X + s, center.Y, 0), gs);
            DrawLineInView(doc, view, new XYZ(center.X, center.Y - s, 0), new XYZ(center.X, center.Y + s, 0), gs);
            // Petit cercle au centre pour distinguer de la croix simple
            int seg = 8;
            double r = s * 0.35;
            for (int i = 0; i < seg; i++)
            {
                double a1 = 2 * Math.PI * i / seg;
                double a2 = 2 * Math.PI * (i + 1) / seg;
                DrawLineInView(doc, view,
                    new XYZ(center.X + r * Math.Cos(a1), center.Y + r * Math.Sin(a1), 0),
                    new XYZ(center.X + r * Math.Cos(a2), center.Y + r * Math.Sin(a2), 0), gs);
            }
        }

        /// <summary>Carre avec diagonales — GAINE-005 Calcul charge (violet)</summary>
        private void DrawSquareSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
        {
            double s = size * 0.85;
            XYZ tl = new XYZ(center.X - s, center.Y + s, 0);
            XYZ tr = new XYZ(center.X + s, center.Y + s, 0);
            XYZ br = new XYZ(center.X + s, center.Y - s, 0);
            XYZ bl = new XYZ(center.X - s, center.Y - s, 0);
            // Contour du carre
            DrawLineInView(doc, view, tl, tr, gs);
            DrawLineInView(doc, view, tr, br, gs);
            DrawLineInView(doc, view, br, bl, gs);
            DrawLineInView(doc, view, bl, tl, gs);
            // Diagonale (symbole de charge)
            DrawLineInView(doc, view, tl, br, gs);
        }

        // ── Symboles CHANT — FilledRegion pleins et colorés ───────────────────

        /// <summary>Cercle plein orange — CHANT-001 Manutention</summary>
        private void DrawArrowSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
            => DrawFilledCircle(doc, view, center, size * 0.85, new Color(230, 130, 0));

        /// <summary>Carré plein rouge — CHANT-002 Accès électrique</summary>
        private void DrawLightningSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
            => DrawFilledSquare(doc, view, center, size * 0.85, new Color(200, 30, 30));

        /// <summary>Triangle plein jaune/or — CHANT-003 Travail en hauteur</summary>
        private void DrawHelmetSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
            => DrawFilledTriangle(doc, view, center, size * 0.85, new Color(220, 160, 0));

        /// <summary>Losange plein rouge foncé — CHANT-004 Gaine ascenseur</summary>
        private void DrawForbiddenSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
            => DrawFilledDiamond(doc, view, center, size * 0.85, new Color(160, 0, 0));

        /// <summary>Pentagone plein cyan — CHANT-005 Ventilation</summary>
        private void DrawVentSymbol(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, GraphicsStyle gs)
            => DrawFilledPentagon(doc, view, center, size * 0.85, new Color(40, 160, 180));

        // ── Helpers FilledRegion ──────────────────────────────────────────────

        private void DrawFilledRegion(Document doc, Autodesk.Revit.DB.View view, IList<XYZ> points, Color fillColor)
        {
            try
            {
                FillPatternElement solidPattern = GetSolidFillPattern(doc);
                if (solidPattern == null) return;

                // Créer ou récupérer un FilledRegionType avec la couleur voulue
                FilledRegionType regionType = GetOrCreateFilledRegionType(doc, fillColor, solidPattern.Id);
                if (regionType == null) return;

                // Construire le CurveLoop à partir des points
                var loop = new CurveLoop();
                for (int i = 0; i < points.Count; i++)
                {
                    XYZ p1 = new XYZ(points[i].X, points[i].Y, 0);
                    XYZ p2 = new XYZ(points[(i + 1) % points.Count].X, points[(i + 1) % points.Count].Y, 0);
                    if (!p1.IsAlmostEqualTo(p2))
                        loop.Append(Line.CreateBound(p1, p2));
                }
                if (loop.NumberOfCurves() < 3) return;

                FilledRegion.Create(doc, regionType.Id, view.Id, new List<CurveLoop> { loop });
            }
            catch { }
        }

        private void DrawFilledCircle(Document doc, Autodesk.Revit.DB.View view, XYZ center, double radius, Color color)
        {
            int seg = 20;
            var pts = new List<XYZ>();
            for (int i = 0; i < seg; i++)
            {
                double a = 2 * Math.PI * i / seg;
                pts.Add(new XYZ(center.X + radius * Math.Cos(a), center.Y + radius * Math.Sin(a), 0));
            }
            DrawFilledRegion(doc, view, pts, color);
        }

        private void DrawFilledSquare(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, Color color)
        {
            double s = size * 0.85;
            var pts = new List<XYZ>
            {
                new XYZ(center.X - s, center.Y + s, 0),
                new XYZ(center.X + s, center.Y + s, 0),
                new XYZ(center.X + s, center.Y - s, 0),
                new XYZ(center.X - s, center.Y - s, 0),
            };
            DrawFilledRegion(doc, view, pts, color);
        }

        private void DrawFilledTriangle(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, Color color)
        {
            var pts = new List<XYZ>
            {
                new XYZ(center.X,              center.Y + size,        0),
                new XYZ(center.X + size * 0.866, center.Y - size * 0.5, 0),
                new XYZ(center.X - size * 0.866, center.Y - size * 0.5, 0),
            };
            DrawFilledRegion(doc, view, pts, color);
        }

        private void DrawFilledDiamond(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, Color color)
        {
            var pts = new List<XYZ>
            {
                new XYZ(center.X,        center.Y + size, 0),
                new XYZ(center.X + size, center.Y,        0),
                new XYZ(center.X,        center.Y - size, 0),
                new XYZ(center.X - size, center.Y,        0),
            };
            DrawFilledRegion(doc, view, pts, color);
        }

        private void DrawFilledPentagon(Document doc, Autodesk.Revit.DB.View view, XYZ center, double size, Color color)
        {
            int n = 5;
            var pts = new List<XYZ>();
            for (int i = 0; i < n; i++)
            {
                double a = Math.PI / 2 + 2 * Math.PI * i / n;
                pts.Add(new XYZ(center.X + size * Math.Cos(a), center.Y + size * Math.Sin(a), 0));
            }
            DrawFilledRegion(doc, view, pts, color);
        }

        private FilledRegionType GetOrCreateFilledRegionType(Document doc, Color color, ElementId patternId)
        {
            string typeName = $"CHANT_{color.Red}_{color.Green}_{color.Blue}";

            // Chercher si ce type existe déjà (créé dans la transaction 1b)
            var existing = new FilteredElementCollector(doc)
                .OfClass(typeof(FilledRegionType))
                .Cast<FilledRegionType>()
                .FirstOrDefault(t => t.Name == typeName);
            if (existing != null) return existing;

            // Créer le type — DOIT être appelé dans une transaction dédiée (pas dans txView)
            var baseType = new FilteredElementCollector(doc)
                .OfClass(typeof(FilledRegionType))
                .Cast<FilledRegionType>()
                .FirstOrDefault();
            if (baseType == null) return null;

            var newType = baseType.Duplicate(typeName) as FilledRegionType;
            if (newType == null) return null;

            newType.ForegroundPatternId    = patternId;
            newType.ForegroundPatternColor = color;
            newType.BackgroundPatternId    = patternId;
            newType.BackgroundPatternColor = color;
            newType.IsMasking              = false;

            return newType;
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
                // Catégorie 5
                case "CHANT-001":
                    return "MANUTENTION (" + count + ")";
                case "CHANT-002":
                    return "ELEC. HABILIT. (" + count + ")";
                case "CHANT-003":
                    return "HAUTEUR (" + count + ")";
                case "CHANT-004":
                    return "GAINE INTERDIT (" + count + ")";
                case "CHANT-005":
                    return "VENTILATION (" + count + ")";
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
