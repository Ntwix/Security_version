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
        // ── Couleurs style clair (comme TrappesFormDialog) ────────────────────
        private static readonly SolidColorBrush BR_BG       = new SolidColorBrush(Colors.White);
        private static readonly SolidColorBrush BR_BG2      = new SolidColorBrush(Color.FromRgb(245, 245, 245));
        private static readonly SolidColorBrush BR_BG3      = new SolidColorBrush(Color.FromRgb(230, 230, 230));
        private static readonly SolidColorBrush BR_BORDER   = new SolidColorBrush(Color.FromRgb(180, 180, 180));
        private static readonly SolidColorBrush BR_TEXT     = new SolidColorBrush(Color.FromRgb(30,  30,  30));
        private static readonly SolidColorBrush BR_MUTED    = new SolidColorBrush(Color.FromRgb(100, 100, 100));
        private static readonly SolidColorBrush BR_HEADER   = new SolidColorBrush(Color.FromRgb(0,  84, 166));
        private static readonly SolidColorBrush BR_HDR_TXT  = new SolidColorBrush(Colors.White);

        // Couleurs par règle
        private static readonly Dictionary<string, Color> RuleColors = new Dictionary<string, Color>
        {
            { "ELEC-001", Color.FromRgb( 50, 120, 220) },
            { "ELEC-002", Color.FromRgb(100, 160, 255) },
            { "ELEC-003", Color.FromRgb(255, 140,  40) },
            { "ELEC-004", Color.FromRgb(220,  60,  60) },
            { "GAINE-001", Color.FromRgb(180,   0,   0) },
            { "GAINE-002", Color.FromRgb(200,   0, 200) },
            { "GAINE-003", Color.FromRgb(  0, 140,   0) },
            { "GAINE-004", Color.FromRgb(160,  90,   0) },
            { "GAINE-005", Color.FromRgb( 90,   0, 160) },
        };

        private static readonly Dictionary<string, string> RuleLabels = new Dictionary<string, string>
        {
            { "ELEC-001", "Sécurité générale" },
            { "ELEC-002", "Ventilation"        },
            { "ELEC-003", "Porte"              },
            { "ELEC-004", "Zone IP65"          },
            { "GAINE-001", "Chute objets"      },
            { "GAINE-002", "Croisement CF/CFA" },
            { "GAINE-003", "Trappes accès"     },
            { "GAINE-004", "Surcharge support" },
            { "GAINE-005", "Calcul charge"     },
        };

        // Zones et leurs règles
        private static readonly Dictionary<string, string[]> ZoneRules = new Dictionary<string, string[]>
        {
            { "ELEC",  new[] { "ELEC-001", "ELEC-002", "ELEC-003", "ELEC-004" } },
            { "GAINE", new[] { "GAINE-001", "GAINE-002", "GAINE-003", "GAINE-004", "GAINE-005" } },
        };

        private static readonly Dictionary<string, string> ZoneLabels = new Dictionary<string, string>
        {
            { "ELEC",  "Zone 1 — Locaux Électriques" },
            { "GAINE", "Zone 2 — Gaines Techniques"  },
        };

        private static readonly Dictionary<string, Color> ZoneColors = new Dictionary<string, Color>
        {
            { "ELEC",  Color.FromRgb(  0,  84, 166) },
            { "GAINE", Color.FromRgb(160,  60,   0) },
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

        // ── État ──────────────────────────────────────────────────────────────
        private AnalysisResults _results;
        private string _activeZone   = null; // "ELEC" | "GAINE" | null = tout
        private string _activeRule   = null; // "ELEC-002" etc. | null = zone entière

        // ── Contrôles ─────────────────────────────────────────────────────────
        private TextBlock   _txtStats;
        private StackPanel  _statBars;
        private StackPanel  _filterZoneRow;
        private StackPanel  _filterRuleRow;
        private Border      _filterRuleBar;
        private TreeView    _tree;
        private readonly Dictionary<string, ToggleButton> _zoneBtns = new Dictionary<string, ToggleButton>();
        private readonly Dictionary<string, ToggleButton> _ruleBtns = new Dictionary<string, ToggleButton>();
        private ToggleButton _btnAll;

        public RiskPanelPage() { Build(); }

        // =====================================================================
        //  CONSTRUCTION UI
        // =====================================================================
        private void Build()
        {
            Background = BR_BG;
            FontFamily = new FontFamily("Segoe UI");
            FontSize   = 12;

            var root = new DockPanel();

            // ── Header bleu ──────────────────────────────────────────────────
            var header = new Border
            {
                Background = BR_HEADER,
                Padding    = new Thickness(10, 8, 10, 8)
            };
            DockPanel.SetDock(header, Dock.Top);

            var hStack = new StackPanel();

            var titleRow = new StackPanel { Orientation = Orientation.Horizontal };
            var dot = new Ellipse
            {
                Width = 9, Height = 9,
                Fill  = new SolidColorBrush(Color.FromRgb(100, 220, 120)),
                Margin = new Thickness(0, 0, 8, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            titleRow.Children.Add(dot);
            titleRow.Children.Add(new TextBlock
            {
                Text       = "CHU — Zones à Risque",
                FontSize   = 14, FontWeight = FontWeights.Bold,
                Foreground = BR_HDR_TXT,
                VerticalAlignment = VerticalAlignment.Center
            });
            hStack.Children.Add(titleRow);

            _txtStats = new TextBlock
            {
                Text       = "Aucune analyse lancée",
                FontSize   = 10,
                Foreground = new SolidColorBrush(Color.FromRgb(200, 210, 230)),
                Margin     = new Thickness(17, 3, 0, 4)
            };
            hStack.Children.Add(_txtStats);

            _statBars = new StackPanel { Margin = new Thickness(17, 0, 0, 0) };
            hStack.Children.Add(_statBars);

            header.Child = hStack;
            root.Children.Add(header);

            // ── Filtres Niveau 1 : Zone ──────────────────────────────────────
            var filterZoneBar = new Border
            {
                Background      = BR_BG2,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(8, 6, 8, 6)
            };
            DockPanel.SetDock(filterZoneBar, Dock.Top);

            var fzStack = new StackPanel();
            fzStack.Children.Add(new TextBlock
            {
                Text       = "FILTRER PAR ZONE",
                FontSize   = 9, FontWeight = FontWeights.Bold,
                Foreground = BR_MUTED,
                Margin     = new Thickness(0, 0, 0, 5)
            });

            _filterZoneRow = new StackPanel { Orientation = Orientation.Horizontal };

            _btnAll = MakeZoneButton("Tout afficher", Color.FromRgb(60, 60, 60), true);
            _btnAll.Checked += (s, e) => { _activeZone = null; _activeRule = null; RefreshRuleButtons(); RebuildTree(); };
            _filterZoneRow.Children.Add(_btnAll);

            foreach (var kvp in ZoneRules)
            {
                string zoneKey = kvp.Key;
                Color  c       = ZoneColors[zoneKey];
                var btn = MakeZoneButton(ZoneLabels[zoneKey], c, false);
                btn.Tag      = zoneKey;
                btn.Checked  += (s, e) => OnZoneChecked((string)((ToggleButton)s).Tag);
                btn.Unchecked += (s, e) => { _activeZone = null; _activeRule = null; _btnAll.IsChecked = true; RefreshRuleButtons(); RebuildTree(); };
                _zoneBtns[zoneKey] = btn;
                _filterZoneRow.Children.Add(btn);
            }

            fzStack.Children.Add(_filterZoneRow);
            filterZoneBar.Child = fzStack;
            root.Children.Add(filterZoneBar);

            // ── Filtres Niveau 2 : Règles (visible seulement quand une zone est sélectionnée) ──
            _filterRuleBar = new Border
            {
                Background      = BR_BG,
                BorderBrush     = BR_BORDER,
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding         = new Thickness(8, 5, 8, 5),
                Visibility      = Visibility.Collapsed
            };
            DockPanel.SetDock(_filterRuleBar, Dock.Top);

            var frStack = new StackPanel();
            frStack.Children.Add(new TextBlock
            {
                Text       = "FILTRER PAR RÈGLE",
                FontSize   = 9, FontWeight = FontWeights.Bold,
                Foreground = BR_MUTED,
                Margin     = new Thickness(0, 0, 0, 4)
            });
            _filterRuleRow = new StackPanel { Orientation = Orientation.Horizontal };
            frStack.Children.Add(_filterRuleRow);
            _filterRuleBar.Child = frStack;
            root.Children.Add(_filterRuleBar);

            // ── TreeView ─────────────────────────────────────────────────────
            var scroll = new ScrollViewer
            {
                VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Background = BR_BG
            };
            _tree = new TreeView
            {
                Background      = BR_BG,
                BorderThickness = new Thickness(0),
                Padding         = new Thickness(0, 4, 0, 4),
                Foreground      = BR_TEXT
            };
            scroll.Content = _tree;
            root.Children.Add(scroll);

            Content = root;
        }

        // =====================================================================
        //  MISE À JOUR RÉSULTATS
        // =====================================================================
        public void UpdateResults(AnalysisResults results, string zone)
        {
            _results    = results;
            _activeZone = null;
            _activeRule = null;

            _btnAll.IsChecked = true;
            foreach (var b in _zoneBtns.Values) b.IsChecked = false;
            _filterRuleBar.Visibility = Visibility.Collapsed;

            int total = results?.Violations?.Count ?? 0;
            _txtStats.Text = $"Zone {zone}   —   {total} violations";

            // Barres stats par règle
            _statBars.Children.Clear();
            var byRule = (results?.Violations ?? new List<ViolationData>())
                .GroupBy(v => v.RuleId ?? "")
                .Where(g => RuleColors.ContainsKey(g.Key))
                .OrderBy(g => g.Key);

            foreach (var grp in byRule)
            {
                Color  c   = RuleColors[grp.Key];
                string lbl = RuleLabels.ContainsKey(grp.Key) ? RuleLabels[grp.Key] : grp.Key;
                double pct = total > 0 ? (double)grp.Count() / total : 0;

                var row = new Grid { Margin = new Thickness(0, 1, 0, 1) };
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(90) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

                var lbTxt = new TextBlock
                {
                    Text = grp.Key, FontSize = 9, FontWeight = FontWeights.SemiBold,
                    Foreground = new SolidColorBrush(c), VerticalAlignment = VerticalAlignment.Center
                };
                Grid.SetColumn(lbTxt, 0); row.Children.Add(lbTxt);

                var barBg = new Border
                {
                    Height = 5, CornerRadius = new CornerRadius(3),
                    Background = BR_BG3, VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(4, 0, 8, 0)
                };
                var barFill = new Border
                {
                    Height = 5, CornerRadius = new CornerRadius(3),
                    Background = new SolidColorBrush(c), HorizontalAlignment = HorizontalAlignment.Left
                };
                barBg.Loaded      += (s, e) => barFill.Width = Math.Max(2, barBg.ActualWidth * pct);
                barBg.SizeChanged += (s, e) => barFill.Width = Math.Max(2, barBg.ActualWidth * pct);
                barBg.Child = barFill;
                Grid.SetColumn(barBg, 1); row.Children.Add(barBg);

                var cnt = new TextBlock
                {
                    Text = grp.Count().ToString(), FontSize = 9, FontWeight = FontWeights.Bold,
                    Foreground = new SolidColorBrush(c), VerticalAlignment = VerticalAlignment.Center
                };
                Grid.SetColumn(cnt, 2); row.Children.Add(cnt);

                _statBars.Children.Add(row);
            }

            RebuildTree();
        }

        // =====================================================================
        //  FILTRES
        // =====================================================================
        private void OnZoneChecked(string zoneKey)
        {
            _activeZone = zoneKey;
            _activeRule = null;
            _btnAll.IsChecked = false;
            foreach (var kvp in _zoneBtns)
                if (kvp.Key != zoneKey) kvp.Value.IsChecked = false;

            RefreshRuleButtons();
            RebuildTree();
        }

        private void RefreshRuleButtons()
        {
            _filterRuleRow.Children.Clear();
            _ruleBtns.Clear();

            if (_activeZone == null || !ZoneRules.ContainsKey(_activeZone))
            {
                _filterRuleBar.Visibility = Visibility.Collapsed;
                return;
            }

            _filterRuleBar.Visibility = Visibility.Visible;

            // Bouton "Toute la zone"
            var btnZoneAll = MakeRuleButton($"Tout {_activeZone}", ZoneColors[_activeZone], true);
            btnZoneAll.Checked += (s, e) => { _activeRule = null; RebuildTree(); };
            _filterRuleRow.Children.Add(btnZoneAll);

            foreach (string ruleId in ZoneRules[_activeZone])
            {
                // N'afficher que si des violations existent pour cette règle
                int cnt = _results?.Violations?.Count(v => v.RuleId == ruleId) ?? 0;
                if (cnt == 0) continue;

                Color  c   = RuleColors.ContainsKey(ruleId) ? RuleColors[ruleId] : Color.FromRgb(100, 100, 100);
                string lbl = RuleLabels.ContainsKey(ruleId) ? ruleId + "  " + RuleLabels[ruleId] : ruleId;

                var btn = MakeRuleButton(lbl + $"  ({cnt})", c, false);
                btn.Tag      = ruleId;
                btn.Checked  += (s, e) =>
                {
                    _activeRule = (string)((ToggleButton)s).Tag;
                    // Décocher les autres règles
                    foreach (var rb in _ruleBtns.Values)
                        if ((string)rb.Tag != _activeRule) rb.IsChecked = false;
                    btnZoneAll.IsChecked = false;
                    RebuildTree();
                };
                btn.Unchecked += (s, e) =>
                {
                    if (_activeRule == (string)((ToggleButton)s).Tag)
                    { _activeRule = null; btnZoneAll.IsChecked = true; RebuildTree(); }
                };
                _ruleBtns[ruleId] = btn;
                _filterRuleRow.Children.Add(btn);
            }
        }

        // =====================================================================
        //  ARBRE
        // =====================================================================
        private void RebuildTree()
        {
            _tree.Items.Clear();
            if (_results?.Violations == null) return;

            var viols = _results.Violations.AsEnumerable();

            // Appliquer filtre zone
            if (_activeZone != null && ZoneRules.ContainsKey(_activeZone))
                viols = viols.Where(v => ZoneRules[_activeZone].Contains(v.RuleId ?? ""));

            // Appliquer filtre règle
            if (_activeRule != null)
                viols = viols.Where(v => v.RuleId == _activeRule);

            var list = viols.ToList();
            if (list.Count == 0) return;

            foreach (var lvl in LevelRanges)
            {
                var lvlViols = list
                    .Where(v => v.Location != null && v.Location.Length >= 3
                                && v.Location[2] >= lvl.ZMin && v.Location[2] < lvl.ZMax)
                    .ToList();

                if (lvlViols.Count == 0) continue;

                var lvlItem = MakeLevelItem(lvl.Name, lvlViols.Count);

                foreach (var grp in lvlViols.GroupBy(v => v.SpaceName ?? "INCONNU").OrderBy(g => g.Key))
                    lvlItem.Items.Add(MakeSpaceItem(grp.Key, grp.ToList()));

                _tree.Items.Add(lvlItem);
            }
        }

        // ── Item niveau ──────────────────────────────────────────────────────
        private TreeViewItem MakeLevelItem(string name, int total)
        {
            var panel = new Grid();
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(4) });
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            panel.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var bar = new Border
            {
                Width = 4, Background = new SolidColorBrush(Color.FromRgb(0, 114, 188)),
                CornerRadius = new CornerRadius(2), VerticalAlignment = VerticalAlignment.Stretch,
                Margin = new Thickness(0, 0, 8, 0)
            };
            Grid.SetColumn(bar, 0); panel.Children.Add(bar);

            var txt = new TextBlock
            {
                Text = name, FontSize = 12, FontWeight = FontWeights.SemiBold,
                Foreground = BR_TEXT, VerticalAlignment = VerticalAlignment.Center
            };
            Grid.SetColumn(txt, 1); panel.Children.Add(txt);

            var badge = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(0, 114, 188)),
                CornerRadius = new CornerRadius(10),
                Padding = new Thickness(7, 2, 7, 2),
                VerticalAlignment = VerticalAlignment.Center,
                Child = new TextBlock
                {
                    Text = total.ToString(), FontSize = 10, FontWeight = FontWeights.Bold,
                    Foreground = BR_HDR_TXT
                }
            };
            Grid.SetColumn(badge, 2); panel.Children.Add(badge);

            var item = new TreeViewItem
            {
                Header = panel, IsExpanded = false,
                Padding = new Thickness(4, 3, 4, 3),
                Background = BR_BG2
            };
            item.MouseEnter += (s, e) => ((TreeViewItem)s).Background = BR_BG3;
            item.MouseLeave += (s, e) => ((TreeViewItem)s).Background = BR_BG2;
            return item;
        }

        // ── Item espace ──────────────────────────────────────────────────────
        private TreeViewItem MakeSpaceItem(string spaceName, List<ViolationData> viols)
        {
            var rules    = viols.Select(v => v.RuleId ?? "").Distinct().OrderBy(r => r).ToList();
            bool hasCrit = viols.Any(v => v.Severity?.ToUpper() == "CRITIQUE" || v.Severity?.ToUpper() == "CRITICAL");

            var panel = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 1, 0, 1) };

            foreach (var rule in rules)
            {
                Color c = RuleColors.ContainsKey(rule) ? RuleColors[rule] : Color.FromRgb(130, 130, 130);
                panel.Children.Add(new Ellipse
                {
                    Width = 7, Height = 7, Fill = new SolidColorBrush(c),
                    Margin = new Thickness(0, 0, 3, 0), VerticalAlignment = VerticalAlignment.Center
                });
            }

            panel.Children.Add(new TextBlock
            {
                Text = spaceName, FontSize = 11, FontWeight = FontWeights.SemiBold,
                Foreground = hasCrit ? new SolidColorBrush(Color.FromRgb(180, 0, 0)) : BR_TEXT,
                VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(2, 0, 8, 0)
            });
            panel.Children.Add(new TextBlock
            {
                Text = viols.Count + " viol.", FontSize = 9, Foreground = BR_MUTED,
                VerticalAlignment = VerticalAlignment.Center
            });

            var spaceItem = new TreeViewItem
            {
                Header = panel, IsExpanded = false,
                Padding = new Thickness(4, 2, 4, 2), Background = BR_BG
            };
            spaceItem.MouseEnter += (s, e) => ((TreeViewItem)s).Background = BR_BG2;
            spaceItem.MouseLeave += (s, e) => ((TreeViewItem)s).Background = BR_BG;

            foreach (var rule in rules)
            {
                Color  c    = RuleColors.ContainsKey(rule) ? RuleColors[rule] : Color.FromRgb(130, 130, 130);
                string lbl  = RuleLabels.ContainsKey(rule) ? RuleLabels[rule] : rule;
                int    rc   = viols.Count(v => v.RuleId == rule);
                bool   rCrit = viols.Any(v => v.RuleId == rule &&
                    (v.Severity?.ToUpper() == "CRITIQUE" || v.Severity?.ToUpper() == "CRITICAL"));

                var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 1, 0, 1) };

                row.Children.Add(new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(30, c.R, c.G, c.B)),
                    BorderBrush = new SolidColorBrush(c), BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(3), Padding = new Thickness(5, 1, 5, 1),
                    Margin = new Thickness(0, 0, 6, 0),
                    Child = new TextBlock
                    {
                        Text = rule, FontSize = 9, FontWeight = FontWeights.Bold,
                        Foreground = new SolidColorBrush(c)
                    }
                });

                row.Children.Add(new TextBlock
                {
                    Text = lbl + (rc > 1 ? "  ×" + rc : ""),
                    FontSize = 11, Foreground = BR_TEXT,
                    VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0)
                });

                Color sevC = rCrit ? Color.FromRgb(200, 40, 40) : Color.FromRgb(200, 120, 0);
                row.Children.Add(new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(25, sevC.R, sevC.G, sevC.B)),
                    BorderBrush = new SolidColorBrush(Color.FromArgb(80, sevC.R, sevC.G, sevC.B)),
                    BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(5, 1, 5, 1),
                    Child = new TextBlock
                    {
                        Text = rCrit ? "CRITIQUE" : "HAUTE",
                        FontSize = 9, FontWeight = FontWeights.SemiBold,
                        Foreground = new SolidColorBrush(sevC)
                    }
                });

                var subItem = new TreeViewItem
                {
                    Header = row, Padding = new Thickness(4, 1, 4, 1), Background = BR_BG
                };
                subItem.MouseEnter += (s2, e2) => ((TreeViewItem)s2).Background = BR_BG2;
                subItem.MouseLeave += (s2, e2) => ((TreeViewItem)s2).Background = BR_BG;
                spaceItem.Items.Add(subItem);
            }

            return spaceItem;
        }

        // =====================================================================
        //  HELPERS BOUTONS
        // =====================================================================
        private static ToggleButton MakeZoneButton(string text, Color color, bool isChecked)
        {
            return new ToggleButton
            {
                Content   = text,
                IsChecked = isChecked,
                Margin    = new Thickness(0, 0, 6, 0),
                Padding   = new Thickness(10, 4, 10, 4),
                FontSize  = 10, FontWeight = FontWeights.SemiBold,
                Foreground      = new SolidColorBrush(isChecked ? Colors.White : color),
                Background      = new SolidColorBrush(isChecked
                    ? color
                    : Color.FromArgb(20, color.R, color.G, color.B)),
                BorderBrush     = new SolidColorBrush(color),
                BorderThickness = new Thickness(1),
                Cursor          = System.Windows.Input.Cursors.Hand
            };
        }

        private static ToggleButton MakeRuleButton(string text, Color color, bool isChecked)
        {
            return new ToggleButton
            {
                Content   = text,
                IsChecked = isChecked,
                Margin    = new Thickness(0, 0, 4, 3),
                Padding   = new Thickness(7, 3, 7, 3),
                FontSize  = 9, FontWeight = FontWeights.SemiBold,
                Foreground      = new SolidColorBrush(color),
                Background      = new SolidColorBrush(Color.FromArgb(20, color.R, color.G, color.B)),
                BorderBrush     = new SolidColorBrush(color),
                BorderThickness = new Thickness(1),
                Cursor          = System.Windows.Input.Cursors.Hand
            };
        }
    }
}
