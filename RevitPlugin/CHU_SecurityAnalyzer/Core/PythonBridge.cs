using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.Serialization.Json;
using System.Text;
using System.Threading;

namespace CHU_SecurityAnalyzer.Core
{
    /// <summary>
    /// Pont entre le plugin Revit C# et le backend Python.
    ///
    /// Workflow :
    /// 1. Sérialise ExtractedData en JSON
    /// 2. Lance python main.py --zone N --input extracted_data.json
    /// 3. Lit le JSON résultat (analysis_results.json)
    /// </summary>
    public class PythonBridge
    {
        private readonly string _pythonExe;
        private readonly string _mainPyPath;
        private readonly string _workingDir;

        public PythonBridge(string pythonExe, string projectDir)
        {
            _pythonExe = pythonExe;
            _mainPyPath = Path.Combine(projectDir, "main.py");
            _workingDir = projectDir;

            if (!File.Exists(_mainPyPath))
                throw new FileNotFoundException($"main.py introuvable: {_mainPyPath}");
        }

        /// <summary>
        /// Exporte les données extraites en JSON pour le Python
        /// </summary>
        public string ExportDataToJson(ExtractedData data, string outputPath = null)
        {
            if (outputPath == null)
                outputPath = Path.Combine(Path.GetTempPath(), "chu_extracted_data_" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".json");

            var serializer = new DataContractJsonSerializer(typeof(ExtractedData));
            using (var stream = new FileStream(outputPath, FileMode.Create))
            {
                serializer.WriteObject(stream, data);
            }

            return outputPath;
        }

        /// <summary>
        /// Lance l'analyse Python pour une zone donnée
        /// </summary>
        /// <param name="zone">Numéro de zone (1, 2, 3, 4) ou "all"</param>
        /// <param name="inputJsonPath">Chemin vers le JSON des données extraites</param>
        /// <returns>Chemin vers le fichier résultats JSON</returns>
        public string RunAnalysis(string zone, string inputJsonPath)
        {
            string outputDir = Path.Combine(_workingDir, "resultats", $"zone{zone}");
            Directory.CreateDirectory(outputDir);

            string args = $"\"{_mainPyPath}\" --zone {zone} --input \"{inputJsonPath}\" --output \"{outputDir}\"";

            var processInfo = new ProcessStartInfo
            {
                FileName = _pythonExe,
                Arguments = args,
                WorkingDirectory = _workingDir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };

            var process = new Process { StartInfo = processInfo };

            // Lire stdout et stderr dans des threads separes pour eviter le deadlock
            string output = "";
            string errors = "";
            var sbOut = new StringBuilder();
            var sbErr = new StringBuilder();

            process.Start();

            var tOut = new Thread(() => { sbOut.Append(process.StandardOutput.ReadToEnd()); });
            var tErr = new Thread(() => { sbErr.Append(process.StandardError.ReadToEnd()); });
            tOut.Start();
            tErr.Start();

            bool finished = process.WaitForExit(120000); // 120s timeout
            tOut.Join(5000);
            tErr.Join(5000);

            output = sbOut.ToString();
            errors = sbErr.ToString();

            if (!finished)
            {
                try { process.Kill(); } catch { }
                throw new TimeoutException("L'analyse Python a depasse 120 secondes.\nOutput: " + output + "\nErrors: " + errors);
            }

            if (process.ExitCode != 0)
            {
                throw new Exception("Erreur Python (code " + process.ExitCode + "):\n" + errors + "\nOutput: " + output);
            }

            string resultPath = Path.Combine(outputDir, "analysis_results.json");
            if (!File.Exists(resultPath))
            {
                throw new FileNotFoundException($"Résultats non trouvés: {resultPath}\nOutput: {output}");
            }

            return resultPath;
        }

        /// <summary>
        /// Lit et désérialise les résultats d'analyse
        /// </summary>
        public AnalysisResults ReadResults(string resultJsonPath)
        {
            var serializer = new DataContractJsonSerializer(typeof(AnalysisResults));
            using (var stream = new FileStream(resultJsonPath, FileMode.Open, FileAccess.Read))
            {
                return (AnalysisResults)serializer.ReadObject(stream);
            }
        }

        /// <summary>
        /// Détecte automatiquement l'exécutable Python
        /// </summary>
        public static string FindPythonExe(string projectDir)
        {
            // 1. venv local dans le projet
            string venvPython = Path.Combine(projectDir, "venv", "Scripts", "python.exe");
            if (File.Exists(venvPython)) return venvPython;

            // 2. PATH système
            string pathPython = FindInPath("python.exe");
            if (pathPython != null) return pathPython;

            // 3. Installations courantes
            string[] commonPaths = new[]
            {
                @"C:\Python313\python.exe",
                @"C:\Python312\python.exe",
                @"C:\Python311\python.exe",
                @"C:\Python310\python.exe",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    @"Programs\Python\Python313\python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    @"Programs\Python\Python312\python.exe"),
            };

            foreach (string path in commonPaths)
            {
                if (File.Exists(path)) return path;
            }

            return null;
        }

        private static string FindInPath(string exe)
        {
            string path = Environment.GetEnvironmentVariable("PATH");
            if (path == null) return null;

            foreach (string dir in path.Split(';'))
            {
                string fullPath = Path.Combine(dir.Trim(), exe);
                if (File.Exists(fullPath)) return fullPath;
            }
            return null;
        }
    }
}
