using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace BioPipe.Desktop;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length == 1 && args[0] == "--check-runtime")
        {
            // WinExe has redirected handles but no console code page to change.
            Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
            Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
            try
            {
                Console.WriteLine(JsonSerializer.Serialize(RuntimeLocator.Resolve(AppContext.BaseDirectory).GetAwaiter().GetResult()));
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
        }
        ApplicationConfiguration.Initialize();
        string? profileOverride = null;
        var smoke = false;
        var checkProfile = false;
        for (var i = 0; i < args.Length; i++)
        {
            if ((args[i] == "--data-dir" || args[i] == "--profile-dir") && i + 1 < args.Length) profileOverride = args[++i];
            else if (args[i] == "--smoke-test") smoke = true;
            else if (args[i] == "--check-profile") checkProfile = true;
            else return 2;
        }
        RuntimePaths runtime;
        ProfilePaths profile;
        try {
            runtime = RuntimeLocator.Resolve(AppContext.BaseDirectory).GetAwaiter().GetResult();
            profile = RuntimeLocator.ResolveProfile(runtime, profileOverride).GetAwaiter().GetResult();
            if (checkProfile) {
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
                Console.WriteLine(JsonSerializer.Serialize(profile)); return 0;
            }
        } catch (Exception error) {
            if (!smoke && !checkProfile) MessageBox.Show(error.Message, "BioPipe Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            else { Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true }); Console.Error.WriteLine(error.Message); }
            return 1;
        }
        var dataDir = profile.ProfileDir;
        var identity = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(dataDir.ToUpperInvariant())))[..24];
        var name = @"Local\BioPipeStudio-" + identity;
        using var mutex = new Mutex(true, name, out var first);
        if (!first)
        {
            try { using var signal = EventWaitHandle.OpenExisting(name + "-activate"); signal.Set(); }
            catch (WaitHandleCannotBeOpenedException) { }
            return 0;
        }
        using var activation = new EventWaitHandle(false, EventResetMode.AutoReset, name + "-activate");
        try
        {
            Directory.CreateDirectory(dataDir);
            using var form = new StudioWindow(profile, runtime, smoke, activation);
            Application.Run(form);
            return form.ExitCode;
        }
        catch (Exception error)
        {
            if (!smoke) MessageBox.Show("BioPipe Studio 无法启动。\n\n" + error.Message,
                "BioPipe Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}

internal sealed class StudioWindow : Form
{
    private readonly string dataDir;
    private readonly ProfilePaths profile;
    private readonly RuntimePaths runtime;
    private readonly bool smoke;
    private readonly WebView2 view = new() { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.White, Visible = false };
    private readonly Label status = new() { AutoSize = false, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
        Font = new Font("Segoe UI", 14), Text = "BioPipe Studio\n\n正在启动本地运行时…" };
    private readonly HttpClient http = new(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(5) };
    private readonly TaskCompletionSource<string> ready = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly CancellationTokenSource stopped = new();
    private readonly object logLock = new();
    private readonly EventWaitHandle activation;
    private ProcessLifetime? lifetime;
    private Process? backend;
    private string? origin;
    private bool frontReady, closing, allowClose;
    private TaskCompletionSource<bool>? draftSaved;
    public int ExitCode { get; private set; }

    public StudioWindow(ProfilePaths profile, RuntimePaths runtime, bool smoke, EventWaitHandle activation)
    {
        this.profile = profile; this.runtime = runtime; this.dataDir = profile.ProfileDir;
        this.smoke = smoke; this.activation = activation;
        Text = "BioPipe Studio";
        StartPosition = FormStartPosition.CenterScreen;
        var area = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1600, 1000);
        Size = new Size(Math.Min(1440, area.Width - 60), Math.Min(960, area.Height - 60));
        MinimumSize = new Size(960, 640);
        BackColor = Color.White;
        Controls.Add(status); Controls.Add(view);
        Shown += async (_, _) => await StartStudio();
        FormClosing += ClosingStudio;
    }

    private void Log(string text)
    {
        lock (logLock)
        {
            var directory = Path.Combine(dataDir, "logs");
            Directory.CreateDirectory(directory);
            File.AppendAllText(Path.Combine(directory, "desktop-" + DateTime.Now.ToString("yyyyMMdd") + ".log"),
                DateTime.Now.ToString("O") + " " + text + Environment.NewLine, Encoding.UTF8);
        }
    }

    private async Task StartStudio()
    {
        try
        {
            Log("Host starting; pid=" + Environment.ProcessId);
            // Fail before launching Python if the required browser runtime is absent.
            var browserVersion = CoreWebView2Environment.GetAvailableBrowserVersionString();
            Log("WebView2 " + browserVersion);
            stopped.Token.ThrowIfCancellationRequested();
            var python = runtime.Python;
            var script = runtime.EntryPoint;
            var frontend = runtime.Frontend;
            Log("Runtime selected; python=" + python + "; backend=" + runtime.BackendRoot);
            var workspace = profile.Workspace;
            Log("Profile=" + dataDir + "; registry=" + profile.Registry);
            Directory.CreateDirectory(workspace);
            var preferredPort = 0;
            var portFile = Path.Combine(dataDir, "port.txt");
            if (File.Exists(portFile)) int.TryParse(File.ReadAllText(portFile), out preferredPort);
            if (preferredPort < 0 || preferredPort > 65535) preferredPort = 0;
            var start = new ProcessStartInfo(python) {
                WorkingDirectory = workspace, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
            };
            foreach (var value in new[] { "-B", "-u", script, "--profile-dir", dataDir, "--frontend", frontend,
                "--port", preferredPort.ToString(), "--wait-for-host" })
                start.ArgumentList.Add(value);
            if (profile.MigrateLegacy) start.ArgumentList.Add("--migrate-legacy");
            start.Environment["PYTHONIOENCODING"] = "utf-8";
            start.Environment["PYTHONUTF8"] = "1";
            lifetime = new ProcessLifetime();
            backend = new Process { StartInfo = start, EnableRaisingEvents = true };
            backend.OutputDataReceived += (_, e) => {
                if (e.Data is null) return;
                if (e.Data.StartsWith("BIOPIPE_READY "))
                {
                    try { using var value = JsonDocument.Parse(e.Data[14..]); ready.TrySetResult(value.RootElement.GetProperty("url").GetString()!); }
                    catch (Exception error) { ready.TrySetException(error); }
                }
                else Log("Backend: " + e.Data);
            };
            backend.ErrorDataReceived += (_, e) => { if (e.Data is not null) Log("Backend: " + e.Data); };
            backend.Exited += (_, _) => {
                ready.TrySetException(new InvalidOperationException("本地运行时提前退出。详情见 logs 文件夹。"));
                if (!closing && frontReady && !IsDisposed)
                    BeginInvoke(() => { frontReady = false; view.Visible = false; status.Text = "本地运行时已退出，请重新打开 BioPipe Studio。\n\n日志位置：" + Path.Combine(dataDir, "logs"); });
            };
            backend.Start();
            Log("Backend started; pid=" + backend.Id);
            try { lifetime.Attach(backend); }
            catch { backend.Kill(true); throw; }
            backend.BeginOutputReadLine(); backend.BeginErrorReadLine();
            await backend.StandardInput.WriteLineAsync("start");
            await backend.StandardInput.FlushAsync();
            origin = await ready.Task.WaitAsync(TimeSpan.FromSeconds(90), stopped.Token);
            var url = new Uri(origin);
            if (url.Scheme != "http" || url.Host != "127.0.0.1") throw new InvalidOperationException("运行时地址无效。");
            using var health = JsonDocument.Parse(await http.GetStringAsync(origin + "/ready", stopped.Token));
            if (health.RootElement.GetProperty("status").GetString() != "ok") throw new InvalidOperationException("本地运行时尚未就绪。");
            File.WriteAllText(portFile, url.Port.ToString());
            Log("Backend ready; " + origin);
            status.Text = "BioPipe Studio\n\n正在打开工作台…";
            var environment = await CoreWebView2Environment.CreateAsync(null, Path.Combine(dataDir, "browser"));
            if (stopped.IsCancellationRequested) return;
            await view.EnsureCoreWebView2Async(environment);
            view.CoreWebView2.Settings.AreDevToolsEnabled = false;
            view.CoreWebView2.Settings.IsStatusBarEnabled = false;
            view.CoreWebView2.Settings.IsPasswordAutosaveEnabled = false;
            view.CoreWebView2.Settings.IsGeneralAutofillEnabled = false;
            view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            view.CoreWebView2.NavigationStarting += (_, e) => {
                if (e.Uri == "about:blank" || IsLocal(e.Uri) || e.Uri.StartsWith("blob:" + origin + "/")) return;
                e.Cancel = true;
                if (e.IsUserInitiated) OpenExternal(e.Uri);
            };
            view.CoreWebView2.NewWindowRequested += (_, e) => { e.Handled = true; if (e.IsUserInitiated) OpenExternal(e.Uri); };
            view.CoreWebView2.WebMessageReceived += (_, e) => {
                if (!IsLocal(e.Source)) return;
                try
                {
                    using var message = JsonDocument.Parse(e.WebMessageAsJson);
                    switch (message.RootElement.GetProperty("type").GetString())
                    {
                        case "studio-ready":
                            frontReady = true; view.Visible = true; view.BringToFront();
                            Log("Frontend ready; operator catalog and workspace loaded");
                            if (smoke) BeginInvoke(Close);
                            break;
                        case "draft-saved": draftSaved?.TrySetResult(true); break;
                        case "draft-save-failed": draftSaved?.TrySetResult(false); break;
                    }
                }
                catch (JsonException) { }
            };
            view.CoreWebView2.NavigationCompleted += (_, e) => {
                if (!e.IsSuccess) { status.Text = "工作台加载失败：" + e.WebErrorStatus + "\n请重新打开 BioPipe Studio。"; Log(status.Text); }
            };
            view.CoreWebView2.Navigate(origin + "/");
            _ = Task.Run(() => {
                while (!stopped.IsCancellationRequested)
                    if (activation.WaitOne(500) && !IsDisposed)
                        BeginInvoke(() => { if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal; Show(); Activate(); });
            });
            // A failed JS bootstrap must produce an actionable error, not an endless splash.
            _ = MonitorFrontend();
        }
        catch (OperationCanceledException) when (stopped.IsCancellationRequested) { }
        catch (Exception error)
        {
            ExitCode = 1;
            Log(error.ToString());
            await StopBackend();
            if (smoke) { allowClose = true; Close(); return; }
            status.Text = "BioPipe Studio 启动失败\n\n" +
                (error is WebView2RuntimeNotFoundException ? "请安装 Microsoft Edge WebView2 Runtime 后重试。\nhttps://developer.microsoft.com/microsoft-edge/webview2/" : error.Message)
                + "\n\n日志位置：" + Path.Combine(dataDir, "logs");
        }
    }

    private async Task MonitorFrontend()
    {
        try
        {
            await Task.Delay(TimeSpan.FromSeconds(60), stopped.Token);
            if (frontReady || closing) return;
            Log("Frontend bootstrap timed out"); ExitCode = 1;
            if (smoke) { allowClose = true; await StopBackend(); Close(); }
            else { view.Visible = true; view.BringToFront(); } // Show React's retry/error screen.
        }
        catch (OperationCanceledException) { }
    }

    private bool IsLocal(string value) => Uri.TryCreate(value, UriKind.Absolute, out var uri) &&
        uri.GetLeftPart(UriPartial.Authority) == origin;

    private static void OpenExternal(string value)
    {
        if (Uri.TryCreate(value, UriKind.Absolute, out var uri) && uri.Scheme is "http" or "https")
            Process.Start(new ProcessStartInfo(value) { UseShellExecute = true });
    }

    private async void ClosingStudio(object? sender, FormClosingEventArgs e)
    {
        if (allowClose) return;
        e.Cancel = true;
        if (closing) return;
        closing = true;
        try
        {
            if (frontReady)
            {
                using var jobs = JsonDocument.Parse(await http.GetStringAsync(origin + "/api/jobs"));
                if (jobs.RootElement.EnumerateArray().Any(job => job.GetProperty("status").GetString() == "running") && !smoke &&
                    MessageBox.Show(this, "工作流仍在运行。退出会停止当前任务，已保存的记录和结果会保留。\n\n确定退出吗？",
                        "退出 BioPipe Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                { closing = false; return; }
                draftSaved = new(TaskCreationOptions.RunContinuationsAsynchronously);
                view.CoreWebView2.PostWebMessageAsJson("{\"type\":\"prepare-close\"}");
                var saved = await Task.WhenAny(draftSaved.Task, Task.Delay(5000)) == draftSaved.Task && await draftSaved.Task;
                if (!saved)
                {
                    Log("Draft flush failed");
                    if (smoke) ExitCode = 1;
                    else if (MessageBox.Show(this, "最新草稿未能保存。仍然退出吗？", "BioPipe Studio",
                        MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) { closing = false; return; }
                }
                else Log("Draft flushed to workspace");
            }
        }
        catch (Exception error) { Log("Closing: " + error.Message); if (smoke) ExitCode = 1; }
        await StopBackend();
        allowClose = true;
        Log("Host stopped");
        Close();
    }

    private async Task StopBackend()
    {
        stopped.Cancel();
        if (backend is not null)
        {
            try
            {
                if (!backend.HasExited)
                {
                    await backend.StandardInput.WriteLineAsync("shutdown");
                    backend.StandardInput.Close();
                    await backend.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(8));
                }
                Log("Backend stopped; exit=" + backend.ExitCode);
            }
            catch (Exception error)
            {
                Log("Backend cleanup: " + error.Message);
                try { if (!backend.HasExited) backend.Kill(true); } catch (InvalidOperationException) { }
            }
        }
        lifetime?.Dispose();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            stopped.Cancel(); lifetime?.Dispose(); view.Dispose(); backend?.Dispose(); http.Dispose();
        }
        base.Dispose(disposing);
    }
}
