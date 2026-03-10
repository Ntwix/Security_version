using System;
using System.IO;
using System.Reflection;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Autodesk.Revit.UI;
using CHU_SecurityAnalyzer.UI;

namespace CHU_SecurityAnalyzer
{
    /// <summary>
    /// Application principale du plugin Revit.
    /// Cree l'onglet "BIM Conformite" dans le ruban avec les boutons d'analyse.
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
                    "Rapport de Conformite",
                    new RiskDockablePane());

                // Creer onglet dans le ruban
                string tabName = "BIM Conformite";
                try { application.CreateRibbonTab(tabName); } catch { }

                // Panneau principal
                RibbonPanel panel = application.CreateRibbonPanel(tabName, "Securite & Risques");

                // Chemin de l'assembly
                string assemblyPath = Assembly.GetExecutingAssembly().Location;

                // === Bouton : Analyser Conformite ===
                var btnAnalyze = new PushButtonData(
                    "cmdAnalyze",
                    "Analyser\nConformite",
                    assemblyPath,
                    "CHU_SecurityAnalyzer.Commands.ExtractAndAnalyzeCommand"
                )
                {
                    ToolTip = "Lancer l'analyse de conformite securite BIM",
                    LongDescription =
                        "Extrait les donnees de la maquette BIM,\n" +
                        "lance l'analyse reglementaire pour la categorie selectionnee\n" +
                        "(Locaux Electriques, Gaines Techniques, ...),\n" +
                        "puis visualise les non-conformites sur les vues de plan.",
                    Image       = CreateIcon16(),
                    LargeImage  = CreateIcon32(),
                };

                panel.AddItem(btnAnalyze);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("Erreur Plugin BIM Conformite",
                    "Erreur initialisation plugin:\n" + ex.Message);
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }

        // ── Icones dessinées programmatiquement ──────────────────────────────
        // Bouclier avec un check : symbole universel de conformite / securite

        private static BitmapSource CreateIcon16()  => DrawShieldIcon(16);
        private static BitmapSource CreateIcon32()  => DrawShieldIcon(32);

        private static BitmapSource DrawShieldIcon(int size)
        {
            int s = size;
            var bmp = new WriteableBitmap(s, s, 96, 96, PixelFormats.Bgra32, null);
            int stride = s * 4;
            byte[] px = new byte[s * stride];

            // Couleurs
            byte[] blue  = { 166,  84,   0, 255 };  // BGRA bleu fonce #0054A6
            byte[] white = { 255, 255, 255, 255 };
            byte[] trans = {   0,   0,   0,   0 };

            // Dessiner pixel par pixel
            for (int y = 0; y < s; y++)
            {
                for (int x = 0; x < s; x++)
                {
                    double nx = (x + 0.5) / s;  // 0..1
                    double ny = (y + 0.5) / s;

                    byte[] col = trans;

                    if (InShield(nx, ny))
                        col = blue;

                    // Check mark blanc (taille adaptee)
                    if (InCheck(nx, ny, s))
                        col = white;

                    int idx = y * stride + x * 4;
                    px[idx]   = col[0];
                    px[idx+1] = col[1];
                    px[idx+2] = col[2];
                    px[idx+3] = col[3];
                }
            }

            bmp.WritePixels(
                new System.Windows.Int32Rect(0, 0, s, s),
                px, stride, 0);
            bmp.Freeze();
            return bmp;
        }

        // Forme bouclier : large en haut, pointe en bas
        private static bool InShield(double nx, double ny)
        {
            // Bords gauche/droite : légèrement arrondis
            double margin = 0.10;
            double halfW  = 0.50 - margin;

            // Partie haute (rectangle arrondi)
            if (ny < 0.55)
            {
                double cx = Math.Abs(nx - 0.5);
                return cx <= halfW;
            }
            // Partie basse : triangle pointu vers le bas
            // La largeur se réduit linéairement de 0.55 à 1.0
            double t    = (ny - 0.55) / 0.45;          // 0..1
            double half = halfW * (1.0 - t);
            return Math.Abs(nx - 0.5) <= half;
        }

        // Check mark : branche courte (bas gauche) + branche longue (haut droit)
        private static bool InCheck(double nx, double ny, int size)
        {
            double thick = size <= 16 ? 0.12 : 0.09;

            // Branche courte : de (0.22,0.55) à (0.40,0.72)
            double d1 = DistToSegment(nx, ny, 0.22, 0.55, 0.40, 0.72);
            // Branche longue : de (0.40,0.72) à (0.74,0.35)
            double d2 = DistToSegment(nx, ny, 0.40, 0.72, 0.74, 0.35);

            return (d1 < thick || d2 < thick)
                   && InShield(nx, ny);
        }

        private static double DistToSegment(
            double px, double py,
            double ax, double ay,
            double bx, double by)
        {
            double dx = bx - ax, dy = by - ay;
            double lenSq = dx*dx + dy*dy;
            if (lenSq < 1e-10) return Math.Sqrt((px-ax)*(px-ax)+(py-ay)*(py-ay));
            double t = Math.Max(0, Math.Min(1, ((px-ax)*dx+(py-ay)*dy)/lenSq));
            double projX = ax + t*dx, projY = ay + t*dy;
            return Math.Sqrt((px-projX)*(px-projX)+(py-projY)*(py-projY));
        }
    }
}
