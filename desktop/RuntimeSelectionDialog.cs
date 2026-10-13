namespace BioPipe.Desktop;

internal sealed class RuntimeSelectionDialog : Form
{
    public RuntimePaths? SelectedRuntime { get; private set; }

    public RuntimeSelectionDialog(string install, string diagnostic)
    {
        Text = "BioPipe Studio · Python 环境";
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(620, 340);
        MinimumSize = new Size(550, 350);
        Font = new Font("Segoe UI", 10);
        BackColor = Color.FromArgb(250, 250, 250);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), ColumnCount = 1, RowCount = 4 };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.Controls.Add(new Label { Text = "选择已有的 Python 环境", AutoSize = true,
            Font = new Font("Segoe UI", 16, FontStyle.Bold), Margin = new Padding(0, 0, 0, 12) });
        layout.Controls.Add(new Label { Text = "选择环境中的 python.exe。验证通过后记住，下次双击即可启动。",
            AutoSize = true, Margin = new Padding(0, 0, 0, 16) });
        var details = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical,
            Dock = DockStyle.Fill, Text = diagnostic, BorderStyle = BorderStyle.FixedSingle };
        layout.Controls.Add(details);
        var buttons = new FlowLayoutPanel { FlowDirection = FlowDirection.RightToLeft,
            Dock = DockStyle.Fill, AutoSize = true, Padding = new Padding(0, 16, 0, 0) };
        var choose = new Button { Text = "选择 python.exe", AutoSize = true, Padding = new Padding(10, 5, 10, 5) };
        var cancel = new Button { Text = "取消", AutoSize = true, Padding = new Padding(10, 5, 10, 5), DialogResult = DialogResult.Cancel };
        buttons.Controls.Add(choose); buttons.Controls.Add(cancel); layout.Controls.Add(buttons);
        Controls.Add(layout); CancelButton = cancel; AcceptButton = choose;
        choose.Click += async (_, _) => {
            using var browser = new OpenFileDialog { Title = "选择已安装依赖的 Python 3.11+ 环境",
                Filter = "Python (python.exe)|python.exe|可执行文件 (*.exe)|*.exe", CheckFileExists = true, RestoreDirectory = true };
            if (browser.ShowDialog(this) != DialogResult.OK) return;
            choose.Enabled = cancel.Enabled = false;
            details.Text = "正在检查 Python 版本和依赖…";
            try
            {
                var runtime = await RuntimeLocator.Resolve(install, browser.FileName);
                if (IsDisposed) return;
                RuntimePreferences.Save(runtime.Python);
                SelectedRuntime = runtime;
                DialogResult = DialogResult.OK;
                Close();
            }
            catch (Exception error) { if (!IsDisposed) details.Text = error.Message; }
            finally { if (!IsDisposed) choose.Enabled = cancel.Enabled = true; }
        };
    }
}
