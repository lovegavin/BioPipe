using System.Diagnostics;

namespace Operon.Desktop;

internal static class IsolatedEnvironment
{
    internal static void Configure(ProcessStartInfo start, string install)
    {
        foreach (var key in start.Environment.Keys.ToArray())
            if (key.StartsWith("OPERON_", StringComparison.OrdinalIgnoreCase) ||
                key.StartsWith("OPERON_", StringComparison.OrdinalIgnoreCase) ||
                key.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase) ||
                key.StartsWith("CONDA", StringComparison.OrdinalIgnoreCase) ||
                key is "VIRTUAL_ENV" or "R_HOME" or "R_LIBS" or "R_LIBS_USER" or "R_PROFILE" or "R_ENVIRON" or
                    "PIP_TARGET" or "PIP_PREFIX" or "PIP_USER" or "PIP_REQUIRE_VIRTUALENV")
                start.Environment.Remove(key);
        var python = Path.Combine(install, "runtime", "python");
        start.Environment["PATH"] = string.Join(Path.PathSeparator, python, Path.Combine(python, "Scripts"),
            Environment.GetFolderPath(Environment.SpecialFolder.System), Environment.GetFolderPath(Environment.SpecialFolder.Windows));
        start.Environment["PYTHONNOUSERSITE"] = "1";
        start.Environment["PIP_CONFIG_FILE"] = "NUL";
    }
}
