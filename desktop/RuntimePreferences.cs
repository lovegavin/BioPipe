using System.Text;
using System.Text.Json;
using Microsoft.Win32;

namespace BioPipe.Desktop;

internal static class RuntimePreferences
{
    // Bootstrap only, independent of canvas profiles. Keep this tiny contract in
    // sync with biopipe/runtime.py; profile resolution still belongs to Python.
    internal static string UserHome => Environment.GetEnvironmentVariable("USERPROFILE")
        is { Length: > 0 } home ? home : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    internal static string FilePath => Path.GetFullPath(
        Environment.GetEnvironmentVariable("BIOPIPE_RUNTIME_CONFIG") is { Length: > 0 } value
            ? value : ".biopipe/runtime.json", UserHome);

    internal static string? Read()
    {
        try
        {
            using var json = JsonDocument.Parse(File.ReadAllText(FilePath));
            var root = json.RootElement;
            if (root.GetProperty("schema_version").GetInt32() != 1) return null;
            var python = root.GetProperty("python").GetString();
            return python is not null && Path.IsPathFullyQualified(python) ? python : null;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or JsonException
            or KeyNotFoundException or InvalidOperationException or FormatException or ArgumentException)
        { return null; }
    }

    internal static void Save(string python)
    {
        var file = FilePath;
        var directory = Path.GetDirectoryName(file)!;
        Directory.CreateDirectory(directory);
        var temp = Path.Combine(directory, ".runtime-" + Guid.NewGuid().ToString("N") + ".tmp");
        try
        {
            File.WriteAllText(temp, JsonSerializer.Serialize(new { schema_version = 1, python },
                new JsonSerializerOptions { WriteIndented = true }) + "\n", new UTF8Encoding(false));
            File.Move(temp, file, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }

    internal static IEnumerable<string> CondaPrefixes()
    {
        // Conda records environments even when Explorer has no conda/activation in PATH.
        string[] lines;
        try { lines = File.ReadAllLines(Path.Combine(UserHome, ".conda/environments.txt")); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { yield break; }
        foreach (var line in lines)
        {
            var prefix = line.Trim();
            if (Path.IsPathFullyQualified(prefix)) yield return prefix;
        }
    }

    internal static IEnumerable<string> RegisteredPython()
    {
        // Read the standard PEP 514 registrations. Never write the Windows registry.
        var paths = new List<string>();
        foreach (var hive in new[] { RegistryHive.CurrentUser, RegistryHive.LocalMachine })
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(hive, view);
                using var python = baseKey.OpenSubKey(@"Software\Python");
                if (python is null) continue;
                foreach (var company in python.GetSubKeyNames())
                {
                    if (company.Equals("PyLauncher", StringComparison.OrdinalIgnoreCase)) continue;
                    using var vendor = python.OpenSubKey(company);
                    if (vendor is null) continue;
                    foreach (var tag in vendor.GetSubKeyNames())
                    {
                        using var location = vendor.OpenSubKey(tag + @"\InstallPath");
                        if (location is null) continue;
                        // Wrapper interpreters needing custom arguments are not bare Python runtimes.
                        if (location.GetValue("ExecutableArguments") is string arguments && arguments.Length > 0) continue;
                        var executable = location.GetValue("ExecutablePath") as string;
                        if (executable is null && company.Equals("PythonCore", StringComparison.OrdinalIgnoreCase)
                            && location.GetValue("") is string prefix)
                            executable = Path.Combine(prefix, "python.exe");
                        if (executable is not null && Path.IsPathFullyQualified(executable)) paths.Add(executable);
                    }
                }
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.Security.SecurityException) { }
        }
        return paths;
    }
}
