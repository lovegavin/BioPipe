using System.Diagnostics;
using System.IO.Compression;
using System.Text;
using BioPipe.Setup;

var root = Path.GetFullPath(args.Single());
if (Directory.Exists(root)) throw new Exception("Use a fresh test directory");
Directory.CreateDirectory(root);
var checks = 0;
void Check(bool value, string name) { if (!value) throw new Exception(name); checks++; }
void Reject(Action action, string name) { try { action(); } catch (InvalidDataException) { checks++; return; } throw new Exception(name); }

foreach (var bad in new[] { "../outside", "/absolute", "C:/absolute", "folder\\file", "x:stream", "folder/../file", "CON.txt", "file.", "trailing " })
    Reject(() => InstallFiles.Inside(root, bad), "accepted unsafe path " + bad);
var outside = Path.Combine(Path.GetDirectoryName(root)!, "never-delete");
Reject(() => InstallFiles.DeleteOwnedStage(root, outside), "accepted outside cleanup");
var input = new ProcessStartInfo("unused.exe");
foreach (var variable in new[] { "BIOPIPE_PYTHON", "BIOPIPE_STUDIO_HOME", "BIOPIPE_BASE_PATHS", "BIOPIPE_ENVIRONMENTS_ROOT", "OPERON_HOME", "OPERON_RUNTIME_CONFIG", "PYTHONPATH", "PYTHONHOME", "CONDA_PREFIX", "VIRTUAL_ENV", "PIP_TARGET" }) input.Environment[variable] = "old";
input.Environment["HTTPS_PROXY"] = "http://proxy.example:8080";
BioPipe.Desktop.IsolatedEnvironment.Configure(input, root);
Check(!input.Environment.Keys.Any(k => k.StartsWith("BIOPIPE_")), "old BioPipe overrides survive");
Check(!input.Environment.Keys.Any(k => k.StartsWith("OPERON_")), "outside Operon overrides survive isolated setup");
Check(!input.Environment.ContainsKey("PYTHONPATH") && !input.Environment.ContainsKey("CONDA_PREFIX"), "old Python overrides survive");
Check(input.Environment["PATH"]!.StartsWith(Path.Combine(root, "runtime", "python")), "runtime path not isolated");
Check(input.Environment["HTTPS_PROXY"] == "http://proxy.example:8080", "proxy was lost");
Check(input.Environment["PIP_CONFIG_FILE"] == "NUL", "pip user config was retained");

var logProfile = Path.Combine(root, "log-profile");
var desktopLog = new BioPipe.Desktop.DesktopLog(logProfile);
desktopLog.Write("Host starting");
var desktopFile = Directory.GetFiles(Path.Combine(logProfile, "logs")).Single();
using (var lockedLog = new FileStream(desktopFile, FileMode.Open, FileAccess.Read, FileShare.Read))
{
    var timer = Stopwatch.StartNew();
    desktopLog.Write("Host stopped while log viewer has the file open");
    Check(timer.Elapsed < TimeSpan.FromSeconds(1), "logging blocked shutdown");
    var fallback = Directory.GetFiles(Path.Combine(logProfile, "logs"), "*.fallback.log").Single();
    Check(File.ReadAllText(fallback).Contains("Host stopped while log viewer"), "locked-log message lost");
}
Parallel.For(0, 30, i => desktopLog.Write("concurrent-" + i));
Check(File.ReadAllLines(desktopFile).Count(l => l.Contains("concurrent-")) == 30, "concurrent log messages lost");
var unavailable = Path.Combine(root, "not-a-profile"); File.WriteAllText(unavailable, "preserve");
new BioPipe.Desktop.DesktopLog(unavailable).Write("logging cannot crash shutdown");
Check(File.ReadAllText(unavailable) == "preserve", "logging changed blocking file");

var zip = Path.Combine(root, "payload.zip");
using (var archive = ZipFile.Open(zip, ZipArchiveMode.Create)) {
    var entry = archive.CreateEntry("Operon Studio/value.txt"); using var writer = new StreamWriter(entry.Open(), new UTF8Encoding(false)); writer.Write("hello");
}
var spec = new PayloadSpec("2.5.0", InstallFiles.Hash(zip), new FileInfo(zip).Length, 5, 1);
Check(InstallFiles.RequiredInstallBytes(spec, 4096) == 5 + 4096 + 128L * 1024 * 1024, "filesystem allocation not reserved");
Check(InstallFiles.ClusterBytes(root) > 0, "invalid allocation unit");
var engine = new InstallEngine(spec, new Progress<InstallProgress>(), Path.GetRelativePath(Environment.CurrentDirectory, Path.Combine(root, "logs")));
Check(Path.IsPathFullyQualified(engine.LogPath), "installer report path depends on child cwd");
Check(File.Exists(engine.LogPath), "log link has no file before the first install action");
Check(InstallFiles.Owner == "Operon.Studio.Install.v1", "new installer owns the old product");
var occupied = Path.Combine(root, "chosen-parent"); Directory.CreateDirectory(occupied);
var untouched = Path.Combine(occupied, "research.txt"); File.WriteAllText(untouched, "keep my files");
Check(InstallEngine.ResolveDestination(occupied) == Path.Combine(occupied, "Operon"), "nonempty parent not redirected");
Directory.CreateDirectory(Path.Combine(occupied, "Operon"));
File.WriteAllText(Path.Combine(occupied, "Operon", "notes.txt"), "keep child files");
File.WriteAllText(Path.Combine(occupied, "Operon-2"), "occupied file");
Check(InstallEngine.ResolveDestination(occupied) == Path.Combine(occupied, "Operon-3"), "child collision overwrites user files");
var ownedChild = Path.Combine(occupied, "Operon-3"); Directory.CreateDirectory(ownedChild);
File.WriteAllText(Path.Combine(ownedChild, ".biopipe-setup.json"), "{\"owner\":\"" + InstallFiles.Owner + "\"}");
Check(InstallEngine.ResolveDestination(occupied) == ownedChild, "repeat parent does not reuse owned child");
Check(InstallEngine.ResolveDestination(ownedChild) == ownedChild, "owned install was nested again");
Check(File.ReadAllText(untouched) == "keep my files" && File.ReadAllText(Path.Combine(occupied, "Operon-2")) == "occupied file", "destination resolution changed files");
File.WriteAllText(Path.Combine(ownedChild, "installation.json"), "not-json");
try { InstallEngine.ResolveDestination(occupied); throw new Exception("accepted corrupt owned receipt"); }
catch (System.Text.Json.JsonException) { checks++; }
var legacyRoot = Path.Combine(root, "legacy-biopipe"); Directory.CreateDirectory(legacyRoot);
var legacyReceipt = "{\"owner\":\"BioPipe.Studio.Install.v1\",\"version\":\"2.6.0\",\"current\":\"versions/old\",\"profile\":\"unused\",\"versions\":[\"versions/old\"],\"shortcuts\":{},\"uninstallKey\":null}";
File.WriteAllText(Path.Combine(legacyRoot, "installation.json"), legacyReceipt);
File.WriteAllText(Path.Combine(legacyRoot, "BioPipe Studio.exe"), "preserve old software");
Reject(() => engine.Uninstall(legacyRoot), "Operon uninstaller accepted a BioPipe receipt");
Check(File.ReadAllText(Path.Combine(legacyRoot, "installation.json")) == legacyReceipt &&
      File.ReadAllText(Path.Combine(legacyRoot, "BioPipe Studio.exe")) == "preserve old software", "old BioPipe installation changed");
var inspection = Path.Combine(root, "inspection.json");
const string validInspection = "{\"schema_version\":1,\"status\":\"ready\",\"issues\":[]}";
Check(InstallEngine.PersistInspection(validInspection, inspection).GetProperty("status").GetString() == "ready", "stdout inspection rejected");
var inspectionBytes = File.ReadAllBytes(inspection);
foreach (var invalid in new[] { "not json", "[]", "{}", "{\"schema_version\":\"1\",\"status\":\"ready\"}", "{\"schema_version\":1,\"status\":\"unknown\"}" })
{
    Reject(() => InstallEngine.PersistInspection(invalid, inspection), "invalid inspection accepted");
    Check(File.ReadAllBytes(inspection).SequenceEqual(inspectionBytes), "invalid inspection replaced a valid report");
}
Check(!Directory.GetFiles(root, "inspection.json.tmp-*").Any(), "inspection temporary file leaked");
var stage = Path.Combine(root, "stage"); Directory.CreateDirectory(stage);
await InstallFiles.Extract(zip, stage, spec, new Progress<InstallProgress>(), CancellationToken.None);
Check(File.ReadAllText(Path.Combine(stage, "value.txt")) == "hello", "extraction mismatch");
var corrupt = Path.Combine(root, "corrupt.zip"); File.Copy(zip, corrupt); File.AppendAllText(corrupt, "corrupt");
try { await InstallFiles.MaterializePayload(spec, root, corrupt, new Progress<InstallProgress>(), CancellationToken.None); throw new Exception("accepted corrupt archive"); }
catch (InvalidDataException) { checks++; }
var malicious = Path.Combine(root, "malicious.zip");
using (var archive = ZipFile.Open(malicious, ZipArchiveMode.Create)) archive.CreateEntry("Operon Studio/../escaped.txt");
try { await InstallFiles.Extract(malicious, stage, spec, new Progress<InstallProgress>(), CancellationToken.None); throw new Exception("accepted zip traversal"); }
catch (InvalidDataException) { checks++; }
Check(!File.Exists(Path.Combine(root, "escaped.txt")), "zip traversal wrote outside stage");
var managed = Path.Combine(root, "managed"); var version = Path.Combine(managed, "versions", "old");
Directory.CreateDirectory(version);
var profiles = Path.Combine(root, "profiles"); var id = Guid.NewGuid().ToString("N");
File.WriteAllText(Path.Combine(version, "biopipe-install.json"), "{\"profile_id\":\"" + id + "\"}");
File.WriteAllText(Path.Combine(version, "package-manifest.json"), "{\"files\":[]}");
using (var busy = new InstallLease("Local\\BioPipeStudio-" + InstallLease.Identity(Path.Combine(profiles, id)))) {
    try { InstallEngine.CleanVersion(managed, "versions/old", profiles); throw new Exception("removed active installation"); }
    catch (InvalidOperationException) { checks++; }
    Check(File.Exists(Path.Combine(version, "package-manifest.json")), "active install manifest removed");
}
InstallEngine.CleanVersion(managed, "versions/old", profiles);
Check(!Directory.Exists(version), "stopped installation not cleaned");
Console.WriteLine($"PASS: {checks} native installer checks");
