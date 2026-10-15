using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace BioPipe.Desktop;

internal sealed class DesktopConfiguration
{
    public string BackendRoot { get; set; } = "../..";
    public string Python { get; set; } = "auto";
    public string EntryPoint { get; set; } = "scripts/desktop_server.py";
    public string Frontend { get; set; } = "frontend";
    public bool BundledRuntime { get; set; }
}

internal sealed record RuntimePaths(string BackendRoot, string Python, string EntryPoint, string Frontend);
internal sealed record ProfilePaths(string ProfileDir, string Workspace, string DataDir, string Registry, bool MigrateLegacy);
internal sealed class RuntimeNotFoundException(string message, bool automatic) : InvalidOperationException(message)
{
    public bool Automatic { get; } = automatic;
}

internal static class RuntimeLocator
{
    public static async Task<ProfilePaths> ResolveProfile(RuntimePaths runtime, string? profileOverride)
    {
        // Python owns the directory policy. Do not duplicate home/AppData rules
        // in the host: that previously split Explorer and development profiles.
        var start = new ProcessStartInfo(runtime.Python) {
            WorkingDirectory = runtime.BackendRoot, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var value in new[] { "-I", "-X", "utf8", "-B", runtime.EntryPoint, "--resolve-profile" }) start.ArgumentList.Add(value);
        if (profileOverride is not null) {
            start.ArgumentList.Add("--profile-dir"); start.ArgumentList.Add(profileOverride);
        }
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        using var process = Process.Start(start) ?? throw new InvalidOperationException("无法解析 Studio 数据目录。");
        process.StandardInput.Close();
        var output = process.StandardOutput.ReadToEndAsync();
        var errors = process.StandardError.ReadToEndAsync();
        try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(15)); }
        catch { if (!process.HasExited) process.Kill(true); throw; }
        if (process.ExitCode != 0) throw new InvalidOperationException(await errors);
        using var json = JsonDocument.Parse(await output);
        var data = json.RootElement;
        return new(data.GetProperty("profile_dir").GetString()!, data.GetProperty("workspace").GetString()!,
            data.GetProperty("data_dir").GetString()!, data.GetProperty("registry").GetString()!,
            data.GetProperty("migrate_legacy").GetBoolean());
    }

    public static async Task<RuntimePaths> Resolve(string install, string? pythonOverride = null)
    {
        var configuration = JsonSerializer.Deserialize<DesktopConfiguration>(
            File.ReadAllText(Path.Combine(install, "biopipe-desktop.json")),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidDataException("桌面配置文件无效。");
        var backendRoot = Expand(configuration.BundledRuntime ? configuration.BackendRoot
            : Environment.GetEnvironmentVariable("BIOPIPE_BACKEND_ROOT") ?? configuration.BackendRoot, install);
        var script = Expand(configuration.EntryPoint, backendRoot);
        var frontend = Expand(configuration.Frontend, install);
        if (!File.Exists(script))
            throw new FileNotFoundException("找不到后端入口。请将客户端保留在项目的 dist/BioPipe Studio 目录，" +
                "或设置 biopipe-desktop.json 的 backendRoot / BIOPIPE_BACKEND_ROOT。\n" + script);
        if (!File.Exists(Path.Combine(frontend, "index.html")))
            throw new FileNotFoundException("前端资源不完整。请保留 exe 旁边的 frontend 文件夹。");
        // A full package owns its interpreter. Do not silently use a remembered
        // or system Python when the bundled environment is missing or damaged.
        var bundled = configuration.BundledRuntime && pythonOverride is null;
        var setting = bundled ? Path.Combine(install, "runtime", "python", "python.exe")
            : pythonOverride ?? Environment.GetEnvironmentVariable("BIOPIPE_PYTHON") ?? configuration.Python;
        var automatic = string.IsNullOrWhiteSpace(setting) || setting.Equals("auto", StringComparison.OrdinalIgnoreCase);
        var candidates = automatic ? Candidates(backendRoot) : Explicit(setting, backendRoot);
        var failures = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var candidate in candidates)
        {
            if (!seen.Add(candidate.File + " " + candidate.Argument)) continue;
            try
            {
                var python = await Probe(candidate, backendRoot);
                return new(backendRoot, python, script, frontend);
            }
            catch (Exception error) when (error is not OutOfMemoryException)
            { failures.Add(candidate.File + ": " + error.Message); }
        }
        if (bundled)
            throw new RuntimeNotFoundException("随附运行环境不完整或无法启动。请重新解压完整发行包，并保留 runtime 文件夹。\n\n" +
                string.Join("\n", failures), false);
        throw new RuntimeNotFoundException("未找到可运行 BioPipe 的 Python 3.11+ 环境。" +
            "请在已有环境安装 requirements-studio.txt，或用 BIOPIPE_PYTHON / biopipe-desktop.json 的 python 指定解释器。" +
            (automatic ? "\n已检查已记住的环境、项目环境、活动环境、PATH、Conda 环境记录和 Windows Python 注册项。"
                : "\n明确指定的解释器未通过检查。") +
            "\n\n" + string.Join("\n", failures), automatic);
    }

    private static string Expand(string path, string root) =>
        Path.GetFullPath(Environment.ExpandEnvironmentVariables(path), root);

    private sealed record Candidate(string File, string? Argument = null);

    private static IEnumerable<Candidate> Explicit(string value, string root)
    {
        value = Environment.ExpandEnvironmentVariables(value.Trim().Trim('"'));
        if (Path.IsPathRooted(value) || value.Contains('/') || value.Contains('\\'))
            yield return new(Expand(value, root));
        else
        {
            var path = OnPath(value).FirstOrDefault()
                ?? throw new FileNotFoundException("PATH 中找不到指定的 Python 命令：" + value);
            yield return new(path);
        }
    }

    private static IEnumerable<Candidate> Candidates(string root)
    {
        // Full releases own their runtime. A remembered interpreter from another
        // installation must never take precedence over the adjacent tested one.
        var bundled = Path.Combine(root, "runtime", "python", "python.exe");
        if (File.Exists(bundled)) yield return new(bundled);
        // A remembered selection wins, including an environment chosen with the picker.
        // Stale hints and broken/copied venvs never hide a usable fallback.
        if (RuntimePreferences.Read() is string remembered) yield return new(remembered);
        foreach (var relative in new[] { ".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python" })
        {
            var path = Path.Combine(root, relative);
            if (File.Exists(path)) yield return new(path);
        }
        foreach (var variable in new[] { "VIRTUAL_ENV", "CONDA_PREFIX" })
        {
            var prefix = Environment.GetEnvironmentVariable(variable);
            if (string.IsNullOrWhiteSpace(prefix) || !Path.IsPathFullyQualified(prefix)) continue;
            foreach (var relative in new[] { "Scripts/python.exe", "python.exe", "bin/python" })
            {
                var path = Path.Combine(prefix, relative);
                if (File.Exists(path)) yield return new(path);
            }
        }
        foreach (var command in new[] { "python", "python3" })
            foreach (var path in OnPath(command)) yield return new(path);
        foreach (var path in OnPath("py")) yield return new(path, "-3");
        foreach (var prefix in RuntimePreferences.CondaPrefixes())
            foreach (var relative in new[] { "python.exe", "Scripts/python.exe", "bin/python" })
            {
                var path = Path.Combine(prefix, relative);
                if (File.Exists(path)) yield return new(path);
            }
        foreach (var path in RuntimePreferences.RegisteredPython())
            if (File.Exists(path)) yield return new(path);
    }

    private static IEnumerable<string> OnPath(string command)
    {
        var name = Path.HasExtension(command) ? command : command + ".exe";
        foreach (var part in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
        {
            var directory = Environment.ExpandEnvironmentVariables(part.Trim().Trim('"'));
            // Ignore empty/relative entries (cwd-dependent) and Windows Store execution aliases.
            if (!Path.IsPathFullyQualified(directory) ||
                directory.TrimEnd('\\', '/').EndsWith("\\Microsoft\\WindowsApps", StringComparison.OrdinalIgnoreCase)) continue;
            var path = Path.Combine(directory, name);
            if (File.Exists(path)) yield return path;
        }
    }

    private static async Task<string> Probe(Candidate candidate, string root)
    {
        var start = new ProcessStartInfo(candidate.File) {
            WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
        };
        if (candidate.Argument is not null) start.ArgumentList.Add(candidate.Argument);
        start.ArgumentList.Add("-I");
        start.ArgumentList.Add("-c");
        start.ArgumentList.Add("import importlib.util,json,sys; " +
            "modules=['numpy','pandas','yaml','scipy','statsmodels','matplotlib','psutil','fastapi','uvicorn','jsonschema','pydantic','packaging','httpx']; " +
            "print(json.dumps({'python':sys.executable,'version':list(sys.version_info[:2])," +
            "'missing':[m for m in modules if importlib.util.find_spec(m) is None]}))");
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        using var process = Process.Start(start) ?? throw new InvalidOperationException("解释器无法启动。");
        var output = process.StandardOutput.ReadToEndAsync();
        var errors = process.StandardError.ReadToEndAsync();
        try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10)); }
        catch (TimeoutException)
        {
            try { process.Kill(true); } catch (InvalidOperationException) { }
            throw new InvalidOperationException("解释器探测超时。");
        }
        if (process.ExitCode != 0)
            throw new InvalidOperationException("解释器不可用：" + (await errors).Trim());
        using var result = JsonDocument.Parse(await output);
        var version = result.RootElement.GetProperty("version");
        if (version[0].GetInt32() < 3 || (version[0].GetInt32() == 3 && version[1].GetInt32() < 11))
            throw new InvalidOperationException("需要 Python 3.11 或更新版本。");
        var missing = result.RootElement.GetProperty("missing").EnumerateArray().Select(v => v.GetString()).ToArray();
        if (missing.Length > 0) throw new InvalidOperationException("缺少依赖：" + string.Join(", ", missing));
        var python = result.RootElement.GetProperty("python").GetString();
        if (string.IsNullOrWhiteSpace(python) || !Path.IsPathFullyQualified(python) || !File.Exists(python))
            throw new InvalidOperationException("解释器返回的可执行文件路径无效。");
        return python;
    }
}
