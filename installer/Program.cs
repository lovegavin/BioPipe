using System.Diagnostics;
using System.Text.Json;
using System.Runtime.InteropServices;
using System.Text;

namespace BioPipe.Setup;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        bool unattended = args.Contains("--quiet") || args.Contains("--cli");
        if (unattended || args.Contains("--help") || args.Contains("-h")) SetupConsole.Attach();
        if (args.Contains("--help") || args.Contains("-h"))
        {
            Console.WriteLine("""
                Operon Setup
                Operon_Setup.exe [--install] [--install-dir DIRECTORY]
                Operon_Setup.exe --quiet --install-dir DIRECTORY [--result FILE.json] [--no-register]
                Operon_Setup.exe --uninstall --quiet --install-dir ACTUAL_DIRECTORY [--result FILE.json]

                --cli             Alias for --quiet; no windows or application launch.
                --result FILE     Save the same JSON result printed to stdout.
                --no-register     Do not create shortcuts or Windows uninstall registration.
                --payload ZIP     Use a local payload matching this installer's embedded checksum.
                --help, -h        Show this help without installing.

                Progress goes to stderr; the final result is JSON on stdout.
                Exit codes: 0 success, 1 installation failure/cancellation, 2 invalid arguments.
                An occupied, unmanaged destination uses an Operon child directory. The result
                reports the actual directory. Existing user files and profiles are preserved.
                """);
            return 0;
        }
        string? resultFile = null;
        try
        {
            var values = new Dictionary<string, string>(); var flags = new HashSet<string>();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] is "--quiet" or "--cli" or "--install" or "--uninstall" or "--no-register" or "--uninstall-worker") flags.Add(args[i]);
                else if (args[i] is "--install-dir" or "--payload" or "--result")
                {
                    var key = args[i];
                    if (++i == args.Length || args[i].StartsWith("--")) throw new ArgumentException("缺少参数值：" + key);
                    values.Add(key, args[i]);
                }
                else throw new ArgumentException("未知安装参数：" + args[i]);
            }
            values.TryGetValue("--result", out resultFile);
            if (flags.Contains("--install") && flags.Contains("--uninstall")) throw new ArgumentException("Choose --install or --uninstall, not both.");
            var spec = InstallFiles.EmbeddedSpec();
            var options = new InstallOptions(values.GetValueOrDefault("--install-dir") ?? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Operon Studio"),
                values.GetValueOrDefault("--payload"), !flags.Contains("--no-register"));
            bool uninstall = flags.Contains("--uninstall");
            // A running executable cannot remove itself. Only copy this small
            // helper when invoked from the installation that is being removed.
            if (uninstall && !unattended && !flags.Contains("--uninstall-worker") &&
                string.Equals(Path.GetDirectoryName(Environment.ProcessPath), Path.GetFullPath(options.InstallDir), StringComparison.OrdinalIgnoreCase))
            {
                var folder = Path.Combine(Path.GetTempPath(), "Operon-Uninstall-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(folder); var helper = Path.Combine(folder, "Operon_Uninstall.exe");
                File.Copy(Environment.ProcessPath!, helper);
                var start = new ProcessStartInfo(helper) { UseShellExecute = false, CreateNoWindow = true };
                foreach (var arg in args) start.ArgumentList.Add(arg);
                start.ArgumentList.Add("--uninstall-worker");
                using var worker = Process.Start(start) ?? throw new IOException("Could not start the uninstall worker.");
                return 0;
            }
            if (unattended)
            {
                var engine = new InstallEngine(spec, new SetupConsole.Progress());
                using var cancellation = new CancellationTokenSource();
                ConsoleCancelEventHandler stop = (_, e) => { e.Cancel = true; cancellation.Cancel(); };
                Console.CancelKeyPress += stop;
                try
                {
                    if (!uninstall) options = options with { InstallDir = InstallEngine.ResolveDestination(options.InstallDir) };
                    var result = uninstall ? engine.Uninstall(options.InstallDir) : engine.Install(options, cancellation.Token).GetAwaiter().GetResult();
                    return SetupConsole.Result(result, resultFile) ? 0 : 1;
                }
                catch (Exception error)
                {
                    var result = new InstallResult("failed", options.InstallDir, null, null, engine.LogPath, error.Message);
                    SetupConsole.Result(result, resultFile);
                    return 1;
                }
                finally { Console.CancelKeyPress -= stop; }
            }
            ApplicationConfiguration.Initialize();
            using var window = new SetupWindow(spec, options, uninstall, resultFile);
            Application.Run(window); return window.ExitCode;
        }
        catch (Exception error)
        {
            if (unattended) SetupConsole.Result(new { status = "failed", message = error.Message }, resultFile);
            else MessageBox.Show(error.Message, "Operon Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return error is ArgumentException ? 2 : 1;
        }
    }
}

internal static class SetupConsole
{
    internal static bool Result<T>(T result, string? resultFile)
    {
        try
        {
            if (resultFile is not null)
            {
                var path = Path.GetFullPath(resultFile);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                InstallFiles.AtomicJson(path, result);
            }
        }
        catch (Exception error)
        {
            Console.WriteLine(JsonSerializer.Serialize(new { status = "failed",
                message = "Could not save the result file: " + error.Message, installationResult = result }, InstallFiles.Json));
            return false;
        }
        Console.WriteLine(JsonSerializer.Serialize(result, InstallFiles.Json));
        return true;
    }
    [DllImport("kernel32.dll")] private static extern bool AttachConsole(uint processId);
    [DllImport("kernel32.dll")] private static extern IntPtr GetStdHandle(int which);
    internal static void Attach()
    {
        var output = GetStdHandle(-11);
        if (output == IntPtr.Zero || output == new IntPtr(-1)) AttachConsole(uint.MaxValue);
        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
        Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
    }
    internal sealed class Progress : IProgress<InstallProgress>
    {
        public void Report(InstallProgress value) => Console.Error.WriteLine($"[{value.Percent}%] {value.Message}");
    }
}

internal sealed class SetupWindow : Form
{
    private readonly InstallOptions options;
    private readonly bool uninstall;
    private readonly string? resultFile;
    private readonly InstallEngine engine;
    private readonly TextBox destination = new();
    private readonly Label state = new();
    private readonly ProgressBar progress = new();
    private readonly Button action = new SetupActionButton(), cancel = new(), browse = new();
    private readonly LinkLabel logs = new();
    private CancellationTokenSource? cancellation;
    private InstallResult? completed;
    private bool running;
    internal int ExitCode { get; private set; } = 1;

    internal SetupWindow(PayloadSpec spec, InstallOptions options, bool uninstall, string? resultFile)
    {
        this.options = options; this.uninstall = uninstall; this.resultFile = resultFile;
        Text = uninstall ? "Uninstall Operon" : "Operon Setup";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        ClientSize = new Size(630, 400); MinimumSize = MaximumSize = Size;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen; BackColor = Color.FromArgb(249, 249, 250);
        Font = new Font("Microsoft YaHei UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
        var title = new Label { Text = uninstall ? "卸载 Operon Studio" : "安装 Operon Studio", AutoSize = true,
            Location = new Point(32, 28), Font = new Font("Microsoft YaHei UI", 22, FontStyle.Bold) };
        var subtitle = new Label { Text = uninstall ? "软件将被移除，用户档案和分析数据会保留。" :
            $"{spec.Version}  ·  内置运行环境，无需预先安装 Python", Location = new Point(34, 88), Size = new Size(560, 30), ForeColor = Color.DimGray };
        var label = new Label { Text = "安装位置", AutoSize = true, Location = new Point(34, 145) };
        destination.SetBounds(34, 175, 462, 32); destination.Text = options.InstallDir; destination.ReadOnly = uninstall;
        browse.SetBounds(506, 173, 90, 34); browse.Text = "更改"; browse.Enabled = !uninstall;
        browse.Click += (_, _) => { using var dialog = new FolderBrowserDialog { InitialDirectory = destination.Text, Description = "选择 Operon 安装目录" };
            if (dialog.ShowDialog(this) == DialogResult.OK) destination.Text = dialog.SelectedPath; };
        state.SetBounds(34, 222, 562, 52); state.Text = uninstall ? "仅移除本安装程序管理的软件文件。" : "创建独立环境。旧档案保留，可稍后导入路线。";
        progress.SetBounds(34, 284, 562, 6); progress.Style = ProgressBarStyle.Continuous;
        logs.SetBounds(34, 335, 150, 30); logs.Text = "查看安装日志"; logs.Visible = false;
        engine = new InstallEngine(spec, new Progress<InstallProgress>(value => { state.Text = value.Message; progress.Value = Math.Clamp(value.Percent, 0, 100); }));
        logs.LinkClicked += (_, _) => { Process.Start(new ProcessStartInfo(engine.LogPath) { UseShellExecute = true }); };
        cancel.SetBounds(370, 327, 104, 40); cancel.Text = "取消";
        cancel.Click += (_, _) => { if (running) { cancellation?.Cancel(); cancel.Enabled = false; state.Text = "正在安全停止，请稍候…"; } else Close(); };
        action.SetBounds(486, 327, 110, 40); action.Text = uninstall ? "卸载" : "安装";
        action.BackColor = Color.FromArgb(35, 35, 39); action.ForeColor = Color.White; action.FlatStyle = FlatStyle.Flat;
        action.Click += async (_, _) => {
            if (running) return;
            if (completed is not null)
            {
                if (completed.Executable is not null)
                {
                    var launch = new ProcessStartInfo(completed.Executable) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(completed.Executable) };
                    launch.ArgumentList.Add("--profile-dir"); launch.ArgumentList.Add(completed.Profile!); Process.Start(launch);
                }
                Close(); return;
            }
            running = true; action.Text = uninstall ? "卸载中…" : "安装中…";
            action.Enabled = browse.Enabled = false; destination.ReadOnly = true; logs.Visible = true;
            progress.Value = 0; cancel.Text = "取消"; cancel.Enabled = true;
            cancellation = new CancellationTokenSource();
            try
            {
                var target = uninstall ? destination.Text : InstallEngine.ResolveDestination(destination.Text);
                destination.Text = target;
                completed = await Task.Run(async () => uninstall ? engine.Uninstall(target) :
                    await engine.Install(options with { InstallDir = target }, cancellation.Token));
                destination.Text = completed.InstallDir;
                ExitCode = 0; action.Text = uninstall ? "完成" : "打开 Operon"; action.Enabled = true; cancel.Text = "关闭"; cancel.Enabled = true;
                SaveResult(completed);
            }
            catch (Exception error)
            {
                state.Text = error is OperationCanceledException ? "安装已取消。可修改目录后重试，原有文件已保留。" : "安装未完成。可修改目录后重试，详情见日志。";
                SaveResult(new InstallResult("failed", destination.Text, null, null, engine.LogPath, error.Message));
                if (error is not OperationCanceledException) MessageBox.Show(this, error.Message, "Operon Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                running = false; cancellation.Dispose(); cancellation = null;
                if (completed is null)
                {
                    action.Text = uninstall ? "重试卸载" : "重新安装"; action.Enabled = true;
                    browse.Enabled = !uninstall; destination.ReadOnly = uninstall;
                    cancel.Text = "关闭"; cancel.Enabled = true;
                }
            }
        };
        Controls.AddRange([title, subtitle, label, destination, browse, state, progress, logs, cancel, action]);
        FormClosing += (_, e) => { if (running) { e.Cancel = true; cancellation?.Cancel(); cancel.Enabled = false; } };
    }

    private void SaveResult(InstallResult result)
    {
        if (resultFile is null) return;
        try
        {
            var path = Path.GetFullPath(resultFile);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            InstallFiles.AtomicJson(path, result);
        }
        catch (Exception error)
        {
            MessageBox.Show(this, "结果文件未保存：" + error.Message + "\n安装状态可在窗口及日志中查看。",
                "Operon Setup", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}

internal sealed class SetupActionButton : Button
{
    protected override void OnPaint(PaintEventArgs e)
    {
        if (Enabled) { base.OnPaint(e); return; }
        // WinForms' themed disabled text is almost invisible on a dark flat button.
        e.Graphics.Clear(Color.FromArgb(224, 225, 229));
        TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, Color.FromArgb(65, 66, 72),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
    }
}
