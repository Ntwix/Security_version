using System;
using System.IO;
using System.Reflection;
using System.Windows.Media.Imaging;
using Autodesk.Revit.UI;

namespace CHU_SecurityAnalyzer
{
    /// <summary>
    /// Application principale du plugin Revit.
    /// Crée l'onglet "CHU Sécurité" dans le ruban avec les boutons d'analyse.
    /// </summary>
    public class App : IExternalApplication
    {
        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Créer onglet dans le ruban
                string tabName = "CHU Sécurité";
                application.CreateRibbonTab(tabName);

                // Panneau principal
                RibbonPanel panel = application.CreateRibbonPanel(tabName, "Analyse Conformité");

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
                    ToolTip = "Extraire les données BIM et lancer l'analyse de conformité sécurité",
                    LongDescription = "Extrait les données des maquettes ARCHI et ELEC,\n" +
                                     "lance l'analyse Python pour la zone sélectionnée,\n" +
                                     "puis colorie les éléments en violation dans la vue.",
                };

                panel.AddItem(btnAnalyze);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("Erreur Plugin CHU",
                    $"Erreur initialisation plugin:\n{ex.Message}");
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }
    }
}
