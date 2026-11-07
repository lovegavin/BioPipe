using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Operon.Setup;

internal sealed record PayloadSpec(string Version, string Sha256, long Bytes, long UnpackedBytes, int Files);
internal sealed record ManifestFile(string Path, long Bytes, string Sha256);
internal sealed record PackageManifest(string Version, bool PythonBundled, List<ManifestFile> Files);
internal sealed record InstallProgress(string Message, int Percent);

internal static class InstallFiles
{
    internal static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true, WriteIndented = true };
    internal static readonly byte[] FooterMagic = Encoding.ASCII.GetBytes("OPERON-SETUP-V1");
    internal const string Owner = "Operon.Studio.Install.v1";
    internal const string PayloadRoot = "Operon Studio/";

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool GetDiskFreeSpace(string root, out uint sectorsPerCluster,
        out uint bytesPerSector, out uint freeClusters, out uint totalClusters);

    internal static long ClusterBytes(string root) =>
        GetDiskFreeSpace(Path.GetPathRoot(Path.GetFullPath(root))!, out var sectors, out var bytes, out _, out _)
            ? checked((long)sectors * bytes) : 65536;

    // Many small Python files occupy whole filesystem allocation units.
    internal static long RequiredInstallBytes(PayloadSpec spec, long clusterBytes) =>
        checked(spec.UnpackedBytes + spec.Files * clusterBytes + 128L * 1024 * 1024);

    internal static PayloadSpec EmbeddedSpec()
    {
        using var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("Operon.Payload.json")
            ?? throw new InvalidDataException("安装包缺少版本信息。");
        var spec = JsonSerializer.Deserialize<PayloadSpec>(input, Json) ?? throw new InvalidDataException("安装包版本信息无效。");
        if (spec.Bytes <= 0 || spec.UnpackedBytes <= 0 || spec.Files <= 0 || spec.Sha256.Length != 64 ||
            !spec.Sha256.All(Uri.IsHexDigit) || !System.Version.TryParse(spec.Version, out _))
            throw new InvalidDataException("安装包版本信息无效。");
        return spec;
    }

    internal static string Inside(string root, string relative)
    {
        if (string.IsNullOrEmpty(relative) || Path.IsPathRooted(relative) || relative.Contains(':') || relative.Contains('\\'))
            throw new InvalidDataException("不安全的安装路径：" + relative);
        var components = relative.Split('/');
        if (components.Any(c => c is "" or "." or ".." || c.EndsWith(' ') || c.EndsWith('.') ||
            c.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ||
            System.Text.RegularExpressions.Regex.IsMatch(c, @"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", System.Text.RegularExpressions.RegexOptions.IgnoreCase)))
            throw new InvalidDataException("不安全的安装路径：" + relative);
        var parent = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var result = Path.GetFullPath(Path.Combine(root, Path.Combine(components)));
        if (!result.StartsWith(parent, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("安装路径超出目标目录。");
        NoLinks(root);
        var cursor = root;
        foreach (var component in components) { cursor = Path.Combine(cursor, component); NoLinks(cursor, ancestors: false); }
        return result;
    }

    internal static void NoLinks(string path, bool ancestors = true)
    {
        for (var cursor = Path.GetFullPath(path); !string.IsNullOrEmpty(cursor); cursor = ancestors ? Path.GetDirectoryName(cursor) : null)
            if ((File.Exists(cursor) || Directory.Exists(cursor)) && File.GetAttributes(cursor).HasFlag(FileAttributes.ReparsePoint))
                throw new InvalidDataException("安装路径不能包含链接或重定向目录：" + cursor);
    }

    internal static string Hash(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    internal static void AtomicJson<T>(string path, T value)
    {
        var temporary = path + ".tmp-" + Guid.NewGuid().ToString("N");
        try { File.WriteAllText(temporary, JsonSerializer.Serialize(value, Json), new UTF8Encoding(false)); File.Move(temporary, path, true); }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    internal static async Task<string> MaterializePayload(PayloadSpec spec, string cache, string? supplied,
        IProgress<InstallProgress> progress, CancellationToken token)
    {
        if (supplied is not null)
        {
            var path = Path.GetFullPath(supplied);
            if (new FileInfo(path).Length != spec.Bytes || Hash(path) != spec.Sha256)
                throw new InvalidDataException("安装文件校验失败，请重新下载安装包。");
            return path;
        }
        NoLinks(cache); Directory.CreateDirectory(cache);
        var destination = Inside(cache, spec.Sha256 + ".zip");
        if (File.Exists(destination) && new FileInfo(destination).Length == spec.Bytes && Hash(destination) == spec.Sha256)
            return destination;
        var temporary = destination + ".part-" + Guid.NewGuid().ToString("N");
        try
        {
            using var source = File.OpenRead(Environment.ProcessPath!);
            if (source.Length < 32) throw new InvalidDataException("安装包不完整。");
            source.Seek(-32, SeekOrigin.End);
            var footer = new byte[32]; source.ReadExactly(footer);
            if (!footer.AsSpan(0, 16).SequenceEqual(FooterMagic)) throw new InvalidDataException("安装包缺少内置环境。");
            long offset = BitConverter.ToInt64(footer, 16), length = BitConverter.ToInt64(footer, 24);
            if (length != spec.Bytes || offset < 64 || offset != source.Length - 32 - length)
                throw new InvalidDataException("安装包长度无效。");
            source.Position = offset;
            using var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            byte[] buffer = new byte[1024 * 1024]; long copied = 0;
            while (copied < length)
            {
                int count = await source.ReadAsync(buffer.AsMemory(0, (int)Math.Min(buffer.Length, length - copied)), token);
                if (count == 0) throw new EndOfStreamException("安装包不完整。");
                hash.AppendData(buffer, 0, count);
                await output.WriteAsync(buffer.AsMemory(0, count), token); copied += count;
                progress.Report(new("正在验证内置运行环境…", (int)(copied * 15 / length)));
            }
            if (Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant() != spec.Sha256)
                throw new InvalidDataException("安装文件校验失败，请重新下载安装包。");
            output.Close(); File.Move(temporary, destination, true);
            return destination;
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    internal static async Task Extract(string payload, string stage, PayloadSpec spec,
        IProgress<InstallProgress> progress, CancellationToken token)
    {
        using var archive = ZipFile.OpenRead(payload);
        long total = 0; int count = 0;
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in archive.Entries)
        {
            token.ThrowIfCancellationRequested();
            if (!entry.FullName.StartsWith(PayloadRoot, StringComparison.Ordinal)) throw new InvalidDataException("安装包目录无效。");
            if (((entry.ExternalAttributes >> 16) & 0xf000) == 0xa000 || (entry.ExternalAttributes & 0x400) != 0)
                throw new InvalidDataException("安装包不能包含符号链接。");
            var relative = entry.FullName[PayloadRoot.Length..];
            if (relative.Length == 0) continue;
            bool directory = relative.EndsWith('/');
            var target = Inside(stage, directory ? relative[..^1] : relative);
            if (!seen.Add(target)) throw new InvalidDataException("安装包包含重复路径。");
            if (directory) { Directory.CreateDirectory(target); continue; }
            total = checked(total + entry.Length); count++;
            if (total > spec.UnpackedBytes || count > spec.Files) throw new InvalidDataException("安装包超出声明大小。");
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            using var input = entry.Open();
            using var output = new FileStream(target, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            await input.CopyToAsync(output, token);
            if (output.Length != entry.Length) throw new InvalidDataException("安装文件长度无效。");
            if (count % 100 == 0) progress.Report(new("正在安装 Operon 和运行环境…", 15 + (int)(total * 60 / spec.UnpackedBytes)));
        }
        if (count != spec.Files || total != spec.UnpackedBytes) throw new InvalidDataException("安装包文件清单不完整。");
    }

    internal static void VerifyPackage(string directory, PayloadSpec spec, CancellationToken token)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(Inside(directory, "package-manifest.json")));
        var root = document.RootElement;
        if (root.GetProperty("version").GetString() != spec.Version || !root.GetProperty("python_bundled").GetBoolean())
            throw new InvalidDataException("安装包不是指定版本的完整运行环境。");
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in root.GetProperty("files").EnumerateArray())
        {
            token.ThrowIfCancellationRequested();
            var path = Inside(directory, item.GetProperty("path").GetString()!);
            if (!seen.Add(path) || !File.Exists(path) || new FileInfo(path).Length != item.GetProperty("bytes").GetInt64() ||
                Hash(path) != item.GetProperty("sha256").GetString())
                throw new InvalidDataException("安装文件损坏：" + Path.GetFileName(path));
        }
        foreach (var required in new[] { "Operon Studio.exe", "runtime/python/python.exe", "scripts/install_maintenance.py", "frontend/index.html" })
            if (!seen.Contains(Inside(directory, required))) throw new InvalidDataException("安装包缺少组件：" + required);
    }

    internal static void DeleteOwnedStage(string parent, string path)
    {
        // Only a task-owned stage/installation with a matching marker is removable.
        var root = Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar);
        var candidate = Path.GetFullPath(path);
        if (!string.Equals(Path.GetDirectoryName(candidate), root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("拒绝清理目标目录之外的文件。");
        NoLinks(candidate);
        var marker = Path.Combine(candidate, ".operon-install.json");
        using var json = JsonDocument.Parse(File.ReadAllText(marker));
        if (json.RootElement.GetProperty("owner").GetString() != Owner) throw new InvalidDataException("目录不属于此安装程序。");
        // Never traverse a reparse point, even if it appeared after installation.
        void Clean(string folder)
        {
            foreach (var item in Directory.EnumerateFileSystemEntries(folder))
            {
                NoLinks(item, ancestors: false);
                if (Directory.Exists(item)) Clean(item); else File.Delete(item);
            }
            Directory.Delete(folder);
        }
        Clean(candidate);
    }
}
