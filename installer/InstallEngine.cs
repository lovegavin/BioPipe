using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;

namespace Operon.Setup;

internal sealed record InstallOptions(string InstallDir, string? Payload = null,
    bool Register = true);
internal sealed record InstallReceipt(string Owner, string Version, string Current, string Profile,
    List<string> Versions, Dictionary<string, string> Shortcuts, string? UninstallKey);
internal sealed record InstallResult(string Status, string InstallDir, string? Executable, string? Profile,
    string Log, string? Message = null);

// Windows mutexes are thread-owned. Keep acquisition/release on one dedicated
// thread while the async installer awaits I/O on other threads.
internal sealed class InstallLease : IDisposable
{
    private readonly ManualResetEventSlim release = new();
    private readonly Thread thread;
    internal InstallLease(string name)
    {
        using var acquired = new ManualResetEventSlim();
        Exception? error = null;
        thread = new Thread(() => {
            using var mutex = new Mutex(false, name);
            var owned = false;
            try { try { owned = mutex.WaitOne(0); } catch (AbandonedMutexException) { owned = true; }
                if (!owned) throw new InvalidOperationException("Operon 或另一个安装程序正在使用此目录，请关闭后重试。"); }
            catch (Exception e) { error = e; }
            finally { acquired.Set(); }
            if (owned) { release.Wait(); mutex.ReleaseMutex(); }
        }) { IsBackground = true };
        thread.Start(); acquired.Wait();
        if (error is not null) { thread.Join(); release.Dispose(); throw error; }
    }
    public void Dispose() { release.Set(); thread.Join(); release.Dispose(); }
    internal static string Identity(string path) => Convert.ToHexString(SHA256.HashData(
        Encoding.UTF8.GetBytes(Path.GetFullPath(path).ToUpperInvariant())))[..24];
}

internal sealed class InstallEngine
{
    private readonly PayloadSpec spec;
    private readonly string work;
    internal string LogPath { get; }
    private readonly IProgress<InstallProgress> progress;
    private readonly object logGate = new();
    internal InstallEngine(PayloadSpec spec, IProgress<InstallProgress> progress, string? workRoot = null)
    {
        this.spec = spec; this.progress = progress;
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var baseDir = Path.GetFullPath(workRoot ?? (string.IsNullOrWhiteSpace(local)
            ? Path.Combine(Path.GetTempPath(), "OperonSetup") : Path.Combine(local, "Operon", "Setup")));
        try { InstallFiles.NoLinks(baseDir); Directory.CreateDirectory(baseDir); }
        catch (Exception error) when (workRoot is null && error is UnauthorizedAccessException or IOException)
        {
            // Restricted or redirected accounts may deny LocalAppData. Keep
            // installation diagnostics available in the user's writable temp.
            baseDir = Path.Combine(Path.GetTempPath(), "OperonSetup");
            InstallFiles.NoLinks(baseDir); Directory.CreateDirectory(baseDir);
        }
        work = Path.Combine(baseDir, DateTime.UtcNow.ToString("yyyyMMddTHHmmss") + "-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(work); LogPath = Path.Combine(work, "setup.log");
        Log("Operon Setup " + spec.Version + " initialized.");
    }
    private void Log(string line)
    {
        lock (logGate) File.AppendAllText(LogPath, DateTimeOffset.Now.ToString("O") + " " + line + Environment.NewLine, Encoding.UTF8);
    }
    private void Report(string message, int percent) { Log(message); progress.Report(new(message, percent)); }
    private static string ReceiptPath(string root) => Path.Combine(root, "installation.json");

    // Resolve without modifying anything. Both UI and unattended installation
    // use this policy; ownership validation is repeated under the install lease.
    internal static string ResolveDestination(string selected)
    {
        if (string.IsNullOrWhiteSpace(selected)) throw new ArgumentException("请选择安装目录。");
        var root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(selected.Trim()));
        InstallFiles.NoLinks(root);
        if (File.Exists(root)) throw new IOException("安装位置是文件，请选择文件夹。");
        if (Available(root)) return root;
        for (int suffix = 1; ; suffix++)
        {
            var child = Path.Combine(root, suffix == 1 ? "Operon" : $"Operon-{suffix}");
            InstallFiles.NoLinks(child);
            if (Available(child)) return child;
        }
    }

    private static bool Available(string root)
    {
        if (File.Exists(root)) return false;
        if (!Directory.Exists(root) || !Directory.EnumerateFileSystemEntries(root).Any()) return true;
        bool Owned(string path)
        {
            if (!File.Exists(path)) return false;
            using var value = JsonDocument.Parse(File.ReadAllText(path));
            return value.RootElement.ValueKind == JsonValueKind.Object &&
                value.RootElement.TryGetProperty("owner", out var owner) &&
                owner.ValueKind == JsonValueKind.String && owner.GetString() == InstallFiles.Owner;
        }
        bool marker;
        try { marker = Owned(Path.Combine(root, ".operon-setup.json")); }
        catch (JsonException) { marker = false; }
        bool receipt;
        try { receipt = Owned(ReceiptPath(root)); }
        catch (JsonException) when (!marker) { return false; }
        if (!marker && !receipt) return false;
        ReadReceipt(root); // Corrupt owned receipts never become an overwrite request.
        return true;
    }

    private static InstallReceipt? ReadReceipt(string root)
    {
        InstallFiles.NoLinks(root);
        if (!Directory.Exists(root)) return null;
        var file = ReceiptPath(root);
        if (!File.Exists(file))
        {
            var marker = Path.Combine(root, ".operon-setup.json");
            bool owned = File.Exists(marker) && JsonDocument.Parse(File.ReadAllText(marker)).RootElement.GetProperty("owner").GetString() == InstallFiles.Owner;
            if (!owned && Directory.EnumerateFileSystemEntries(root).Any())
                throw new InvalidOperationException("此目录已有其他文件。请选择新的安装目录；原文件会保留。");
            return null;
        }
        var receipt = JsonSerializer.Deserialize<InstallReceipt>(File.ReadAllText(file), InstallFiles.Json);
        if (receipt?.Owner != InstallFiles.Owner || !receipt.Versions.Contains(receipt.Current))
            throw new InvalidDataException("安装记录无效，请保留此目录并选择新的安装位置。");
        foreach (var item in receipt.Versions)
        {
            var path = InstallFiles.Inside(root, item);
            if (Path.GetDirectoryName(path) != Path.Combine(root, "versions")) throw new InvalidDataException("安装记录包含无效版本目录。");
        }
        return receipt;
    }

    private async Task<JsonElement> Inspect(string code, CancellationToken token)
    {
        var report = Path.Combine(work, "inspection.json");
        var start = new ProcessStartInfo(InstallFiles.Inside(code, "runtime/python/python.exe")) {
            WorkingDirectory = code, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        foreach (var arg in new[] { "-I", "-X", "utf8", "-B", "-u", InstallFiles.Inside(code, "scripts/install_maintenance.py"), "--trace-stalls" }) start.ArgumentList.Add(arg);
        Operon.Desktop.IsolatedEnvironment.Configure(start, code);
        start.Environment["PYTHONUTF8"] = "1"; start.Environment["PYTHONIOENCODING"] = "utf-8";
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        start.Environment["MPLCONFIGDIR"] = Path.Combine(work, "matplotlib");
        using var lifetime = new Operon.Desktop.ProcessLifetime();
        using var child = Process.Start(start) ?? throw new IOException("无法启动内置运行环境。");
        try { lifetime.Attach(child); } catch { child.Kill(true); throw; }
        child.StandardInput.Close();
        var output = child.StandardOutput.ReadToEndAsync();
        async Task DrainErrors()
        {
            while (await child.StandardError.ReadLineAsync() is { } line) Log("Runtime: " + line);
        }
        var errors = DrainErrors();
        try { await child.WaitForExitAsync(token).WaitAsync(TimeSpan.FromMinutes(10), token); }
        catch
        {
            if (!child.HasExited) child.Kill(true);
            await child.WaitForExitAsync();
            try { await Task.WhenAll(output, errors).WaitAsync(TimeSpan.FromSeconds(5)); }
            catch (TimeoutException) { Log("Runtime diagnostics pipe did not close after cancellation."); }
            throw;
        }
        await errors;
        var result = PersistInspection(await output, report);
        Log("inspect: " + result.GetProperty("status").GetString());
        if (child.ExitCode != 0 || result.GetProperty("status").GetString() == "blocked")
        {
            var details = result.GetProperty("issues").EnumerateArray().Select(e => e.GetProperty("message").GetString());
            var message = string.Join(Environment.NewLine, details);
            Log(message); throw new InvalidOperationException(message);
        }
        return result;
    }

    internal static JsonElement PersistInspection(string output, string report)
    {
        try
        {
            using var data = JsonDocument.Parse(output);
            var value = data.RootElement;
            if (value.ValueKind != JsonValueKind.Object ||
                !value.TryGetProperty("schema_version", out var schema) || schema.ValueKind != JsonValueKind.Number || !schema.TryGetInt32(out var version) || version != 1 ||
                !value.TryGetProperty("status", out var status) || status.ValueKind != JsonValueKind.String ||
                status.GetString() is not ("ready" or "blocked"))
                throw new InvalidDataException("运行环境检查返回了无效报告，详情见安装日志。");
            var result = value.Clone();
            InstallFiles.AtomicJson(report, result);
            return result;
        }
        catch (JsonException error)
        {
            throw new InvalidDataException("运行环境检查未返回有效报告，详情见安装日志。", error);
        }
    }

    internal async Task<InstallResult> Install(InstallOptions options, CancellationToken token)
    {
        string root = ResolveDestination(options.InstallDir);
        using var installLease = new InstallLease("Local\\OperonSetup-" + InstallLease.Identity(root));
        InstallFiles.NoLinks(root);
        var old = ReadReceipt(root);
        string? stage = null, installed = null, resolvedProfile = null;
        InstallLease? profileLease = null;
        var priorLinks = new Dictionary<string, byte[]?>();
        string? registrationKey = null;
        Dictionary<string, (object Value, RegistryValueKind Kind)>? priorRegistration = null;
        string? savedUninstaller = null;
        bool wroteUninstaller = false;
        var committed = false;
        try
        {
            var cache = Path.Combine(Path.GetDirectoryName(work)!, "cache");
            var cached = InstallFiles.Inside(cache, spec.Sha256 + ".zip");
            bool reuseCache = options.Payload is not null || (File.Exists(cached) &&
                new FileInfo(cached).Length == spec.Bytes && InstallFiles.Hash(cached) == spec.Sha256);
            var drive = new DriveInfo(Path.GetPathRoot(root)!);
            var cacheDrive = new DriveInfo(Path.GetPathRoot(cache)!);
            bool sameDrive = string.Equals(drive.Name, cacheDrive.Name, StringComparison.OrdinalIgnoreCase);
            long required = InstallFiles.RequiredInstallBytes(spec, InstallFiles.ClusterBytes(root));
            if (!reuseCache && sameDrive) required += spec.Bytes;
            if (drive.AvailableFreeSpace < required)
                throw new IOException($"安装盘空间不足，需要约 {required / 1073741824.0:F1} GiB 可用空间。");
            if (!reuseCache && !sameDrive && cacheDrive.AvailableFreeSpace < spec.Bytes + 128L * 1024 * 1024)
                throw new IOException("安装缓存所在磁盘空间不足，请释放空间后重试。");
            Report("准备安装 Operon " + spec.Version, 0);
            var payload = await InstallFiles.MaterializePayload(spec, cache, options.Payload, progress, token);
            Directory.CreateDirectory(root);
            InstallFiles.AtomicJson(Path.Combine(root, ".operon-setup.json"), new { owner = InstallFiles.Owner });
            var versions = Path.Combine(root, "versions"); Directory.CreateDirectory(versions);
            stage = Path.Combine(versions, ".install-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(stage);
            InstallFiles.AtomicJson(Path.Combine(stage, ".operon-install.json"), new { owner = InstallFiles.Owner, version = spec.Version });
            await InstallFiles.Extract(payload, stage, spec, progress, token);
            Report("正在核对已安装文件…", 76); InstallFiles.VerifyPackage(stage, spec, token);
            var profileId = Guid.NewGuid().ToString("N");
            InstallFiles.AtomicJson(Path.Combine(stage, "operon-install.json"),
                new { schema_version = 1, isolated = true, profile_id = profileId, product = "operon" });
            Report("正在验证独立运行环境…", 82);
            var inspection = await Inspect(stage, token);
            resolvedProfile = inspection.GetProperty("profile").GetProperty("profile_dir").GetString()
                ?? throw new InvalidDataException("用户档案路径无效。");
            if ((resolvedProfile.TrimEnd('\\') + "\\").StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("用户档案必须位于安装目录之外，以便升级和卸载时保留。");
            profileLease = new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(resolvedProfile));
            token.ThrowIfCancellationRequested();
            // A fresh profile is never populated from an old registry or target.
            if (Directory.Exists(resolvedProfile)) throw new IOException("新档案目录已存在，请重新运行安装程序。");
            Report("正在启用独立安装…", 90);
            var relative = "versions/" + spec.Version + "-" + Guid.NewGuid().ToString("N")[..12];
            installed = InstallFiles.Inside(root, relative);
            Directory.Move(stage, installed); stage = null;
            var shortcuts = new Dictionary<string, string>();
            if (options.Register)
            {
                Report("正在创建快捷方式…", 96);
                foreach (var folder in new[] { Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon") })
                {
                    InstallFiles.NoLinks(folder);
                    Directory.CreateDirectory(folder);
                    var link = Path.Combine(folder, "Operon Studio.lnk");
                    priorLinks[link] = File.Exists(link) ? File.ReadAllBytes(link) : null;
                    CreateShortcut(link, Path.Combine(installed, "Operon Studio.exe"), resolvedProfile);
                    shortcuts[link] = InstallFiles.Hash(link);
                }
                var uninstall = Path.Combine(root, "Operon_Uninstall.exe");
                if (File.Exists(uninstall)) { savedUninstaller = Path.Combine(work, "previous-uninstaller.exe"); File.Copy(uninstall, savedUninstaller); }
                SaveUninstaller(uninstall);
                wroteUninstaller = true;
                registrationKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudio-" + InstallLease.Identity(root);
                using (var previous = Registry.CurrentUser.OpenSubKey(registrationKey))
                    if (previous is not null) priorRegistration = previous.GetValueNames().ToDictionary(k => k,
                        k => (previous.GetValue(k, null, RegistryValueOptions.DoNotExpandEnvironmentNames)!, previous.GetValueKind(k)));
                using var key = Registry.CurrentUser.CreateSubKey(registrationKey);
                key.SetValue("DisplayName", "Operon Studio"); key.SetValue("DisplayVersion", spec.Version);
                key.SetValue("Publisher", "Operon contributors"); key.SetValue("InstallLocation", root);
                key.SetValue("DisplayIcon", Path.Combine(installed, "Operon Studio.exe"));
                key.SetValue("UninstallString", $"\"{uninstall}\" --uninstall --install-dir \"{root}\"");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord); key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            }
            var allVersions = old?.Versions.ToList() ?? [];
            allVersions.Add(relative);
            var receipt = new InstallReceipt(InstallFiles.Owner, spec.Version, relative, resolvedProfile, allVersions, shortcuts, registrationKey);
            InstallFiles.AtomicJson(ReceiptPath(root), receipt); committed = true;
            // Old software is removable only through its own receipt. Failure to
            // clean an old version never redirects or blocks the fresh runtime.
            if (old is not null)
            {
                Report("正在清理旧版本；用户档案会保留…", 98);
                foreach (var previous in old.Versions)
                    try { CleanVersion(root, previous, Path.GetDirectoryName(old.Profile)!); }
                    catch (Exception cleanupError) { Log("Old version retained: " + cleanupError.Message); }
            }
            Report("安装完成", 100);
            return new("installed", root, Path.Combine(installed, "Operon Studio.exe"), resolvedProfile, LogPath);
        }
        catch (Exception error)
        {
            Log(error.ToString());
            if (!committed)
            {
                foreach (var (path, content) in priorLinks)
                    try { if (content is null) File.Delete(path); else File.WriteAllBytes(path, content); } catch (Exception e) { Log("Shortcut restore: " + e.Message); }
                if (registrationKey is not null)
                    try {
                        Registry.CurrentUser.DeleteSubKeyTree(registrationKey, false);
                        if (priorRegistration is not null) { using var key = Registry.CurrentUser.CreateSubKey(registrationKey);
                            foreach (var (name, value) in priorRegistration) key.SetValue(name, value.Value, value.Kind); }
                    } catch (Exception e) { Log("Registration restore: " + e.Message); }
                if (wroteUninstaller)
                    try { var target = Path.Combine(root, "Operon_Uninstall.exe");
                        if (savedUninstaller is not null) File.Copy(savedUninstaller, target, true); else File.Delete(target);
                    } catch (Exception e) { Log("Uninstaller restore: " + e.Message); }
                foreach (var candidate in new[] { stage, installed }.Where(p => p is not null))
                    try { InstallFiles.DeleteOwnedStage(Path.Combine(root, "versions"), candidate!); } catch (Exception e) { Log("Stage retained: " + e.Message); }
            }
            throw;
        }
        finally { profileLease?.Dispose(); }
    }

    private static void CreateShortcut(string path, string executable, string profile)
    {
        var type = Type.GetTypeFromProgID("WScript.Shell") ?? throw new NotSupportedException("无法创建 Windows 快捷方式。");
        dynamic shell = Activator.CreateInstance(type)!;
        try {
            dynamic shortcut = shell.CreateShortcut(path);
            try { shortcut.TargetPath = executable; shortcut.Arguments = $"--profile-dir \"{profile}\"";
                shortcut.IconLocation = executable + ",0";
                shortcut.WorkingDirectory = Path.GetDirectoryName(executable); shortcut.Description = "Operon Studio"; shortcut.Save(); }
            finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut); }
        } finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
    }

    private static void SaveUninstaller(string destination)
    {
        // Copy just the self-contained program, not the large appended payload.
        using var source = File.OpenRead(Environment.ProcessPath!);
        source.Seek(-32, SeekOrigin.End); byte[] footer = new byte[32]; source.ReadExactly(footer);
        if (!footer.AsSpan(0,16).SequenceEqual(InstallFiles.FooterMagic)) throw new InvalidDataException("安装包缺少卸载组件。");
        long length = BitConverter.ToInt64(footer, 16); source.Position = 0;
        var temporary = destination + ".tmp-" + Guid.NewGuid().ToString("N");
        try {
            using (var output = File.Create(temporary)) {
                byte[] buffer = new byte[1024 * 1024]; long copied = 0;
                while (copied < length) { int n = source.Read(buffer,0,(int)Math.Min(buffer.Length,length-copied));
                    if (n == 0) throw new EndOfStreamException(); output.Write(buffer,0,n); copied += n; }
            }
            File.Move(temporary, destination, true);
        } finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    internal InstallResult Uninstall(string installDir)
    {
        string root = Path.GetFullPath(installDir).TrimEnd(Path.DirectorySeparatorChar);
        using var lease = new InstallLease("Local\\OperonSetup-" + InstallLease.Identity(root));
        var receipt = ReadReceipt(root) ?? throw new InvalidOperationException("此目录没有 Operon 安装记录。");
        using var profileLease = new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(receipt.Profile));
        Report("正在卸载软件；用户档案和分析数据会保留…", 0);
        var expectedKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\OperonStudio-" + InstallLease.Identity(root);
        if (receipt.UninstallKey is not null && receipt.UninstallKey != expectedKey) throw new InvalidDataException("卸载注册信息无效。");
        var allowedLinks = new[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Operon Studio.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Operon", "Operon Studio.lnk") };
        foreach (var path in receipt.Shortcuts.Keys) {
            if (!allowedLinks.Contains(path, StringComparer.OrdinalIgnoreCase)) throw new InvalidDataException("快捷方式记录无效。");
            InstallFiles.NoLinks(path);
        }
        foreach (var relative in receipt.Versions) CleanVersion(root, relative, Path.GetDirectoryName(receipt.Profile)!, receipt.Profile);
        foreach (var (path, hash) in receipt.Shortcuts)
            if (File.Exists(path) && InstallFiles.Hash(path) == hash) File.Delete(path);
        if (receipt.UninstallKey is not null)
        {
            Registry.CurrentUser.DeleteSubKeyTree(expectedKey, false);
        }
        File.Delete(ReceiptPath(root));
        File.Delete(Path.Combine(root, ".operon-setup.json"));
        var uninstaller = Path.Combine(root,"Operon_Uninstall.exe");
        if (File.Exists(uninstaller) && !string.Equals(uninstaller, Environment.ProcessPath, StringComparison.OrdinalIgnoreCase)) File.Delete(uninstaller);
        Report("已卸载 Operon；用户档案、路线、数据和任务记录均已保留。",100);
        return new("uninstalled", root, null, receipt.Profile, LogPath);
    }

    internal static void CleanVersion(string root, string relative, string profiles, string? heldProfile = null)
        {
            var version = InstallFiles.Inside(root, relative);
            if (!Directory.Exists(version) || !File.Exists(Path.Combine(version, "package-manifest.json"))) return;
            using var identity = JsonDocument.Parse(File.ReadAllText(InstallFiles.Inside(version, "operon-install.json")));
            var id = identity.RootElement.GetProperty("profile_id").GetString();
            if (!Guid.TryParseExact(id, "N", out _)) throw new InvalidDataException("旧安装档案标识无效，原文件已保留。");
            var profile = Path.Combine(profiles, id!);
            using var versionLease = string.Equals(profile, heldProfile, StringComparison.OrdinalIgnoreCase)
                ? null : new InstallLease("Local\\OperonStudio-" + InstallLease.Identity(profile));
            // Only delete manifest-listed software files. Preserve unexpected
            // user files and any changed/linked paths for manual inspection.
            using var manifest = JsonDocument.Parse(File.ReadAllText(InstallFiles.Inside(version, "package-manifest.json")));
            foreach (var item in manifest.RootElement.GetProperty("files").EnumerateArray())
            {
                var path = InstallFiles.Inside(version, item.GetProperty("path").GetString()!);
                if (File.Exists(path) && InstallFiles.Hash(path) == item.GetProperty("sha256").GetString()) File.Delete(path);
            }
            File.Delete(Path.Combine(version, "package-manifest.json")); File.Delete(Path.Combine(version, ".operon-install.json"));
            File.Delete(Path.Combine(version, "operon-install.json"));
            void EmptyDirectories(string directory) {
                foreach (var child in Directory.EnumerateDirectories(directory)) { InstallFiles.NoLinks(child); EmptyDirectories(child); }
                if (!Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
            }
            EmptyDirectories(version);
        }
}
