using System.Text;

namespace Operon.Desktop;

internal sealed class DesktopLog(string profile)
{
    private readonly object gate = new();
    internal void Write(string text)
    {
        lock (gate)
        {
            var directory = Path.Combine(profile, "logs");
            var now = DateTime.Now;
            var line = now.ToString("O") + " " + text + Environment.NewLine;
            var name = "desktop-" + now.ToString("yyyyMMdd");
            // A viewer/backup tool may hold the normal log without write sharing.
            // Diagnostics must not interrupt the backend callbacks or shutdown.
            if (!Append(directory, name + ".log", line) &&
                !Append(directory, name + "-" + Environment.ProcessId + ".fallback.log", line))
                System.Diagnostics.Debug.WriteLine(line);
        }
    }

    private static bool Append(string directory, string name, string line)
    {
        try
        {
            Directory.CreateDirectory(directory);
            using var stream = new FileStream(Path.Combine(directory, name), FileMode.Append,
                FileAccess.Write, FileShare.ReadWrite | FileShare.Delete);
            using var writer = new StreamWriter(stream, new UTF8Encoding(false));
            writer.Write(line);
            return true;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }
}
