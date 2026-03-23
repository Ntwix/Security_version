using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;

namespace CHU_SecurityAnalyzer.UI
{
    /// <summary>
    /// Formulaire CHANT-001 — Chemin d'accès pour manutention d'équipements lourds.
    /// L'utilisateur coche chaque obstacle (porte, escalier, ascenseur) sur le chemin
    /// depuis l'entrée du bâtiment jusqu'au local technique.
    /// Le formulaire vérifie en temps réel si chaque obstacle est suffisamment large.
    /// </summary>
    public class Chant001ManutentionDialog : Window
    {
        // ── Données ──────────────────────────────────────────────────────────
        private readonly List<Chant001EquipementLourd> _equipements;
        private readonly List<Chant001Obstacle>        _obstacles;
        // Rows indépendantes par équipement (chaque équipement a ses propres coches)
        private readonly Dictionary<int, List<Chant001ObstacleRow>> _rowsByEquip;
        private int _equipIndex = 0;

        // Raccourci vers les rows de l'équipement courant
        private List<Chant001ObstacleRow> CurrentRows =>
            _rowsByEquip.TryGetValue(_equipIndex, out var r) ? r : new List<Chant001ObstacleRow>();

        /// <summary>Violations détectées après validation (une par obstacle trop étroit coché)</summary>
        public List<Chant001ViolationResult> ViolationResults { get; private set; } = new List<Chant001ViolationResult>();

        // ── Contrôles ────────────────────────────────────────────────────────
        private TextBlock   _lblEquipInfo;
        private TextBlock   _lblEquipDim;
        private DataGrid    _grid;
        private TextBlock   _lblResult;
        private Border      _resultBorder;
        private Button      _btnPrev;
        private Button      _btnNext;
        private TextBlock   _lblStep;

        // ── Couleurs ─────────────────────────────────────────────────────────
        private static readonly SolidColorBrush BR_WHITE   = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_HEADER  = new SolidColorBrush(Color.FromRgb(230, 230, 230));
        private static readonly SolidColorBrush BR_BORDER  = new SolidColorBrush(Color.FromRgb(180, 180, 180));
        private static readonly SolidColorBrush BR_SEL     = new SolidColorBrush(Color.FromRgb(0, 114, 188));
        private static readonly SolidColorBrush BR_SEL_TXT = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_ALTA    = new SolidColorBrush(Color.FromRgb(245, 245, 245));
        private static readonly SolidColorBrush BR_TEXT    = new SolidColorBrush(Color.FromRgb(30, 30, 30));
        private static readonly SolidColorBrush BR_MUTED   = new SolidColorBrush(Color.FromRgb(100, 100, 100));
        private static readonly SolidColorBrush BR_FOOTER  = new SolidColorBrush(Color.FromRgb(240, 240, 240));
        private static readonly SolidColorBrush BR_OK      = new SolidColorBrush(Color.FromRgb(0, 140, 60));
        private static readonly SolidColorBrush BR_WARN    = new SolidColorBrush(Color.FromRgb(200, 80, 0));
        private static readonly SolidColorBrush BR_OKBG    = new SolidColorBrush(Color.FromRgb(230, 255, 235));
        private static readonly SolidColorBrush BR_WARNBG  = new SolidColorBrush(Color.FromRgb(255, 240, 230));
        private static readonly SolidColorBrush BR_ORANGE  = new SolidColorBrush(Color.FromRgb(255, 140, 0));

        // =====================================================================
        //  CONSTRUCTEUR
        // =====================================================================
        public Chant001ManutentionDialog(
            List<Chant001EquipementLourd> equipements,
            List<Chant001Obstacle> obstacles)
        {
            Title                 = "CHANT-001 — Vérification chemin d'accès manutention";
            Width                 = 820;
            Height                = 580;
            MinWidth              = 680;
            MinHeight             = 440;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode            = ResizeMode.CanResize;
            Background            = BR_WHITE;
            FontFamily            = new FontFamily("Segoe UI");
            FontSize              = 12;

            _equipements  = equipements ?? new List<Chant001EquipementLourd>();
            _obstacles    = obstacles   ?? new List<Chant001Obstacle>();
            _rowsByEquip  = new Dictionary<int, List<Chant001ObstacleRow>>();

            // Créer des rows INDÉPENDANTES pour chaque équipement
            // + filtrer les obstacles selon le niveau de l'équipement
            for (int i = 0; i < _equipements.Count; i++)
            {
                var eq = _equipements[i];
                double equipZ = eq.Location != null && eq.Location.Length >= 3 ? eq.Location[2] : 0;
                // Garder obstacles entre le RDC et le niveau de l'équipement (+1 étage de marge)
                double zMin = Math.Min(0, equipZ) - 1.0;   // RDC ou sous-sol
                double zMax = Math.Max(0, equipZ) + 4.0;   // niveau équip + 1 étage de marge

                _rowsByEquip[i] = _obstacles
                    .Where(o =>
                    {
                        double oz = o.Location != null && o.Location.Length >= 3 ? o.Location[2] : 0;
                        return oz >= zMin && oz <= zMax;
                    })
                    .Select(o => new Chant001ObstacleRow(o))
                    .ToList();

                // Si aucun obstacle filtré, prendre tous (fallback)
                if (_rowsByEquip[i].Count == 0)
                    _rowsByEquip[i] = _obstacles.Select(o => new Chant001ObstacleRow(o)).ToList();
            }
            // Si aucun équipement, créer quand même une liste vide
            if (_equipements.Count == 0)
                _rowsByEquip[0] = new List<Chant001ObstacleRow>();

            BuildUI();
            RefreshEquipInfo();
        }

        // =====================================================================
        //  CONSTRUCTION UI
        // =====================================================================
        private void BuildUI()
        {
            var root = new Grid();
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // en-tête bleu
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // info équipement
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // barre navigation équipement
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) }); // grille
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // résultat temps réel
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // note
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // boutons

            // ── En-tête bleu ─────────────────────────────────────────────────
            var header = new Border
            {
                Background = BR_SEL,
                Padding    = new Thickness(14, 10, 14, 10)
            };
            var headerStack = new StackPanel();
            headerStack.Children.Add(new TextBlock
            {
                Text       = "CHANT-001 — Manutention des équipements lourds",
                FontSize   = 14,
                FontWeight = FontWeights.Bold,
                Foreground = BR_WHITE
            });
            headerStack.Children.Add(new TextBlock
            {
                Text       = "Cochez chaque obstacle sur le chemin depuis l'entrée jusqu'au local technique.",
                FontSize   = 11,
                Foreground = new SolidColorBrush(Color.FromRgb(180, 210, 255)),
                Margin     = new Thickness(0, 3, 0, 0)
            });
            header.Child = headerStack;
            Grid.SetRow(header, 0);
            root.Children.Add(header);

            // ── Info équipement ───────────────────────────────────────────────
            var equipBorder = new Border
            {
                Background      = new SolidColorBrush(Color.FromRgb(255, 248, 225)),
                BorderBrush     = BR_ORANGE,
                BorderThickness = new Thickness(0, 0, 0, 2),
                Padding         = new Thickness(14, 8, 14, 8)
            };
            var equipGrid = new Grid();
            equipGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            equipGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var equipLeft = new StackPanel();
            equipLeft.Children.Add(new TextBlock
            {
                Text       = "Équipement à livrer :",
                FontSize   = 11,
                Foreground = BR_MUTED
            });
            _lblEquipInfo = new TextBlock
            {
                FontSize   = 13,
                FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT
            };
            equipLeft.Children.Add(_lblEquipInfo);
            Grid.SetColumn(equipLeft, 0);
            equipGrid.Children.Add(equipLeft);

            _lblEquipDim = new TextBlock
            {
                FontSize            = 12,
                FontWeight          = FontWeights.Bold,
                Foreground          = BR_ORANGE,
                VerticalAlignment   = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin              = new Thickness(10, 0, 0, 0)
            };
            Grid.SetColumn(_lblEquipDim, 1);
            equipGrid.Children.Add(_lblEquipDim);

            equipBorder.Child = equipGrid;
            Grid.SetRow(equipBorder, 1);
            root.Children.Add(equipBorder);

            // ── Navigation équipement (si plusieurs) ─────────────────────────
            var navBar = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(10, 5, 10, 5)
            };
            var navPanel = new StackPanel { Orientation = Orientation.Horizontal };

            _btnPrev = new Button
            {
                Content         = "◀ Précédent",
                Width           = 100, Height = 24,
                Margin          = new Thickness(0, 0, 8, 0),
                Background      = BR_WHITE, BorderBrush = BR_BORDER,
                Foreground      = BR_TEXT, Cursor = Cursors.Hand
            };
            _btnPrev.Click += (s, e) => { if (_equipIndex > 0) { _equipIndex--; RefreshEquipInfo(); } };
            navPanel.Children.Add(_btnPrev);

            _lblStep = new TextBlock
            {
                VerticalAlignment = VerticalAlignment.Center,
                Foreground        = BR_MUTED,
                Margin            = new Thickness(0, 0, 8, 0)
            };
            navPanel.Children.Add(_lblStep);

            _btnNext = new Button
            {
                Content         = "Suivant ▶",
                Width           = 100, Height = 24,
                Background      = BR_WHITE, BorderBrush = BR_BORDER,
                Foreground      = BR_TEXT, Cursor = Cursors.Hand
            };
            _btnNext.Click += (s, e) => { if (_equipIndex < _equipements.Count - 1) { _equipIndex++; RefreshEquipInfo(); } };
            navPanel.Children.Add(_btnNext);

            navBar.Child = navPanel;
            Grid.SetRow(navBar, 2);
            root.Children.Add(navBar);

            // ── DataGrid obstacles ────────────────────────────────────────────
            var gridBorder = new Border
            {
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(1),
                Margin          = new Thickness(12, 6, 12, 0)
            };

            _grid = new DataGrid
            {
                AutoGenerateColumns      = false,
                CanUserAddRows           = false,
                CanUserDeleteRows        = false,
                CanUserResizeRows        = false,
                HeadersVisibility        = DataGridHeadersVisibility.Column,
                SelectionMode            = DataGridSelectionMode.Single,
                GridLinesVisibility      = DataGridGridLinesVisibility.Horizontal,
                HorizontalGridLinesBrush = BR_BORDER,
                Background               = BR_WHITE,
                RowBackground            = BR_WHITE,
                AlternatingRowBackground = BR_ALTA,
                BorderThickness          = new Thickness(0),
                ColumnHeaderHeight       = 28,
                RowHeight                = 26,
                FontSize                 = 12,
                Foreground               = BR_TEXT,
            };

            var headerStyle = new Style(typeof(DataGridColumnHeader));
            headerStyle.Setters.Add(new Setter(BackgroundProperty,      BR_HEADER));
            headerStyle.Setters.Add(new Setter(ForegroundProperty,      BR_TEXT));
            headerStyle.Setters.Add(new Setter(FontWeightProperty,      FontWeights.SemiBold));
            headerStyle.Setters.Add(new Setter(BorderBrushProperty,     BR_BORDER));
            headerStyle.Setters.Add(new Setter(BorderThicknessProperty, new Thickness(0, 0, 1, 1)));
            headerStyle.Setters.Add(new Setter(PaddingProperty,         new Thickness(6, 0, 6, 0)));
            _grid.ColumnHeaderStyle = headerStyle;

            // Colonne checkbox "Sur le chemin"
            var chkCol = new DataGridTemplateColumn
            {
                Header = "Sur le chemin",
                Width  = new DataGridLength(90),
                CanUserResize = false,
                CanUserSort   = false,
            };
            var chkFactory = new FrameworkElementFactory(typeof(CheckBox));
            chkFactory.SetBinding(ToggleButton.IsCheckedProperty,
                new Binding("OnPath") { Mode = BindingMode.TwoWay, UpdateSourceTrigger = UpdateSourceTrigger.PropertyChanged });
            chkFactory.SetValue(HorizontalAlignmentProperty, HorizontalAlignment.Center);
            chkFactory.SetValue(VerticalAlignmentProperty,   VerticalAlignment.Center);
            chkFactory.AddHandler(ToggleButton.CheckedEvent,   new RoutedEventHandler((s, e) => RefreshResult()));
            chkFactory.AddHandler(ToggleButton.UncheckedEvent, new RoutedEventHandler((s, e) => RefreshResult()));
            chkCol.CellTemplate = new DataTemplate { VisualTree = chkFactory };
            _grid.Columns.Add(chkCol);

            // Colonne Type (icône)
            var typeCol = new DataGridTemplateColumn
            {
                Header = "Type",
                Width  = new DataGridLength(90),
            };
            var typeFactory = new FrameworkElementFactory(typeof(TextBlock));
            typeFactory.SetBinding(TextBlock.TextProperty,       new Binding("TypeIcon"));
            typeFactory.SetBinding(TextBlock.ForegroundProperty, new Binding("TypeColor"));
            typeFactory.SetValue(FontWeightProperty,             FontWeights.Bold);
            typeFactory.SetValue(VerticalAlignmentProperty,      VerticalAlignment.Center);
            typeFactory.SetValue(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0));
            typeCol.CellTemplate = new DataTemplate { VisualTree = typeFactory };
            _grid.Columns.Add(typeCol);

            // Colonne Nom
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Nom / Emplacement",
                Binding = new Binding("Name"),
                Width   = new DataGridLength(1, DataGridLengthUnitType.Star),
            });

            // Colonne Niveau (étage calculé depuis Z)
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Niveau",
                Binding = new Binding("NiveauLabel"),
                Width   = new DataGridLength(85),
            });

            // Colonne Espace associé (space_name depuis Python)
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Espace associé",
                Binding = new Binding("SpaceName"),
                Width   = new DataGridLength(150),
            });

            // Colonne Largeur disponible
            var widthCol = new DataGridTemplateColumn
            {
                Header = "Largeur disponible",
                Width  = new DataGridLength(130),
            };
            var widthFactory = new FrameworkElementFactory(typeof(TextBlock));
            widthFactory.SetBinding(TextBlock.TextProperty,       new Binding("WidthLabel"));
            widthFactory.SetBinding(TextBlock.ForegroundProperty, new Binding("WidthColor"));
            widthFactory.SetValue(FontWeightProperty,             FontWeights.SemiBold);
            widthFactory.SetValue(VerticalAlignmentProperty,      VerticalAlignment.Center);
            widthFactory.SetValue(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0));
            widthCol.CellTemplate = new DataTemplate { VisualTree = widthFactory };
            _grid.Columns.Add(widthCol);

            // Colonne Statut (OK / BLOQUANT)
            var statusCol = new DataGridTemplateColumn
            {
                Header = "Statut",
                Width  = new DataGridLength(90),
            };
            var statusFactory = new FrameworkElementFactory(typeof(TextBlock));
            statusFactory.SetBinding(TextBlock.TextProperty,       new Binding("StatusLabel"));
            statusFactory.SetBinding(TextBlock.ForegroundProperty, new Binding("StatusColor"));
            statusFactory.SetValue(FontWeightProperty,             FontWeights.Bold);
            statusFactory.SetValue(VerticalAlignmentProperty,      VerticalAlignment.Center);
            statusFactory.SetValue(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0));
            statusCol.CellTemplate = new DataTemplate { VisualTree = statusFactory };
            _grid.Columns.Add(statusCol);

            _grid.ItemsSource = CurrentRows;
            gridBorder.Child  = _grid;
            Grid.SetRow(gridBorder, 3);
            root.Children.Add(gridBorder);

            // ── Résultat en temps réel ────────────────────────────────────────
            _resultBorder = new Border
            {
                Background      = BR_OKBG,
                BorderBrush     = BR_OK,
                BorderThickness = new Thickness(0, 2, 0, 0),
                Padding         = new Thickness(14, 8, 14, 8),
                Margin          = new Thickness(0, 4, 0, 0)
            };
            _lblResult = new TextBlock
            {
                FontSize     = 12,
                FontWeight   = FontWeights.SemiBold,
                Foreground   = BR_OK,
                TextWrapping = TextWrapping.Wrap
            };
            _resultBorder.Child = _lblResult;
            Grid.SetRow(_resultBorder, 4);
            root.Children.Add(_resultBorder);

            // ── Note bas ─────────────────────────────────────────────────────
            var noteBorder = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 0),
                Padding         = new Thickness(14, 6, 14, 6)
            };
            noteBorder.Child = new TextBlock
            {
                Text       = "Cochez uniquement les obstacles réellement sur le chemin d'accès depuis l'entrée principale du bâtiment.",
                FontSize   = 11,
                Foreground = BR_MUTED,
                TextWrapping = TextWrapping.Wrap
            };
            Grid.SetRow(noteBorder, 5);
            root.Children.Add(noteBorder);

            // ── Boutons ───────────────────────────────────────────────────────
            var btnBar = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 0),
                Padding         = new Thickness(14, 8, 14, 8)
            };
            var btnPanel = new StackPanel
            {
                Orientation         = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right
            };
            btnPanel.Children.Add(MakeBtn("Valider", true,  OnOK));
            btnPanel.Children.Add(MakeBtn("Ignorer", false, OnCancel));
            btnBar.Child = btnPanel;
            Grid.SetRow(btnBar, 6);
            root.Children.Add(btnBar);

            Content = root;
            RefreshResult();
        }

        // =====================================================================
        //  LOGIQUE
        // =====================================================================

        private void RefreshEquipInfo()
        {
            if (_equipements.Count == 0)
            {
                _lblEquipInfo.Text = "Aucun équipement";
                _lblEquipDim.Text  = "";
                return;
            }

            var eq = _equipements[_equipIndex];
            _lblEquipInfo.Text = $"{eq.Name}  →  Local : {eq.LocalName}";
            _lblEquipDim.Text  = $"Dim. max : {eq.DimMaxM:F2} m";

            // Mettre à jour couleurs statut en fonction de l'équipement courant
            foreach (var row in CurrentRows)
                row.SetEquipDimMax(eq.DimMaxM);

            _grid.ItemsSource = null;
            _grid.ItemsSource = CurrentRows;

            _lblStep.Text = $"Équipement {_equipIndex + 1} / {_equipements.Count}";
            _btnPrev.IsEnabled = _equipIndex > 0;
            _btnNext.IsEnabled = _equipIndex < _equipements.Count - 1;

            RefreshResult();
        }

        private void RefreshResult()
        {
            if (_equipements.Count == 0) return;

            var eq = _equipements[_equipIndex];
            var blocked = CurrentRows.Where(r => r.OnPath && r.IsBlocking(eq.DimMaxM)).ToList();
            var onPath  = CurrentRows.Where(r => r.OnPath).ToList();

            if (onPath.Count == 0)
            {
                _lblResult.Text      = "ℹ  Cochez les obstacles sur le chemin pour voir le résultat.";
                _lblResult.Foreground = BR_MUTED;
                _resultBorder.Background  = BR_FOOTER;
                _resultBorder.BorderBrush = BR_BORDER;
            }
            else if (blocked.Count == 0)
            {
                _lblResult.Text      = $"✔  Chemin libre — tous les obstacles cochés ({onPath.Count}) sont suffisamment larges pour {eq.Name}.";
                _lblResult.Foreground = BR_OK;
                _resultBorder.Background  = BR_OKBG;
                _resultBorder.BorderBrush = BR_OK;
            }
            else
            {
                string names = string.Join(", ", blocked.Select(b => $"{b.Name} ({b.WidthLabel})"));
                _lblResult.Text      = $"⚠  BLOCAGE détecté — {blocked.Count} obstacle(s) trop étroit(s) : {names}";
                _lblResult.Foreground = BR_WARN;
                _resultBorder.Background  = BR_WARNBG;
                _resultBorder.BorderBrush = BR_WARN;
            }
        }

        private void OnOK(object sender, RoutedEventArgs e)
        {
            ViolationResults.Clear();

            for (int i = 0; i < _equipements.Count; i++)
            {
                var eq   = _equipements[i];
                var rows = _rowsByEquip.TryGetValue(i, out var r) ? r : new List<Chant001ObstacleRow>();
                var blocked = rows.Where(row => row.OnPath && row.IsBlocking(eq.DimMaxM)).ToList();
                foreach (var obs in blocked)
                {
                    ViolationResults.Add(new Chant001ViolationResult
                    {
                        EquipementName = eq.Name,
                        LocalName      = eq.LocalName,
                        LocalGlobalId  = eq.LocalGlobalId,
                        ObstacleName   = obs.Name,
                        ObstacleType   = obs.Source.Type,
                        ObstacleWidthM = obs.Source.WidthM,
                        EquipDimMaxM   = eq.DimMaxM,
                        Location       = obs.Source.Location
                    });
                }
            }

            DialogResult = true;
            Close();
        }

        private void OnCancel(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        // =====================================================================
        //  HELPERS
        // =====================================================================
        private static Button MakeBtn(string label, bool isDefault, RoutedEventHandler handler)
        {
            var btn = new Button
            {
                Content         = label,
                Width           = 90, Height = 28,
                Margin          = new Thickness(6, 0, 0, 0),
                IsDefault       = isDefault,
                FontSize        = 12,
                Cursor          = Cursors.Hand,
                Background      = isDefault ? BR_SEL : BR_WHITE,
                Foreground      = isDefault ? BR_SEL_TXT : BR_TEXT,
                BorderBrush     = isDefault ? BR_SEL : BR_BORDER,
                BorderThickness = new Thickness(1),
            };
            btn.Click += handler;
            return btn;
        }
    }

    // =========================================================================
    //  CLASSES DE DONNÉES
    // =========================================================================

    /// <summary>Équipement lourd à livrer (depuis JSON Python).</summary>
    [System.Runtime.Serialization.DataContract]
    public class Chant001EquipementLourd
    {
        [System.Runtime.Serialization.DataMember(Name = "name")]
        public string Name { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "local_name")]
        public string LocalName { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "local_global_id")]
        public string LocalGlobalId { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "dim_max_m")]
        public double DimMaxM { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "weight_kg")]
        public double WeightKg { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "location")]
        public double[] Location { get; set; }
    }

    /// <summary>Obstacle sur le chemin d'accès (porte, escalier, ascenseur).</summary>
    [System.Runtime.Serialization.DataContract]
    public class Chant001Obstacle
    {
        [System.Runtime.Serialization.DataMember(Name = "type")]
        public string Type { get; set; }   // "porte" | "escalier" | "ascenseur"

        [System.Runtime.Serialization.DataMember(Name = "name")]
        public string Name { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "global_id")]
        public string GlobalId { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "width_m")]
        public double WidthM { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "location")]
        public double[] Location { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "space_name")]
        public string SpaceName { get; set; }
    }

    /// <summary>Résultat de violation détecté par le formulaire.</summary>
    public class Chant001ViolationResult
    {
        public string   EquipementName  { get; set; }
        public string   LocalName       { get; set; }
        public string   LocalGlobalId   { get; set; }
        public string   ObstacleName    { get; set; }
        public string   ObstacleType    { get; set; }
        public double   ObstacleWidthM  { get; set; }
        public double   EquipDimMaxM    { get; set; }
        public double[] Location        { get; set; }
    }

    /// <summary>Ligne de la grille DataGrid pour un obstacle.</summary>
    public class Chant001ObstacleRow : System.ComponentModel.INotifyPropertyChanged
    {
        public Chant001Obstacle Source { get; }

        private bool   _onPath;
        private double _equipDimMax;

        private static readonly SolidColorBrush BR_OK_C   = new SolidColorBrush(Color.FromRgb(0, 140, 60));
        private static readonly SolidColorBrush BR_WARN_C  = new SolidColorBrush(Color.FromRgb(200, 80, 0));
        private static readonly SolidColorBrush BR_MUTED_C = new SolidColorBrush(Color.FromRgb(130, 130, 130));
        private static readonly SolidColorBrush BR_PORTE   = new SolidColorBrush(Color.FromRgb(0, 114, 188));
        private static readonly SolidColorBrush BR_ESCAL   = new SolidColorBrush(Color.FromRgb(150, 60, 180));
        private static readonly SolidColorBrush BR_ASCEN   = new SolidColorBrush(Color.FromRgb(0, 150, 136));

        public bool OnPath
        {
            get => _onPath;
            set { _onPath = value; OnPropChanged(nameof(OnPath)); OnPropChanged(nameof(StatusLabel)); OnPropChanged(nameof(StatusColor)); }
        }

        public string Name => Source.Name ?? "Inconnu";

        /// <summary>Étage calculé depuis la coordonnée Z (mètres).</summary>
        public string NiveauLabel
        {
            get
            {
                double z = Source.Location != null && Source.Location.Length >= 3
                    ? Source.Location[2] : 0;
                if (z < -0.5) return "Sous-sol";
                if (z <  0.5) return "RDC";
                if (z <  4.0) return "Niveau 1";
                if (z <  7.5) return "Niveau 2";
                if (z < 11.0) return "Niveau 3";
                if (z < 14.5) return "Niveau 4";
                return $"Niv. {(int)(z / 3.5)}";
            }
        }

        /// <summary>Nom de l'espace associé (depuis Python space_name).</summary>
        public string SpaceName =>
            string.IsNullOrWhiteSpace(Source.SpaceName) ? "—" : Source.SpaceName;

        public string TypeIcon
        {
            get
            {
                switch (Source.Type?.ToLower())
                {
                    case "escalier":  return "🪜 Escalier";
                    case "ascenseur": return "🛗 Ascenseur";
                    default:          return "🚪 Porte";
                }
            }
        }

        public SolidColorBrush TypeColor
        {
            get
            {
                switch (Source.Type?.ToLower())
                {
                    case "escalier":  return BR_ESCAL;
                    case "ascenseur": return BR_ASCEN;
                    default:          return BR_PORTE;
                }
            }
        }

        public string WidthLabel => $"{Source.WidthM:F2} m";

        public SolidColorBrush WidthColor =>
            _equipDimMax > 0 && Source.WidthM < _equipDimMax ? BR_WARN_C : BR_OK_C;

        public bool IsBlocking(double equipDimMax) =>
            Source.WidthM < equipDimMax || Source.WidthM < 0.90;

        public string StatusLabel
        {
            get
            {
                if (!_onPath) return "—";
                return IsBlocking(_equipDimMax) ? "⚠ BLOQUANT" : "✔ OK";
            }
        }

        public SolidColorBrush StatusColor
        {
            get
            {
                if (!_onPath) return BR_MUTED_C;
                return IsBlocking(_equipDimMax) ? BR_WARN_C : BR_OK_C;
            }
        }

        public void SetEquipDimMax(double dimMax)
        {
            _equipDimMax = dimMax;
            OnPropChanged(nameof(WidthColor));
            OnPropChanged(nameof(StatusLabel));
            OnPropChanged(nameof(StatusColor));
        }

        public Chant001ObstacleRow(Chant001Obstacle source)
        {
            Source      = source;
            _onPath     = false;
            _equipDimMax = 0;
        }

        public event System.ComponentModel.PropertyChangedEventHandler PropertyChanged;
        private void OnPropChanged(string name) =>
            PropertyChanged?.Invoke(this, new System.ComponentModel.PropertyChangedEventArgs(name));
    }
}
