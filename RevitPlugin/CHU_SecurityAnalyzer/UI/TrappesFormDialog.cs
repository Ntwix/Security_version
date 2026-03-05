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
    /// Formulaire GAINE-003 — Sélection des équipements nécessitant une trappe d'accès.
    /// Style natif Revit : fond blanc, grille, checkboxes, boutons OK/Annuler.
    /// </summary>
    public class TrappesFormDialog : Window
    {
        // ── Données ──────────────────────────────────────────────────────────
        private readonly List<EquipmentRow> _rows;
        private List<EquipmentRow> _filteredRows;

        /// <summary>Équipements sélectionnés par l'utilisateur (après OK)</summary>
        public List<EquipmentItem> SelectedEquipment { get; private set; } = new List<EquipmentItem>();

        // ── Contrôles ────────────────────────────────────────────────────────
        private TextBox     _txtSearch;
        private DataGrid    _grid;
        private TextBlock   _lblCount;
        private ComboBox    _cmbFilter;

        // ── Couleurs style Revit ─────────────────────────────────────────────
        private static readonly SolidColorBrush BR_WHITE    = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_HEADER   = new SolidColorBrush(Color.FromRgb(230, 230, 230));
        private static readonly SolidColorBrush BR_BORDER   = new SolidColorBrush(Color.FromRgb(180, 180, 180));
        private static readonly SolidColorBrush BR_SEL      = new SolidColorBrush(Color.FromRgb(0, 114, 188));
        private static readonly SolidColorBrush BR_SEL_TXT  = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_ALTA     = new SolidColorBrush(Color.FromRgb(245, 245, 245));
        private static readonly SolidColorBrush BR_TEXT     = new SolidColorBrush(Color.FromRgb(30,  30,  30));
        private static readonly SolidColorBrush BR_MUTED    = new SolidColorBrush(Color.FromRgb(100, 100, 100));
        private static readonly SolidColorBrush BR_PRIORITY = new SolidColorBrush(Color.FromRgb(0,  84, 166));
        private static readonly SolidColorBrush BR_FOOTER   = new SolidColorBrush(Color.FromRgb(240, 240, 240));

        // =====================================================================
        //  CONSTRUCTEUR
        // =====================================================================
        public TrappesFormDialog(List<EquipmentItem> equipmentList, double minWidth, double minHeight)
        {
            Title           = "GAINE-003 — Trappes d'accès aux équipements";
            Width           = 780;
            Height          = 540;
            MinWidth        = 620;
            MinHeight       = 400;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode      = ResizeMode.CanResize;
            Background      = BR_WHITE;
            FontFamily      = new FontFamily("Segoe UI");
            FontSize        = 12;

            _rows = equipmentList.Select(e => new EquipmentRow(e)).ToList();
            _filteredRows = new List<EquipmentRow>(_rows);

            BuildUI(minWidth, minHeight);
            RefreshGrid();
        }

        // =====================================================================
        //  CONSTRUCTION UI
        // =====================================================================
        private void BuildUI(double minWidth, double minHeight)
        {
            var root = new Grid();
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // titre
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // barre recherche/filtre
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // en-tête info
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) }); // grille
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // note bas
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });   // boutons

            // ── Titre ────────────────────────────────────────────────────────
            var titleBorder = new Border
            {
                Background      = BR_WHITE,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(12, 10, 12, 10)
            };
            var titleStack = new StackPanel();
            titleStack.Children.Add(new TextBlock
            {
                Text       = "Sélection des équipements nécessitant une trappe de visite",
                FontSize   = 13,
                FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT
            });
            titleStack.Children.Add(new TextBlock
            {
                Text       = $"Trappe minimale requise : {(int)(minWidth*100)}×{(int)(minHeight*100)} cm  —  "
                           + "Cochez les équipements à traiter puis cliquez OK",
                FontSize   = 11,
                Foreground = BR_MUTED,
                Margin     = new Thickness(0, 3, 0, 0)
            });
            titleBorder.Child = titleStack;
            Grid.SetRow(titleBorder, 0);
            root.Children.Add(titleBorder);

            // ── Barre recherche + filtre ──────────────────────────────────────
            var searchBar = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(12, 7, 12, 7)
            };
            var searchGrid = new Grid();
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(200) });
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(160) });
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            searchGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            // Label recherche
            var lblSearch = new TextBlock
            {
                Text = "Recherche de nom :",
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(0, 0, 8, 0),
                Foreground = BR_TEXT
            };
            Grid.SetColumn(lblSearch, 0);
            searchGrid.Children.Add(lblSearch);

            // Champ recherche
            _txtSearch = new TextBox
            {
                Height  = 24,
                Padding = new Thickness(4, 2, 4, 2),
                VerticalContentAlignment = VerticalAlignment.Center,
                BorderBrush = BR_BORDER
            };
            _txtSearch.TextChanged += (s, e) => ApplyFilter();
            Grid.SetColumn(_txtSearch, 1);
            searchGrid.Children.Add(_txtSearch);

            // Label filtre
            var lblFilter = new TextBlock
            {
                Text = "Filtre :",
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(16, 0, 8, 0),
                Foreground = BR_TEXT
            };
            Grid.SetColumn(lblFilter, 2);
            searchGrid.Children.Add(lblFilter);

            // ComboBox filtre
            _cmbFilter = new ComboBox
            {
                Height  = 24,
                Padding = new Thickness(4, 0, 4, 0)
            };
            _cmbFilter.Items.Add("<tout afficher>");
            _cmbFilter.Items.Add("Prioritaires seulement");
            _cmbFilter.Items.Add("Cochés seulement");
            _cmbFilter.Items.Add("Non cochés");
            _cmbFilter.SelectedIndex = 0;
            _cmbFilter.SelectionChanged += (s, e) => ApplyFilter();
            Grid.SetColumn(_cmbFilter, 3);
            searchGrid.Children.Add(_cmbFilter);

            // Compteur
            _lblCount = new TextBlock
            {
                VerticalAlignment = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Right,
                Foreground = BR_MUTED,
                FontSize = 11
            };
            Grid.SetColumn(_lblCount, 5);
            searchGrid.Children.Add(_lblCount);

            searchBar.Child = searchGrid;
            Grid.SetRow(searchBar, 1);
            root.Children.Add(searchBar);

            // ── Boutons Tous / Aucun / Inverser ──────────────────────────────
            var quickBar = new Border
            {
                Background      = BR_WHITE,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(12, 5, 12, 5)
            };
            var quickPanel = new StackPanel { Orientation = Orientation.Horizontal };
            quickPanel.Children.Add(MakeQuickButton("Tous",     () => SetAll(true)));
            quickPanel.Children.Add(MakeQuickButton("Aucun",    () => SetAll(false)));
            quickPanel.Children.Add(MakeQuickButton("Inverser", () => InvertAll()));
            quickBar.Child = quickPanel;
            Grid.SetRow(quickBar, 2);
            root.Children.Add(quickBar);

            // ── DataGrid ─────────────────────────────────────────────────────
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
                SelectionMode            = DataGridSelectionMode.Extended,
                GridLinesVisibility      = DataGridGridLinesVisibility.Horizontal,
                HorizontalGridLinesBrush = BR_BORDER,
                Background               = BR_WHITE,
                RowBackground            = BR_WHITE,
                AlternatingRowBackground = BR_ALTA,
                BorderThickness          = new Thickness(0),
                ColumnHeaderHeight       = 28,
                RowHeight                = 24,
                FontSize                 = 12,
                Foreground               = BR_TEXT,
            };

            // Style header
            var headerStyle = new Style(typeof(DataGridColumnHeader));
            headerStyle.Setters.Add(new Setter(BackgroundProperty,       BR_HEADER));
            headerStyle.Setters.Add(new Setter(ForegroundProperty,       BR_TEXT));
            headerStyle.Setters.Add(new Setter(FontWeightProperty,       FontWeights.SemiBold));
            headerStyle.Setters.Add(new Setter(BorderBrushProperty,      BR_BORDER));
            headerStyle.Setters.Add(new Setter(BorderThicknessProperty,  new Thickness(0, 0, 1, 1)));
            headerStyle.Setters.Add(new Setter(PaddingProperty,          new Thickness(6, 0, 6, 0)));
            headerStyle.Setters.Add(new Setter(HorizontalContentAlignmentProperty, HorizontalAlignment.Left));
            _grid.ColumnHeaderStyle = headerStyle;

            // Style cellule
            var cellStyle = new Style(typeof(DataGridCell));
            cellStyle.Setters.Add(new Setter(BorderThicknessProperty, new Thickness(0)));
            cellStyle.Setters.Add(new Setter(PaddingProperty, new Thickness(6, 0, 6, 0)));
            var selTrigger = new Trigger { Property = DataGridCell.IsSelectedProperty, Value = true };
            selTrigger.Setters.Add(new Setter(BackgroundProperty, BR_SEL));
            selTrigger.Setters.Add(new Setter(ForegroundProperty, BR_SEL_TXT));
            cellStyle.Triggers.Add(selTrigger);
            _grid.CellStyle = cellStyle;

            // ── Colonnes ─────────────────────────────────────────────────────

            // Colonne checkbox
            var chkCol = new DataGridTemplateColumn
            {
                Header = "✓",
                Width  = new DataGridLength(36),
                CanUserResize = false,
                CanUserSort   = false,
            };
            var chkFactory = new FrameworkElementFactory(typeof(CheckBox));
            chkFactory.SetBinding(ToggleButton.IsCheckedProperty,
                new Binding("IsSelected") { Mode = BindingMode.TwoWay, UpdateSourceTrigger = UpdateSourceTrigger.PropertyChanged });
            chkFactory.SetValue(HorizontalAlignmentProperty, HorizontalAlignment.Center);
            chkFactory.SetValue(VerticalAlignmentProperty, VerticalAlignment.Center);
            chkCol.CellTemplate = new DataTemplate { VisualTree = chkFactory };
            _grid.Columns.Add(chkCol);

            // Colonne Priorité (pastille)
            var prioCol = new DataGridTemplateColumn
            {
                Header = "Priorité",
                Width  = new DataGridLength(70),
            };
            var prioFactory = new FrameworkElementFactory(typeof(TextBlock));
            prioFactory.SetBinding(TextBlock.TextProperty, new Binding("PriorityLabel"));
            prioFactory.SetBinding(TextBlock.ForegroundProperty, new Binding("PriorityColor"));
            prioFactory.SetValue(FontWeightProperty, FontWeights.SemiBold);
            prioFactory.SetValue(VerticalAlignmentProperty, VerticalAlignment.Center);
            prioFactory.SetValue(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0));
            prioCol.CellTemplate = new DataTemplate { VisualTree = prioFactory };
            _grid.Columns.Add(prioCol);

            // Colonne Nom équipement
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Nom de l'équipement",
                Binding = new Binding("Name"),
                Width   = new DataGridLength(1, DataGridLengthUnitType.Star),
            });

            // Colonne Type IFC
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Type",
                Binding = new Binding("IfcTypeShort"),
                Width   = new DataGridLength(160),
            });

            // Colonne Gaine
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Gaine / Local",
                Binding = new Binding("GaineName"),
                Width   = new DataGridLength(140),
            });

            // Colonne Niveau
            _grid.Columns.Add(new DataGridTextColumn
            {
                Header  = "Niveau",
                Binding = new Binding("LevelLabel"),
                Width   = new DataGridLength(80),
            });

            gridBorder.Child = _grid;
            Grid.SetRow(gridBorder, 3);
            root.Children.Add(gridBorder);

            // ── Note bas ─────────────────────────────────────────────────────
            var noteBorder = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 0),
                Padding         = new Thickness(12, 6, 12, 6),
                Margin          = new Thickness(0, 4, 0, 0)
            };
            noteBorder.Child = new TextBlock
            {
                Text       = "Les équipements cochés recevront un repère circulaire sur les vues dupliquées.",
                FontSize   = 11,
                Foreground = BR_MUTED,
                TextWrapping = TextWrapping.Wrap
            };
            Grid.SetRow(noteBorder, 4);
            root.Children.Add(noteBorder);

            // ── Boutons OK / Annuler ──────────────────────────────────────────
            var btnBar = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 0),
                Padding         = new Thickness(12, 8, 12, 8)
            };
            var btnPanel = new StackPanel
            {
                Orientation         = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right
            };
            btnPanel.Children.Add(MakeDialogButton("OK",       true,  OnOK));
            btnPanel.Children.Add(MakeDialogButton("Annuler",  false, OnCancel));
            btnBar.Child = btnPanel;
            Grid.SetRow(btnBar, 5);
            root.Children.Add(btnBar);

            Content = root;
        }

        // =====================================================================
        //  LOGIQUE
        // =====================================================================
        private void RefreshGrid()
        {
            _grid.ItemsSource = null;
            _grid.ItemsSource = _filteredRows;
            UpdateCount();
        }

        private void ApplyFilter()
        {
            string search  = _txtSearch?.Text?.Trim().ToLower() ?? "";
            int    filterIdx = _cmbFilter?.SelectedIndex ?? 0;

            _filteredRows = _rows.Where(r =>
            {
                bool nameMatch = string.IsNullOrEmpty(search) || r.Name.ToLower().Contains(search);
                bool filterMatch = filterIdx switch
                {
                    1 => r.Priority == "haute",
                    2 => r.IsSelected,
                    3 => !r.IsSelected,
                    _ => true
                };
                return nameMatch && filterMatch;
            }).ToList();

            RefreshGrid();
        }

        private void SetAll(bool value)
        {
            foreach (var r in _filteredRows) r.IsSelected = value;
            RefreshGrid();
        }

        private void InvertAll()
        {
            foreach (var r in _filteredRows) r.IsSelected = !r.IsSelected;
            RefreshGrid();
        }

        private void UpdateCount()
        {
            int total   = _rows.Count;
            int checked_ = _rows.Count(r => r.IsSelected);
            int shown   = _filteredRows.Count;
            if (_lblCount != null)
                _lblCount.Text = $"{shown} affiché(s) sur {total}  —  {checked_} coché(s)";
        }

        private void OnOK(object sender, RoutedEventArgs e)
        {
            SelectedEquipment = _rows
                .Where(r => r.IsSelected)
                .Select(r => r.Source)
                .ToList();
            DialogResult = true;
            Close();
        }

        private void OnCancel(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        // =====================================================================
        //  HELPERS UI
        // =====================================================================
        private static Button MakeDialogButton(string label, bool isDefault, RoutedEventHandler handler)
        {
            var btn = new Button
            {
                Content       = label,
                Width         = 90,
                Height        = 28,
                Margin        = new Thickness(6, 0, 0, 0),
                IsDefault     = isDefault,
                FontSize      = 12,
                Cursor        = Cursors.Hand,
                Background    = isDefault ? BR_SEL : BR_WHITE,
                Foreground    = isDefault ? BR_SEL_TXT : BR_TEXT,
                BorderBrush   = isDefault ? BR_SEL : BR_BORDER,
                BorderThickness = new Thickness(1),
            };
            btn.Click += handler;
            return btn;
        }

        private static Button MakeQuickButton(string label, Action action)
        {
            var btn = new Button
            {
                Content         = label,
                Width           = 80,
                Height          = 24,
                Margin          = new Thickness(0, 0, 6, 0),
                FontSize        = 11,
                Cursor          = Cursors.Hand,
                Background      = BR_WHITE,
                Foreground      = BR_TEXT,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(1),
            };
            btn.Click += (s, e) => action();
            return btn;
        }

        // =====================================================================
        //  CLASSES INTERNES
        // =====================================================================

        /// <summary>Ligne de la grille avec état de sélection.</summary>
        public class EquipmentRow : System.ComponentModel.INotifyPropertyChanged
        {
            public EquipmentItem Source { get; }

            private bool _isSelected;
            public bool IsSelected
            {
                get => _isSelected;
                set { _isSelected = value; OnPropChanged(nameof(IsSelected)); }
            }

            public string Name        => Source.Name;
            public string GaineName   => Source.GaineName;
            public string Priority    => Source.Priority;

            public string PriorityLabel => Priority == "haute" ? "Haute" : "Normale";

            public SolidColorBrush PriorityColor => Priority == "haute"
                ? new SolidColorBrush(Color.FromRgb(0, 84, 166))
                : new SolidColorBrush(Color.FromRgb(100, 100, 100));

            public string IfcTypeShort
            {
                get
                {
                    string t = Source.IfcType ?? "";
                    if (t.Contains("CableCarrier"))  return "Chemin de câbles";
                    if (t.Contains("Distribution"))  return "Tableau électrique";
                    if (t.Contains("Outlet"))        return "Prise / Sortie";
                    if (t.Contains("Alarm"))         return "Alarme / BAES";
                    if (t.Contains("Mechanical"))    return "Équip. mécanique";
                    return t.Replace("Ifc", "");
                }
            }

            public string LevelLabel
            {
                get
                {
                    double z = Source.Location != null && Source.Location.Length >= 3
                        ? Source.Location[2] : 0;
                    if (z < -0.5)  return "Sous-sol";
                    if (z <  3.5)  return "RDC";
                    if (z <  7.0)  return "Niveau 1";
                    if (z < 10.5)  return "Niveau 2";
                    if (z < 14.0)  return "Niveau 3";
                    return "Niveau 4+";
                }
            }

            public EquipmentRow(EquipmentItem source)
            {
                Source     = source;
                _isSelected = source.Priority == "haute"; // pré-cocher les prioritaires
            }

            public event System.ComponentModel.PropertyChangedEventHandler PropertyChanged;
            private void OnPropChanged(string name) =>
                PropertyChanged?.Invoke(this, new System.ComponentModel.PropertyChangedEventArgs(name));
        }
    }

    /// <summary>Données d'un équipement transmises depuis le JSON Python.</summary>
    [System.Runtime.Serialization.DataContract]
    public class EquipmentItem
    {
        [System.Runtime.Serialization.DataMember(Name = "revit_element_id")]
        public int      RevitElementId { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "name")]
        public string   Name           { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "ifc_type")]
        public string   IfcType        { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "location")]
        public double[] Location       { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "gaine_name")]
        public string   GaineName      { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "gaine_global_id")]
        public string   GaineGlobalId  { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "priority")]
        public string   Priority       { get; set; }
    }
}
