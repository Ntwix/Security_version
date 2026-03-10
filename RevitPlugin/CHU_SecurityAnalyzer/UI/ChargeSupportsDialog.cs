using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace CHU_SecurityAnalyzer.UI
{
    /// <summary>
    /// Formulaire GAINE-005 — Saisie des câbles par type de CDC.
    /// L'utilisateur choisit pour chaque type de CDC (CFO/CFA/Incendie)
    /// les câbles qui y passent (matériau CU/AL, conducteurs×section, quantité).
    /// Les masses proviennent de la norme NF C 32-321.
    /// </summary>
    public class ChargeSupportsDialog : Window
    {
        // ── Données entrée ────────────────────────────────────────────────────
        private readonly List<CdcTypeInfo> _cdcTypes;
        private readonly double _supportCapacity;
        private readonly double _safetyMargin;

        /// <summary>Résultats après validation : violations par type de CDC</summary>
        public List<CdcChargeResult> Results { get; private set; } = new List<CdcChargeResult>();

        // ── Couleurs style Revit ─────────────────────────────────────────────
        private static readonly SolidColorBrush BR_WHITE   = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_HEADER  = new SolidColorBrush(Color.FromRgb(230, 230, 230));
        private static readonly SolidColorBrush BR_BORDER  = new SolidColorBrush(Color.FromRgb(180, 180, 180));
        private static readonly SolidColorBrush BR_SEL     = new SolidColorBrush(Color.FromRgb(0, 114, 188));
        private static readonly SolidColorBrush BR_SEL_TXT = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_TEXT    = new SolidColorBrush(Color.FromRgb(30, 30, 30));
        private static readonly SolidColorBrush BR_MUTED   = new SolidColorBrush(Color.FromRgb(100, 100, 100));
        private static readonly SolidColorBrush BR_FOOTER  = new SolidColorBrush(Color.FromRgb(240, 240, 240));
        private static readonly SolidColorBrush BR_OK      = new SolidColorBrush(Color.FromRgb(0, 150, 60));
        private static readonly SolidColorBrush BR_WARN    = new SolidColorBrush(Color.FromRgb(200, 80, 0));
        private static readonly SolidColorBrush BR_ERR     = new SolidColorBrush(Color.FromRgb(180, 0, 0));
        private static readonly SolidColorBrush BR_SECTION = new SolidColorBrush(Color.FromRgb(0, 84, 166));

        // ── Tableau NF C 32-321 — Masse (kg/km) ─────────────────────────────
        // Clé = "conducteurs_section" ex: "1x16", "3x35", "2x70"
        // Valeur = { CU, AL } en kg/km  (-1 = non disponible)
        private static readonly Dictionary<string, (double Cu, double Al)> NF_C_32321 =
            new Dictionary<string, (double, double)>
        {
            { "1x16",  (-1,    103)  },
            { "1x25",  (294.7, 145)  },
            { "1x35",  (293.2, 177)  },
            { "1x50",  (516.5, 229)  },
            { "1x70",  (720.6, 302)  },
            { "1x95",  (967.3, 392)  },
            { "1x120", (1212.1,479)  },
            { "1x150", (1472.5,591)  },
            { "1x185", (1831.9,723)  },
            { "1x240", (2410.8,925)  },
            { "1x300", (2994.4,-1)   },
            { "1x400", (3843.6,-1)   },
            { "2x16",  (-1,    394)  },
            { "2x25",  (853.3, 551)  },
            { "2x35",  (1113.1,682)  },
            { "3x16",  (-1,    436)  },
            { "3x25",  (1049.7,596)  },
            { "3x35",  (139,   735)  },   // NF: 139 kg/km CU (données tableau)
            { "3x50",  (1832.8,960)  },
            { "3x70",  (2599.4,1344) },
            { "3x95",  (3509,  1766) },
            { "3x120", (4345,  2141) },
            { "3x150", (5289,  1626) },
            { "3x185", (6561,  3303) },
            { "3x240", (8650,  4146) },
            { "3x300", (10842, -1)   },
        };

        // ── Sections disponibles ─────────────────────────────────────────────
        private static readonly string[] CONDUCTEURS = { "1x", "2x", "3x" };
        private static readonly string[] SECTIONS    = { "16", "25", "35", "50", "70", "95", "120", "150", "185", "240", "300", "400" };
        private static readonly string[] MATERIAUX   = { "CU", "AL" };

        // ── Contrôles résultat ───────────────────────────────────────────────
        private StackPanel _resultsPanel;

        // ── État saisie par type CDC ─────────────────────────────────────────
        // ServiceType -> liste de lignes de saisie
        private readonly Dictionary<string, List<CableInputRow>> _inputRows =
            new Dictionary<string, List<CableInputRow>>();

        // =====================================================================
        //  CONSTRUCTEUR
        // =====================================================================
        public ChargeSupportsDialog(List<CdcTypeInfo> cdcTypes, double supportCapacity, double safetyMarginPercent)
        {
            _cdcTypes        = cdcTypes ?? new List<CdcTypeInfo>();
            _supportCapacity = supportCapacity > 0 ? supportCapacity : 90.0;
            _safetyMargin    = safetyMarginPercent / 100.0;

            Title                 = "GAINE-005 — Vérification charge supports câbles";
            Width                 = 860;
            Height                = 680;
            MinWidth              = 700;
            MinHeight             = 500;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode            = ResizeMode.CanResize;
            Background            = BR_WHITE;
            FontFamily            = new FontFamily("Segoe UI");
            FontSize              = 12;

            foreach (var cdc in _cdcTypes)
                _inputRows[cdc.ServiceType] = new List<CableInputRow>();

            BuildUI();
        }

        // =====================================================================
        //  CONSTRUCTION UI
        // =====================================================================
        private void BuildUI()
        {
            var root = new Grid();
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });                          // titre
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });     // contenu scrollable
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });                          // résultats
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });                          // boutons

            // ── Titre ────────────────────────────────────────────────────────
            var titleBorder = new Border
            {
                Background      = BR_WHITE,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(14, 10, 14, 10)
            };
            var titleStack = new StackPanel();
            titleStack.Children.Add(new TextBlock
            {
                Text       = "Déclaration des câbles sur les chemins de câbles (CDC)",
                FontSize   = 13,
                FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT
            });
            double safeKg = _supportCapacity * (1 - _safetyMargin);
            titleStack.Children.Add(new TextBlock
            {
                Text       = $"Capacité support : {_supportCapacity:F0} kg  —  Admissible (marge {_safetyMargin*100:F0}%) : {safeKg:F0} kg  —  Masses NF C 32-321",
                FontSize   = 11,
                Foreground = BR_MUTED,
                Margin     = new Thickness(0, 3, 0, 0)
            });
            titleBorder.Child = titleStack;
            Grid.SetRow(titleBorder, 0);
            root.Children.Add(titleBorder);

            // ── Contenu scrollable ───────────────────────────────────────────
            var scroll = new ScrollViewer
            {
                VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Margin                        = new Thickness(0)
            };

            var contentStack = new StackPanel { Margin = new Thickness(14, 8, 14, 8) };

            // Un bloc par type de CDC
            foreach (var cdc in _cdcTypes)
                contentStack.Children.Add(BuildCdcSection(cdc));

            scroll.Content = contentStack;
            Grid.SetRow(scroll, 1);
            root.Children.Add(scroll);

            // ── Zone résultats ───────────────────────────────────────────────
            var resBorder = new Border
            {
                Background      = BR_FOOTER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 0),
                Padding         = new Thickness(14, 8, 14, 8)
            };
            _resultsPanel = new StackPanel();
            _resultsPanel.Children.Add(new TextBlock
            {
                Text       = "Ajoutez des câbles ci-dessus puis cliquez « Calculer ».",
                Foreground = BR_MUTED,
                FontSize   = 11
            });
            resBorder.Child = _resultsPanel;
            Grid.SetRow(resBorder, 2);
            root.Children.Add(resBorder);

            // ── Boutons ──────────────────────────────────────────────────────
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
            btnPanel.Children.Add(MakeButton("Calculer", false, OnCalculate));
            btnPanel.Children.Add(MakeButton("Valider",  true,  OnOK));
            btnPanel.Children.Add(MakeButton("Annuler",  false, OnCancel));
            btnBar.Child = btnPanel;
            Grid.SetRow(btnBar, 3);
            root.Children.Add(btnBar);

            Content = root;
        }

        private UIElement BuildCdcSection(CdcTypeInfo cdc)
        {
            var sectionBorder = new Border
            {
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(1),
                CornerRadius    = new CornerRadius(3),
                Margin          = new Thickness(0, 6, 0, 6),
                Background      = BR_WHITE
            };

            var stack = new StackPanel();

            // En-tête section
            var header = new Border
            {
                Background      = BR_SECTION,
                Padding         = new Thickness(10, 6, 10, 6),
                CornerRadius    = new CornerRadius(2, 2, 0, 0)
            };
            var headerGrid = new Grid();
            headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var headerText = new TextBlock
            {
                Text       = $"CDC {cdc.ServiceType}   —   {cdc.SegmentCount} segments   —   longueur totale : {cdc.TotalLengthM:F1} m",
                Foreground = BR_SEL_TXT,
                FontWeight = FontWeights.SemiBold,
                FontSize   = 12,
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(headerText, 0);
            headerGrid.Children.Add(headerText);

            var btnAdd = new Button
            {
                Content         = "+ Ajouter câble",
                FontSize        = 11,
                Padding         = new Thickness(8, 3, 8, 3),
                Background      = BR_WHITE,
                Foreground      = BR_SECTION,
                BorderBrush     = BR_WHITE,
                BorderThickness = new Thickness(1),
                Cursor          = Cursors.Hand,
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(btnAdd, 1);
            headerGrid.Children.Add(btnAdd);

            header.Child = headerGrid;
            stack.Children.Add(header);

            // En-tête colonnes
            stack.Children.Add(BuildColumnHeaders());

            // Panel lignes de saisie
            var rowsPanel = new StackPanel { Margin = new Thickness(0) };
            stack.Children.Add(rowsPanel);

            // Ligne vide par défaut
            AddInputRow(cdc.ServiceType, rowsPanel);

            // Bouton ajouter → ajoute une ligne
            btnAdd.Click += (s, e) => AddInputRow(cdc.ServiceType, rowsPanel);

            sectionBorder.Child = stack;
            return sectionBorder;
        }

        private UIElement BuildColumnHeaders()
        {
            var border = new Border
            {
                Background      = BR_HEADER,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 1, 0, 1),
                Padding         = new Thickness(8, 4, 8, 4)
            };
            var g = new Grid();
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) }); // Conducteurs
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(80) });  // Matériau
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(90) });  // Section
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(70) });  // Quantité
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(100) }); // Masse kg/km
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) }); // kg/m × qté
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(36) });  // Supprimer

            AddHeaderCell(g, "Conducteurs", 0);
            AddHeaderCell(g, "Matériau",    1);
            AddHeaderCell(g, "Section mm²", 2);
            AddHeaderCell(g, "Quantité",    3);
            AddHeaderCell(g, "Masse kg/km", 4);
            AddHeaderCell(g, "Charge kg/m", 5);
            border.Child = g;
            return border;
        }

        private static void AddHeaderCell(Grid g, string text, int col)
        {
            var tb = new TextBlock
            {
                Text       = text,
                FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT,
                FontSize   = 11,
                VerticalAlignment   = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Left,
                Margin     = new Thickness(4, 0, 4, 0)
            };
            Grid.SetColumn(tb, col);
            g.Children.Add(tb);
        }

        private void AddInputRow(string serviceType, StackPanel rowsPanel)
        {
            var row = new CableInputRow();
            _inputRows[serviceType].Add(row);

            var border = new Border
            {
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(8, 4, 8, 4),
                Background      = BR_WHITE
            };

            var g = new Grid();
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(80) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(90) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(70) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(100) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(36) });

            // ComboBox Conducteurs
            row.CmbConducteurs = new ComboBox { Height = 24, FontSize = 11 };
            foreach (var c in CONDUCTEURS) row.CmbConducteurs.Items.Add(c);
            row.CmbConducteurs.SelectedIndex = 2; // "3x" par défaut
            Grid.SetColumn(row.CmbConducteurs, 0);
            g.Children.Add(row.CmbConducteurs);

            // ComboBox Matériau
            row.CmbMateriau = new ComboBox { Height = 24, FontSize = 11, Margin = new Thickness(4, 0, 0, 0) };
            foreach (var m in MATERIAUX) row.CmbMateriau.Items.Add(m);
            row.CmbMateriau.SelectedIndex = 0; // CU par défaut
            Grid.SetColumn(row.CmbMateriau, 1);
            g.Children.Add(row.CmbMateriau);

            // ComboBox Section
            row.CmbSection = new ComboBox { Height = 24, FontSize = 11, Margin = new Thickness(4, 0, 0, 0) };
            foreach (var s in SECTIONS) row.CmbSection.Items.Add(s);
            row.CmbSection.SelectedIndex = 2; // 35 par défaut
            Grid.SetColumn(row.CmbSection, 2);
            g.Children.Add(row.CmbSection);

            // TextBox Quantité
            row.TxtQuantite = new TextBox
            {
                Text    = "1",
                Height  = 24,
                Padding = new Thickness(4, 2, 4, 2),
                VerticalContentAlignment = VerticalAlignment.Center,
                BorderBrush  = BR_BORDER,
                FontSize     = 11,
                Margin       = new Thickness(4, 0, 0, 0)
            };
            Grid.SetColumn(row.TxtQuantite, 3);
            g.Children.Add(row.TxtQuantite);

            // Label masse kg/km (mis à jour au changement)
            row.LblMasse = new TextBlock
            {
                VerticalAlignment   = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Center,
                FontSize   = 11,
                Foreground = BR_MUTED,
                Margin     = new Thickness(4, 0, 0, 0)
            };
            Grid.SetColumn(row.LblMasse, 4);
            g.Children.Add(row.LblMasse);

            // Label charge kg/m
            row.LblCharge = new TextBlock
            {
                VerticalAlignment   = VerticalAlignment.Center,
                FontSize   = 11,
                FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT,
                Margin     = new Thickness(8, 0, 0, 0)
            };
            Grid.SetColumn(row.LblCharge, 5);
            g.Children.Add(row.LblCharge);

            // Bouton supprimer
            var btnDel = new Button
            {
                Content         = "✕",
                Width           = 28,
                Height          = 24,
                FontSize        = 11,
                Background      = BR_WHITE,
                Foreground      = BR_ERR,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(1),
                Cursor          = Cursors.Hand,
                Margin          = new Thickness(4, 0, 0, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(btnDel, 6);
            g.Children.Add(btnDel);

            border.Child = g;

            // Supprimer la ligne
            btnDel.Click += (s, e) =>
            {
                _inputRows[serviceType].Remove(row);
                rowsPanel.Children.Remove(border);
                UpdateRowMasse(row); // recalcul pas nécessaire mais refresh propre
            };

            // Mise à jour masse quand les combos changent
            row.CmbConducteurs.SelectionChanged += (s, e) => UpdateRowMasse(row);
            row.CmbMateriau.SelectionChanged    += (s, e) => UpdateRowMasse(row);
            row.CmbSection.SelectionChanged     += (s, e) => UpdateRowMasse(row);
            row.TxtQuantite.TextChanged         += (s, e) => UpdateRowMasse(row);

            rowsPanel.Children.Add(border);
            UpdateRowMasse(row);
        }

        private static void UpdateRowMasse(CableInputRow row)
        {
            string key = GetNfKey(row);
            string mat = row.CmbMateriau?.SelectedItem?.ToString() ?? "CU";
            int qty    = GetRowQty(row);

            if (NF_C_32321.TryGetValue(key, out var masses))
            {
                double masseKgKm = mat == "AL" ? masses.Al : masses.Cu;
                if (masseKgKm < 0)
                {
                    row.LblMasse.Text       = "N/D";
                    row.LblMasse.Foreground = BR_MUTED;
                    row.LblCharge.Text      = "—";
                    row.MasseKgKm           = -1;
                }
                else
                {
                    double chargeKgPerM = masseKgKm / 1000.0 * qty;
                    row.LblMasse.Text       = $"{masseKgKm:F0}";
                    row.LblMasse.Foreground = BR_TEXT;
                    row.LblCharge.Text      = $"{chargeKgPerM:F3} kg/m × {qty}";
                    row.MasseKgKm           = masseKgKm;
                }
            }
            else
            {
                row.LblMasse.Text       = "N/D";
                row.LblMasse.Foreground = BR_MUTED;
                row.LblCharge.Text      = "—";
                row.MasseKgKm           = -1;
            }
        }

        private static string GetNfKey(CableInputRow row)
        {
            string cond    = row.CmbConducteurs?.SelectedItem?.ToString() ?? "3x";
            string section = row.CmbSection?.SelectedItem?.ToString() ?? "35";
            return $"{cond}{section}";
        }

        private static int GetRowQty(CableInputRow row)
        {
            if (row.TxtQuantite == null) return 1;
            return int.TryParse(row.TxtQuantite.Text.Trim(), out int q) && q > 0 ? q : 1;
        }

        // =====================================================================
        //  CALCUL
        // =====================================================================
        private void OnCalculate(object sender, RoutedEventArgs e)
        {
            _resultsPanel.Children.Clear();
            Results.Clear();

            double safeCapacity = _supportCapacity * (1 - _safetyMargin);
            bool anyViolation   = false;

            foreach (var cdc in _cdcTypes)
            {
                string svc  = cdc.ServiceType;
                double len  = cdc.TotalLengthM;
                var rows    = _inputRows.ContainsKey(svc) ? _inputRows[svc] : new List<CableInputRow>();

                double totalKgPerM = 0;
                var breakdown      = new List<string>();

                foreach (var row in rows)
                {
                    if (row.MasseKgKm <= 0) continue;
                    int qty          = GetRowQty(row);
                    double kgPerM    = row.MasseKgKm / 1000.0 * qty;
                    totalKgPerM     += kgPerM;
                    string key       = GetNfKey(row);
                    string mat       = row.CmbMateriau?.SelectedItem?.ToString() ?? "CU";
                    breakdown.Add($"{qty}× {key} {mat} ({kgPerM:F3} kg/m)");
                }

                double totalKg  = totalKgPerM * len;
                bool violation  = totalKg > safeCapacity;
                if (violation) anyViolation = true;

                // Ligne résultat
                var resLine = new Border
                {
                    Padding         = new Thickness(6, 3, 6, 3),
                    Background      = violation ? new SolidColorBrush(Color.FromRgb(255, 240, 240))
                                                : new SolidColorBrush(Color.FromRgb(240, 255, 240)),
                    BorderBrush     = violation ? BR_ERR : BR_OK,
                    BorderThickness = new Thickness(0, 0, 0, 1),
                    Margin          = new Thickness(0, 2, 0, 2)
                };

                var resStack = new StackPanel { Orientation = Orientation.Horizontal };
                string icon  = violation ? "⚠" : "✓";
                var iconTb   = new TextBlock
                {
                    Text       = icon,
                    Foreground = violation ? BR_ERR : BR_OK,
                    FontSize   = 14,
                    FontWeight = FontWeights.Bold,
                    Margin     = new Thickness(0, 0, 8, 0),
                    VerticalAlignment = VerticalAlignment.Center
                };
                resStack.Children.Add(iconTb);

                string msg = violation
                    ? $"CDC {svc} : {totalKg:F1} kg > {safeCapacity:F0} kg admissible  [charge/m={totalKgPerM:F3}, sur {len:F1}m]"
                    : $"CDC {svc} : {totalKg:F1} kg ≤ {safeCapacity:F0} kg  [charge/m={totalKgPerM:F3}, sur {len:F1}m]";
                if (breakdown.Count > 0) msg += $"  — {string.Join(", ", breakdown)}";

                resStack.Children.Add(new TextBlock
                {
                    Text       = msg,
                    Foreground = violation ? BR_ERR : BR_OK,
                    FontSize   = 11,
                    VerticalAlignment = VerticalAlignment.Center,
                    TextWrapping = TextWrapping.Wrap
                });
                resLine.Child = resStack;
                _resultsPanel.Children.Add(resLine);

                // Stocker pour transmission au C# parent
                Results.Add(new CdcChargeResult
                {
                    ServiceType      = svc,
                    TotalLengthM     = len,
                    SegmentCount     = cdc.SegmentCount,
                    TotalWeightKg    = Math.Round(totalKg, 2),
                    WeightPerMeterKg = Math.Round(totalKgPerM, 4),
                    SafeCapacityKg   = Math.Round(safeCapacity, 1),
                    IsViolation      = violation,
                    Breakdown        = string.Join(" | ", breakdown)
                });
            }

            // Message récapitulatif
            var summary = new TextBlock
            {
                Text       = anyViolation
                    ? "Des violations ont été détectées. Cliquez « Valider » pour les enregistrer."
                    : "Aucune violation — charge admissible respectée. Cliquez « Valider » pour confirmer.",
                Foreground = anyViolation ? BR_ERR : BR_OK,
                FontWeight = FontWeights.SemiBold,
                FontSize   = 12,
                Margin     = new Thickness(0, 6, 0, 0),
                TextWrapping = TextWrapping.Wrap
            };
            _resultsPanel.Children.Add(summary);
        }

        private void OnOK(object sender, RoutedEventArgs e)
        {
            // Si pas encore calculé, calculer automatiquement
            if (Results.Count == 0)
                OnCalculate(sender, e);

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
        private static Button MakeButton(string label, bool isDefault, RoutedEventHandler handler)
        {
            var btn = new Button
            {
                Content         = label,
                Width           = 90,
                Height          = 28,
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

        // =====================================================================
        //  CLASSES INTERNES
        // =====================================================================

        /// <summary>Ligne de saisie d'un câble dans le formulaire.</summary>
        private class CableInputRow
        {
            public ComboBox CmbConducteurs { get; set; }
            public ComboBox CmbMateriau    { get; set; }
            public ComboBox CmbSection     { get; set; }
            public TextBox  TxtQuantite    { get; set; }
            public TextBlock LblMasse      { get; set; }
            public TextBlock LblCharge     { get; set; }
            public double   MasseKgKm      { get; set; } = -1;
        }
    }

    // =========================================================================
    //  TYPES DE DONNÉES (sérialisables)
    // =========================================================================

    /// <summary>Informations sur un type de CDC extraites du JSON Python.</summary>
    [System.Runtime.Serialization.DataContract]
    public class CdcTypeInfo
    {
        [System.Runtime.Serialization.DataMember(Name = "service_type")]
        public string ServiceType    { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "segment_count")]
        public int    SegmentCount   { get; set; }

        [System.Runtime.Serialization.DataMember(Name = "total_length_m")]
        public double TotalLengthM   { get; set; }
    }

    /// <summary>Résultat de calcul pour un type de CDC — transmis à ExtractAndAnalyzeCommand.</summary>
    public class CdcChargeResult
    {
        public string ServiceType      { get; set; }
        public double TotalLengthM     { get; set; }
        public int    SegmentCount     { get; set; }
        public double TotalWeightKg    { get; set; }
        public double WeightPerMeterKg { get; set; }
        public double SafeCapacityKg   { get; set; }
        public bool   IsViolation      { get; set; }
        public string Breakdown        { get; set; }
    }
}
