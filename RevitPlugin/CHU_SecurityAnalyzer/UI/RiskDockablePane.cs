using System;
using Autodesk.Revit.UI;
using CHU_SecurityAnalyzer.Core;

namespace CHU_SecurityAnalyzer.UI
{
    /// <summary>
    /// Fournisseur du panneau dockable "Zones a Risque".
    /// Enregistre le panneau au demarrage et donne acces a la page WPF.
    /// </summary>
    public class RiskDockablePane : IDockablePaneProvider
    {
        public static readonly DockablePaneId PaneId =
            new DockablePaneId(new Guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890"));

        private static RiskPanelPage _page;

        public static RiskPanelPage Page => _page;

        public void SetupDockablePane(DockablePaneProviderData data)
        {
            _page = new RiskPanelPage();
            data.FrameworkElement = _page;
            data.InitialState = new DockablePaneState
            {
                DockPosition = DockPosition.Right,
                MinimumWidth = 260,
                MinimumHeight = 200
            };
        }

        /// <summary>
        /// Affiche ou cree le panneau dockable.
        /// </summary>
        public static void Show(UIApplication uiApp)
        {
            try
            {
                DockablePane pane = uiApp.GetDockablePane(PaneId);
                if (pane != null) pane.Show();
            }
            catch { }
        }

        /// <summary>
        /// Met a jour le contenu du panneau avec les nouveaux resultats.
        /// </summary>
        public static void UpdateResults(UIApplication uiApp, AnalysisResults results, string zone)
        {
            if (_page == null) return;
            _page.Dispatcher.Invoke(() =>
            {
                _page.UiApp = uiApp;
                _page.UpdateResults(results, zone);
            });
            Show(uiApp);
        }
    }
}
