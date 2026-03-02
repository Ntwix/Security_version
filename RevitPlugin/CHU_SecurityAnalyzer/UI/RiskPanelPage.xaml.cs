using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Shapes;
using CHU_SecurityAnalyzer.Core;

namespace CHU_SecurityAnalyzer.UI
{
    public class RiskPanelPage : UserControl
    {
        // ── Couleurs ─────────────────────────────────────────────────────────
        private static readonly Color C_BG       = Color.FromRgb(25,  25,  35);
        private static readonly Color C_BG2      = Color.FromRgb(32,  32,  45);
        private static readonly Color C_BG3      = Color.FromRgb(40,  40,  58);
        private static readonly Color C_BORDER   = Color.FromRgb(55,  55,  75);
        private static readonly Color C_TEXT     = Color.FromRgb(220, 220, 235);
        private static readonly Color C_MUTED    = Color.FromRgb(120, 120, 150);
        private static readonly Color C_ACCENT   = Color.FromRgb(100, 160, 255);

        private static readonly Dictionary<string, Color> RuleColors = new Dictionary<string, Color>
        {
            { "ELEC-002", Color.FromRgb(100, 160, 255) },  // bleu
            { "ELEC-003", Color.FromRgb(255, 165,  80) },  // orange
            { "ELEC-004", Color.FromRgb(255,  90,  90) },  // rouge
        };

        private static readonly Dictionary<string, string> RuleLabels = new Dictionary<string, string>
        {
            { "ELEC-002", "Ventilation" },
            { "ELEC-003", "Porte"       },
            { "ELEC-004", "Zone IP65"   },
        };

        private static readonly List<(string Name, double ZMin, double ZMax)> LevelRanges =
            new List<(string, double, double)>
        {
            ("Sous-sol",  -6.0, -0.5),
            ("RDC",       -0.5,  3.5),
            ("Niveau 1",   3.5,  7.0),
            ("Niveau 2",   7.0, 10.5),
            ("Niveau 3",  10.5, 14.0),
            ("Niveau 4",  14.0, 25.0),
        };

        // ── Etat ─────────────────────────────────────────────────────────────
        private AnalysisResults _results;
        private readonly HashSet<string> _filters = new HashSet<string>();

        // ── Controles ────────────────────────────────────────────────────────
        private TextBlock  _txtTitle, _txtStats;
        private StackPanel _statBars;
        private TreeView   _tree;
        private readonly Dictionary<string, ToggleButton> _filterBtns =
            new Dictionary<string, ToggleButton>();
        private ToggleButton _btnAll;

        public RiskPanelPage() { Build(); }

        // =====================================================================
        //  CONSTRUCTION UI
        // =====================================================================
        private void Build()
        {
            Background = Brush(C_BG);
            FontFamily = new FontFamily("Segoe UI");

            var root = new DockPanel();

            // ── Header ───────────────────────────────────────────────────────
            var header = new Border
            {
                Background  = Brush(C_BG2),
                BorderBrush = Brush(C_BORDER),
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding = new Thickness(10, 8, 10, 8)
            };
            DockPanel.SetDock(header, Dock.Top);

            var hStack = new StackPanel();

            // Titre + point vert
            var titleRow = new StackPanel { Orientation = Orientation.Horizontal };
            var dot = new Ellipse
            {
                Width = 8, Height = 8,
                Fill = Brush(Color.FromRgb(80, 200, 120)),
                Margin = new Thickness(0, 0, 7, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            titleRow.Children.Add(dot);
            _txtTitle = new TextBlock
            {
                Text = "CHU — Zones a Risque",
                FontSize = 13, FontWeight = FontWeights.SemiBold,
                Foreground = Brush(C_TEXT),
                VerticalAlignment = VerticalAlignment.Center
            };
            titleRow.Children.Add(_txtTitle);
            hStack.Children.Add(titleRow);

            // Ligne de stats texte
            _txtStats = new TextBlock
            {
                Text = "Aucune analyse lancee",
                FontSize = 10, Foreground = Brush(C_MUTED),
                Margin = new Thickness(15, 3, 0, 4)
            };
            hStack.Children.Add(_txtStats);

            // Barres de stats par regle
            _statBars = new StackPanel { Margin = new Thickness(15, 0, 0, 0) };
            hStack.Children.Add(_statBars);

            header.Child = hStack;
            root.Children.Add(header);

            // ── Filtres ──────────────────────────────────────────────────────
            var filterBar = new Border
            {
                Background = Brush(C_BG2),
                BorderBrush = Brush(C_BORDER),
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding = new Thickness(8, 6, 8, 6)
            };
            DockPanel.SetDock(filterBar, Dock.Top);

            var filterStack = new StackPanel();
            filterStack.Children.Add(new TextBlock
            {
                Text = "FILTRER PAR REGLE",
                FontSize = 9, FontWeight = FontWeights.Bold,
                Foreground = Brush(C_MUTED),
                Margin = new Thickness(0, 0, 0, 5)
            });

            var btnRow = new WrapPanel { Orientation = Orientation.Horizontal };

            _btnAll = MakeFilterButton("Tout afficher", Colors.White, true);
            _btnAll.Checked += (s, e) => OnAllChecked();
            btnRow.Children.Add(_btnAll);

            foreach (var kvp in RuleColors)
            {
                var btn = MakeFilterButton(kvp.Key + "  " + RuleLabels[kvp.Key], kvp.Value, false);
                btn.Tag = kvp.Key;
                btn.Checked   += (s, e) => OnRuleChecked((string)((ToggleButton)s).Tag);
                btn.Unchecked += (s, e) => OnRuleUnchecked((string)((ToggleButton)s).Tag);
                _filterBtns[kvp.Key] = btn;
                btnRow.Children.Add(btn);
            }

            filterStack.Children.Add(btnRow);
            filterBar.Child = filterStack;
            root.Children.Add(filterBar);

            // ── TreeView ─────────────────────────────────────────────────────
            var scroll = new ScrollViewer
            {
                VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Background = Brush(C_BG)
            };
            _tree = new TreeView
            {
                Background = Brush(C_BG),
                BorderThickness = new Thickness(0),
                Padding = new Thickness(0, 4, 0, 4),
                Foreground = Brush(C_TEXT)
            };
            scroll.Content = _tree;
            root.Children.Add(scroll);

            Content = root;
        }

        // =====================================================================
        //  MISE A JOUR
        // =====================================================================
        public void UpdateResults(AnalysisResults results, string zone)
        {
            _results = results;
            _filters.Clear();
            _btnAll.IsChecked = true;
            foreach (var b in _filterBtns.Values) b.IsChecked = false;

            int total    = results?.Violations?.Count ?? 0;
            int critical = results?.Violations?.Count(v =>
                v.Severity?.ToUpper() == "CRITICAL") ?? 0;
            int imp      = total - critical;

            _txtStats.Text = string.Format(
                "Zone {0}   {1} violations totales", zone, total);

            // Barres par regle
            _statBars.Children.Clear();
            var byRule = (results?.Violations ?? new List<ViolationData>())
                .GroupBy(v => v.RuleId ?? "")
                .Where(g => RuleColors.ContainsKey(g.Key))
                .OrderBy(g => g.Key);

            foreach (var grp in byRule)
            {
                Color c = RuleColors[grp.Key];
                string lbl = RuleLabels.ContainsKey(grp.Key) ? RuleLabels[grp.Key] : grp.Key;

                var row = new Grid { Margin = new Thickness(0, 1, 0, 1) };
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(85) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

                // Label
                var lbTxt = new TextBlock
                {
                    Text = grp.Key,
                    FontSize = 10, FontWeight = FontWeights.SemiBold,
                    Foreground = Brush(c),
                    VerticalAlignment = VerticalAlignment.Center
                };
                Grid.SetColumn(lbTxt, 0);
                row.Children.Add(lbTxt);

                // Barre
                var barBg = new Border
                {
                    Height = 6, CornerRadius = new CornerRadius(3),
                    Background = Brush(C_BG3),
                    VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(4, 0, 8, 0)
                };
                double pct = total > 0 ? (double)grp.Count() / total : 0;
                var barFill = new Border
                {
                    Height = 6, CornerRadius = new CornerRadius(3),
                    Background = Brush(c),
                    HorizontalAlignment = HorizontalAlignment.Left
                };
                // Appliquer la largeur apres rendu
                barBg.Loaded += (s, e) =>
                {
                    barFill.Width = Math.Max(2, barBg.ActualWidth * pct);
                };
                barBg.SizeChanged += (s, e) =>
                {
                    barFill.Width = Math.Max(2, barBg.ActualWidth * pct);
                };
                barBg.Child = barFill;
                Grid.SetColumn(barBg, 1);
                row.Children.Add(barBg);

                // Compteur
                var cnt = new TextBlock
                {
                    Text = grp.Count().ToString(),
                    FontSize = 10, FontWeight = FontWeights.Bold,
                    Foreground = Brush(c),
                    VerticalAlignment = VerticalAlignment.Center
                };
                Grid.SetColumn(cnt, 2);
                row.Children.Add(cnt);

                _statBars.Children.Add(row);
            }

            RebuildTree();
        }

        // =====================================================================
        //  ARBRE
        // =====================================================================
        private void RebuildTree()
        {
            _tree.Items.Clear();
            if (_results?.Violations == null) return;

            var viols = _results.Violations.AsEnumerable();
            if (_filters.Count > 0)
                viols = viols.Where(v => _filters.Contains(v.RuleId ?? ""));

            var list = viols.ToList();

            foreach (var lvl in LevelRanges)
            {
                var lvlViols = list
                    .Where(v => v.Location != null && v.Location.Length >= 3
                                && v.Location[2] >= lvl.ZMin && v.Location[2] < lvl.ZMax)
                    .ToList();

                if (lvlViols.Count == 0) continue;

                int critCount = lvlViols.Count(v => v.Severity?.ToUpper() == "CRITICAL");
                var lvlItem   = MakeLevelItem(lvl.Name, lvlViols.Count, critCount);

                foreach (var grp in lvlViols
                    .GroupBy(v => v.SpaceName ?? "INCONNU")
                    .OrderBy(g => g.Key))
                {
                    lvlItem.Items.Add(MakeSpaceItem(grp.Key, grp.ToList()));
                }

                _tree.Items.Add(lvlItem);
            }
        }

        // ── Item niveau ──────────────────────────────────────────────────────
        private TreeViewItem MakeLevelItem(string name, int total, int critical)
        {
            var panel = new Grid();
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            // Icone barre verticale coloree
            var bar = new Border
            {
                Width = 3, Height = 16,
                Background = Brush(C_ACCENT),
                CornerRadius = new CornerRadius(2),
                Margin = new Thickness(0, 0, 8, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(bar, 0);
            panel.Children.Add(bar);

            // Nom niveau
            var txt = new TextBlock
            {
                Text = name,
                FontSize = 12, FontWeight = FontWeights.Bold,
                Foreground = Brush(C_TEXT),
                VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(txt, 1);
            panel.Children.Add(txt);

            // Badge critique
            if (critical > 0)
            {
                var critBadge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(50, 255, 80, 80)),
                    BorderBrush = Brush(Color.FromRgb(255, 80, 80)),
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(4),
                    Padding = new Thickness(5, 1, 5, 1),
                    Margin = new Thickness(0, 0, 5, 0),
                    VerticalAlignment = VerticalAlignment.Center,
                    Child = new TextBlock
                    {
                        Text = critical + " crit.",
                        FontSize = 9, FontWeight = FontWeights.Bold,
                        Foreground = Brush(Color.FromRgb(255, 100, 100))
                    }
                };
                Grid.SetColumn(critBadge, 2);
                panel.Children.Add(critBadge);
            }

            // Badge total
            var badge = new Border
            {
                Background = Brush(C_BG3),
                CornerRadius = new CornerRadius(10),
                Padding = new Thickness(7, 2, 7, 2),
                VerticalAlignment = VerticalAlignment.Center,
                Child = new TextBlock
                {
                    Text = total.ToString(),
                    FontSize = 10, FontWeight = FontWeights.Bold,
                    Foreground = Brush(C_ACCENT)
                }
            };
            Grid.SetColumn(badge, 3);
            panel.Children.Add(badge);

            var item = new TreeViewItem
            {
                Header = panel,
                IsExpanded = false,
                Padding = new Thickness(4, 3, 4, 3)
            };
            StyleTreeItem(item, C_BG2, C_BG3);
            return item;
        }

        // ── Item espace ──────────────────────────────────────────────────────
        private TreeViewItem MakeSpaceItem(string spaceName, List<ViolationData> viols)
        {
            var rules = viols.Select(v => v.RuleId ?? "").Distinct().OrderBy(r => r).ToList();
            bool hasCrit = viols.Any(v => v.Severity?.ToUpper() == "CRITICAL");

            // Header espace
            var panel = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 1, 0, 1) };

            // Pastilles regles
            foreach (var rule in rules)
            {
                Color c = RuleColors.ContainsKey(rule) ? RuleColors[rule] : C_MUTED;
                panel.Children.Add(new Ellipse
                {
                    Width = 7, Height = 7,
                    Fill = Brush(c),
                    Margin = new Thickness(0, 0, 3, 0),
                    VerticalAlignment = VerticalAlignment.Center
                });
            }

            panel.Children.Add(new TextBlock
            {
                Text = spaceName,
                FontSize = 11, FontWeight = FontWeights.SemiBold,
                Foreground = Brush(hasCrit ? Color.FromRgb(255, 200, 200) : C_TEXT),
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(2, 0, 8, 0)
            });

            // Nombre total violations
            panel.Children.Add(new TextBlock
            {
                Text = viols.Count + " viol.",
                FontSize = 9, Foreground = Brush(C_MUTED),
                VerticalAlignment = VerticalAlignment.Center
            });

            var spaceItem = new TreeViewItem
            {
                Header = panel,
                IsExpanded = false,
                Padding = new Thickness(4, 2, 4, 2)
            };
            StyleTreeItem(spaceItem, C_BG, C_BG2);

            // Sous-items par regle
            foreach (var rule in rules)
            {
                Color c = RuleColors.ContainsKey(rule) ? RuleColors[rule] : C_MUTED;
                string lbl = RuleLabels.ContainsKey(rule) ? RuleLabels[rule] : rule;
                int rc = viols.Count(v => v.RuleId == rule);
                bool rCrit = viols.Any(v => v.RuleId == rule && v.Severity?.ToUpper() == "CRITICAL");

                var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 1, 0, 1) };

                // Badge regle colore
                row.Children.Add(new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(40, c.R, c.G, c.B)),
                    BorderBrush = Brush(c),
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(5, 1, 5, 1),
                    Margin = new Thickness(0, 0, 6, 0),
                    Child = new TextBlock
                    {
                        Text = rule,
                        FontSize = 9, FontWeight = FontWeights.Bold,
                        Foreground = Brush(c)
                    }
                });

                // Description
                row.Children.Add(new TextBlock
                {
                    Text = lbl + (rc > 1 ? "  ×" + rc : ""),
                    FontSize = 11,
                    Foreground = Brush(Color.FromRgb(185, 190, 210)),
                    VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(0, 0, 8, 0)
                });

                // Severite
                Color sevC = rCrit
                    ? Color.FromRgb(255, 90, 90)
                    : Color.FromRgb(255, 180, 60);
                row.Children.Add(new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(30, sevC.R, sevC.G, sevC.B)),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(5, 1, 5, 1),
                    Child = new TextBlock
                    {
                        Text = rCrit ? "CRITIQUE" : "IMPORTANT",
                        FontSize = 9, FontWeight = FontWeights.SemiBold,
                        Foreground = Brush(sevC)
                    }
                });

                var subItem = new TreeViewItem
                {
                    Header = row,
                    Padding = new Thickness(4, 1, 4, 1)
                };
                StyleTreeItem(subItem, C_BG, C_BG2);
                spaceItem.Items.Add(subItem);
            }

            return spaceItem;
        }

        // ── Style TreeViewItem ───────────────────────────────────────────────
        private void StyleTreeItem(TreeViewItem item, Color bg, Color hover)
        {
            item.Background = Brush(bg);
            item.MouseEnter += (s, e) => ((TreeViewItem)s).Background = Brush(hover);
            item.MouseLeave += (s, e) => ((TreeViewItem)s).Background = Brush(bg);
        }

        // =====================================================================
        //  FILTRES
        // =====================================================================
        private void OnAllChecked()
        {
            _filters.Clear();
            foreach (var b in _filterBtns.Values) b.IsChecked = false;
            RebuildTree();
        }

        private void OnRuleChecked(string rule)
        {
            _btnAll.IsChecked = false;
            _filters.Add(rule);
            RebuildTree();
        }

        private void OnRuleUnchecked(string rule)
        {
            _filters.Remove(rule);
            if (_filters.Count == 0) _btnAll.IsChecked = true;
            RebuildTree();
        }

        // =====================================================================
        //  HELPERS
        // =====================================================================

        private static ToggleButton MakeFilterButton(string text, Color color, bool isChecked)
        {
            return new ToggleButton
            {
                Content = text,
                IsChecked = isChecked,
                Margin = new Thickness(0, 0, 5, 4),
                Padding = new Thickness(8, 3, 8, 3),
                FontSize = 10,
                FontWeight = FontWeights.SemiBold,
                Foreground = new SolidColorBrush(color),
                Background = new SolidColorBrush(Color.FromArgb(30, color.R, color.G, color.B)),
                BorderBrush = new SolidColorBrush(color),
                BorderThickness = new Thickness(1),
                Cursor = System.Windows.Input.Cursors.Hand
            };
        }

        private static SolidColorBrush Brush(Color c) => new SolidColorBrush(c);
    }
}
