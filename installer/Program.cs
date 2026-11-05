using System.Diagnostics;
using System.Text.Json;

namespace BioPipe.Setup;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        string? resultFile = null;
        try
        {
            var values = new Dictionary<string, string>(); var flags = new HashSet<string>();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] is "--quiet" or "--uninstall" or "--no-register" or "--uninstall-worker") flags.Add(args[i]);
                else if (args[i] is "--install-dir" or "--payload" or "--result")
                {
                    var key = args[i];
                    if (++i == args.Length || args[i].StartsWith("--")) throw new ArgumentException("缺少参数值：" + key);
                    values.Add(key, args[i]);
                }
                else throw new ArgumentException("未知安装参数：" + args[i]);
            }
            values.TryGetValue("--result", out resultFile);
            var spec = InstallFiles.EmbeddedSpec();
            var options = new InstallOptions(values.GetValueOrDefault("--install-dir") ?? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "BioPipe Studio"),
                values.GetValueOrDefault("--payload"), !flags.Contains("--no-register"));
            bool uninstall = flags.Contains("--uninstall");
            // A running executable cannot remove itself. Only copy this small
            // helper when invoked from the installation that is being removed.
            if (uninstall && !flags.Contains("--uninstall-worker") &&
                string.Equals(Path.GetDirectoryName(Environment.ProcessPath), Path.GetFullPath(options.InstallDir), StringComparison.OrdinalIgnoreCase))
            {
                var folder = Path.Combine(Path.GetTempPath(), "BioPipe-Uninstall-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(folder); var helper = Path.Combine(folder, "BioPipe_Uninstall.exe");
                File.Copy(Environment.ProcessPath!, helper);
                var start = new ProcessStartInfo(helper) { UseShellExecute = false, CreateNoWindow = true };
                foreach (var arg in args) start.ArgumentList.Add(arg);
                start.ArgumentList.Add("--uninstall-worker"); Process.Start(start); return 0;
            }
            if (flags.Contains("--quiet"))
            {
                var engine = new InstallEngine(spec, new Progress<InstallProgress>());
                try
                {
                    var result = uninstall ? engine.Uninstall(options.InstallDir) : engine.Install(options, CancellationToken.None).GetAwaiter().GetResult();
                    if (resultFile is not null) InstallFiles.AtomicJson(Path.GetFullPath(resultFile), result);
                    return 0;
                }
                catch (Exception error)
                {
                    if (resultFile is not null) InstallFiles.AtomicJson(Path.GetFullPath(resultFile),
                        new InstallResult("failed", options.InstallDir, null, null, engine.LogPath, error.Message));
                    return 1;
                }
            }
            using var window = new SetupWindow(spec, options, uninstall, resultFile);
            Application.Run(window); return window.ExitCode;
        }
        catch (Exception error)
        {
            if (resultFile is not null) InstallFiles.AtomicJson(Path.GetFullPath(resultFile), new { status = "failed", message = error.Message });
            if (!args.Contains("--quiet")) MessageBox.Show(error.Message, "BioPipe Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
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
    private readonly Button action = new(), cancel = new(), browse = new();
    private readonly LinkLabel logs = new();
    private readonly CancellationTokenSource cancellation = new();
    private InstallResult? completed;
    private bool running;
    internal int ExitCode { get; private set; } = 1;

    internal SetupWindow(PayloadSpec spec, InstallOptions options, bool uninstall, string? resultFile)
    {
        this.options = options; this.uninstall = uninstall; this.resultFile = resultFile;
        Text = uninstall ? "Uninstall BioPipe" : "BioPipe Setup";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        ClientSize = new Size(630, 400); MinimumSize = MaximumSize = Size;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen; BackColor = Color.FromArgb(249, 249, 250);
        Font = new Font("Microsoft YaHei UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
        var title = new Label { Text = uninstall ? "卸载 BioPipe Studio" : "安装 BioPipe Studio", AutoSize = true,
            Location = new Point(32, 28), Font = new Font("Microsoft YaHei UI", 22, FontStyle.Bold) };
        var subtitle = new Label { Text = uninstall ? "软件将被移除，用户档案和分析数据会保留。" :
            $"{spec.Version}  ·  内置运行环境，无需预先安装 Python", Location = new Point(34, 88), Size = new Size(560, 30), ForeColor = Color.DimGray };
        var label = new Label { Text = "安装位置", AutoSize = true, Location = new Point(34, 145) };
        destination.SetBounds(34, 175, 462, 32); destination.Text = options.InstallDir; destination.ReadOnly = uninstall;
        browse.SetBounds(506, 173, 90, 34); browse.Text = "更改"; browse.Enabled = !uninstall;
        browse.Click += (_, _) => { using var dialog = new FolderBrowserDialog { InitialDirectory = destination.Text, Description = "选择 BioPipe 安装目录" };
            if (dialog.ShowDialog(this) == DialogResult.OK) destination.Text = dialog.SelectedPath; };
        state.SetBounds(34, 222, 562, 52); state.Text = uninstall ? "仅移除本安装程序管理的软件文件。" : "创建独立环境。旧档案保留，可稍后导入路线。";
        progress.SetBounds(34, 284, 562, 6); progress.Style = ProgressBarStyle.Continuous;
        logs.SetBounds(34, 335, 150, 30); logs.Text = "查看安装日志"; logs.Visible = false;
        engine = new InstallEngine(spec, new Progress<InstallProgress>(value => { state.Text = value.Message; progress.Value = Math.Clamp(value.Percent, 0, 100); }));
        logs.LinkClicked += (_, _) => { Process.Start(new ProcessStartInfo(engine.LogPath) { UseShellExecute = true }); };
        cancel.SetBounds(370, 327, 104, 40); cancel.Text = "取消";
        cancel.Click += (_, _) => { if (running) { cancellation.Cancel(); cancel.Enabled = false; state.Text = "正在安全停止，请稍候…"; } else Close(); };
        action.SetBounds(486, 327, 110, 40); action.Text = uninstall ? "卸载" : "安装";
        action.BackColor = Color.FromArgb(35, 35, 39); action.ForeColor = Color.White; action.FlatStyle = FlatStyle.Flat;
        action.Click += async (_, _) => {
            if (completed is not null)
            {
                if (completed.Executable is not null)
                {
                    var launch = new ProcessStartInfo(completed.Executable) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(completed.Executable) };
                    launch.ArgumentList.Add("--profile-dir"); launch.ArgumentList.Add(completed.Profile!); Process.Start(launch);
                }
                Close(); return;
            }
            running = true; action.Enabled = browse.Enabled = false; destination.ReadOnly = true; logs.Visible = true;
            try
            {
                var target = destination.Text;
                completed = await Task.Run(async () => uninstall ? engine.Uninstall(target) :
                    await engine.Install(options with { InstallDir = target }, cancellation.Token));
                if (resultFile is not null) InstallFiles.AtomicJson(Path.GetFullPath(resultFile), completed);
                ExitCode = 0; action.Text = uninstall ? "完成" : "打开 BioPipe"; action.Enabled = true; cancel.Text = "关闭"; cancel.Enabled = true;
            }
            catch (Exception error)
            {
                state.Text = error is OperationCanceledException ? "安装已取消。原有软件与用户档案已保留。" : "安装未完成，请查看日志。";
                if (resultFile is not null) InstallFiles.AtomicJson(Path.GetFullPath(resultFile), new InstallResult("failed", destination.Text, null, null, engine.LogPath, error.Message));
                if (error is not OperationCanceledException) MessageBox.Show(this, error.Message, "BioPipe Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                cancel.Text = "关闭"; cancel.Enabled = true;
            }
            finally { running = false; }
        };
        Controls.AddRange([title, subtitle, label, destination, browse, state, progress, logs, cancel, action]);
        FormClosing += (_, e) => { if (running) { e.Cancel = true; cancellation.Cancel(); cancel.Enabled = false; } };
    }
}
