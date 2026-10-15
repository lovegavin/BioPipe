using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace BioPipe.Desktop;

internal static class WebViewBootstrap
{
    public static async Task<string> Ensure(string install, Action<string> progress, CancellationToken cancellation)
    {
        try { return CoreWebView2Environment.GetAvailableBrowserVersionString(); }
        catch (WebView2RuntimeNotFoundException) { }
        var installer = Path.Combine(install, "runtime", "MicrosoftEdgeWebview2Setup.exe");
        var receipt = Path.Combine(install, "runtime", "webview2.json");
        if (!File.Exists(installer) || !File.Exists(receipt))
            throw new InvalidOperationException("缺少 WebView2。请使用包含环境的完整发行包，或安装 Microsoft Edge WebView2 Runtime。");
        using var info = JsonDocument.Parse(File.ReadAllText(receipt));
        await using (var input = File.OpenRead(installer)) {
            var digest = Convert.ToHexString(await SHA256.HashDataAsync(input, cancellation));
            if (!digest.Equals(info.RootElement.GetProperty("sha256").GetString(), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("WebView2 安装文件校验失败，请重新解压完整发行包。");
        }
        progress("正在准备 WebView2…\n首次启动需要联网，请稍候。");
        var start = new ProcessStartInfo(installer) { UseShellExecute = false, CreateNoWindow = true };
        start.ArgumentList.Add("/silent"); start.ArgumentList.Add("/install");
        using var process = Process.Start(start) ?? throw new InvalidOperationException("无法启动 WebView2 安装程序。");
        try { await process.WaitForExitAsync(cancellation).WaitAsync(TimeSpan.FromMinutes(5), cancellation); }
        catch { if (!process.HasExited) process.Kill(true); throw; }
        // The official installer can return an already-installed status; verify
        // the actual runtime instead of treating an exit code as readiness.
        try { return CoreWebView2Environment.GetAvailableBrowserVersionString(); }
        catch (WebView2RuntimeNotFoundException) {
            throw new InvalidOperationException($"WebView2 准备失败（{process.ExitCode}）。请检查网络后重新打开软件。");
        }
    }
}
