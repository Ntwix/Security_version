using System;
using System.IO;
using System.Reflection;
using System.Windows.Media.Imaging;
using Autodesk.Revit.UI;
using CHU_SecurityAnalyzer.UI;

namespace CHU_SecurityAnalyzer
{
    /// <summary>
    /// Application principale du plugin Revit.
    /// Cree l'onglet "CHU Securite" dans le ruban avec les boutons d'analyse.
    /// </summary>
    public class App : IExternalApplication
    {
        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Enregistrer le panneau dockable avant tout
                application.RegisterDockablePane(
                    RiskDockablePane.PaneId,
                    "CHU - Zones a Risque",
                    new RiskDockablePane());

                // Creer onglet dans le ruban
                string tabName = "CHU Securite";
                try { application.CreateRibbonTab(tabName); } catch { }

                // Panneau principal
                RibbonPanel panel = application.CreateRibbonPanel(tabName, "Analyse Conformite");

                // Chemin de l'assembly
                string assemblyPath = Assembly.GetExecutingAssembly().Location;

                // === Bouton : Analyser Zone ===
                var btnAnalyze = new PushButtonData(
                    "cmdAnalyze",
                    "Analyser\nZone",
                    assemblyPath,
                    "CHU_SecurityAnalyzer.Commands.ExtractAndAnalyzeCommand"
                )
                {
                    ToolTip = "Extraire les donnees BIM et lancer l'analyse de conformite securite",
                    LongDescription = "Extrait les donnees des maquettes ARCHI et ELEC,\n" +
                                     "lance l'analyse Python pour la zone selectionnee,\n" +
                                     "puis colorie les elements en violation dans la vue.",
                };

                panel.AddItem(btnAnalyze);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("Erreur Plugin CHU",
                    "Erreur initialisation plugin:\n" + ex.Message);
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }
    }
}
