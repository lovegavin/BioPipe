# Agent guide: repairing the environment and provisioning resources

This page is written for an agent that receives a task, discovers a missing
dependency or a missing weight/database, and has to repair the host before the
task can run. It is deliberately command-oriented: every step below is a
command the agent can execute and verify.

## 安装规模与耗时

首次托管的 Linux 安装会下载完整的 Python 依赖（PyTorch、科学计算栈、模型封装
等），**下载量约 8–12 GB**。在服务器上行 1–3 MB/s 时通常需要 1–2 小时；桌面端
断线不会丢失进度，重连或重跑安装会复用 `~/.cache/pip` 缓存。

- 进度看缓存增长：`du -sh ~/.cache/pip`（目标环境 `site-packages` 在下载阶段
  结束后才快速增长）。
- 不要清理 `~/.cache/pip` 或 `managed-v1/mamba-cache`，否则重装会从头下载。
- 需要更快时，可在桌面端用离线方式预置 wheel 目录（`--from-dir`），或让服务器
  管理员提供内网 PyPI 镜像，然后在安装器里替换 `-i` 索引地址。
- 安装完成后 `env-*/` 约 6–9 GB（含 CUDA 版 PyTorch）。

## 快速检查：服务器能否连上并安装

桌面端连接远程服务器时，先在**能上网的机器**上确认 SSH（Windows 用户直接用系统
ssh，不要经过 WSL）：

```bash
ssh -o ConnectTimeout=15 <user>@<host> 'echo SSH_OK'
```

看到 `SSH_OK` 说明 22 端口可用。若使用密钥，确保私钥 ACL 只允许当前用户读取。
Operon 只在这台服务器上写 `~/.local/share/operon/managed-v1/`（可用
`--base` 覆盖），不要求 root、Conda 或预装编译器。

安装完成后检查：

```bash
ls ~/.local/share/operon/managed-v1/                 # micromamba-2.10.0, env-*, setup-*.log
ls ~/.local/share/operon/managed-v1/env-*/operon-ready.json
tail -40 ~/.local/share/operon/managed-v1/setup-*.log
~/.local/share/operon/managed-v1/env-*/bin/python -m pip check
```

`operon-ready.json` 存在且 `pip check` 无输出即安装成功；日志里应出现
`Operon and Hi-C environment ready`。探测阶段若提示
`Optional OpenMM extras are not installed`，安装依然成功，只是 MD/能量算子需要
额外安装 conda-forge 的 `openmm`、`pdbfixer`（命令见下文）。

### 已知环境限制（按报错定位）

| 报错 | 根因 | 处理 |
| --- | --- | --- |
| `No matching distribution found for pdbfixer` | 该包只发 conda-forge | 不进入默认 pip 解析；按需 conda 安装 |
| `openmm 8.1.1` + `numpy.core.multiarray failed to import` | PyPI 的 openmm wheel 是 NumPy 1 ABI | 同上，conda-forge 提供 NumPy 2 构建 |
| `Failed building wheel for libcst` / `can't find Rust compiler` | 新版本 sdist 需要 Rust | 约束 `libcst<1.8`（cp311 wheel） |
| `Failed to build 'pyarrow'` | 新版本走 Arrow C++ 源码 | 约束 `pyarrow<22` |
| `No matching distribution found for pysam` | wheel 需 glibc ≥ 2.28 | 安装完成后由 conda-forge/bioconda 补 `pysam=0.22.1` |
| `No matching distribution found for cooltools` | 只有 sdist，且是纯 Python | 允许 sdist 的第二次安装即可覆盖 |
| `No module named 'packaging'` | 裸 venv 没有 packaging | 安装器会先自动补 packaging |
| `Install curl or wget ...` | 主机缺少下载工具 | 安装 curl 或 wget 后重试 |

## 可选的 antifold（独立环境）

`antifold` 0.3.x 固定 `numpy==1.26.*`，而 `pydeseq2>=0.5` 需要 `numpy>=2`，两者
无法在同一个解析里共存。默认安装不包含 antipfold；需要 AntiFold 逆向折叠时，
单独建一个环境并把算子的 `python_executable` 指向它：

```bash
python -m venv ~/antifold-env
~/antifold-env/bin/pip install numpy==1.26.* torch 'antifold==0.3.1'
~/antifold-env/bin/python -m antifold.main --help   # 确认权重已随包下载
```

`antifold_design` 的 `python_executable` 填 `~/antifold-env/bin/python` 即可，其余
链、采样参数不变。

## 开启 OpenMM 算子

## Decision tree

1. **Is the Python package installed?** `python -c "import operon"` and
   `python -m operon registry check`. A missing operator module is a package
   install, a missing third-party library is a pip install, and a missing
   binary (foldseek, mkdssp, prodigal, vina, pdb2pqr, fpocket) is an apt or
   build install. Never install NVIDIA drivers inside WSL; the driver comes
   from the Windows host.
2. **Is the weight or database present?**
   `python scripts/check_resources.py --json` reports `ok / partial / missing`
   per declared file. Operators that need a resource call
   `require(resource_id, operator)` and raise a message with the expected path,
   the environment variable and the install command — read that message first,
   it is authoritative.
3. **Should the resource be provisioned?** If the task can run without it, use
   the gated operator and record the boundary. If it cannot, provision it with
   the workflow below.

## Provisioning workflow

Provisioning is a **host-level, one-time** action, not part of a job.

```bash
# what is missing, per resource
python scripts/check_resources.py --json

# plan only (no network)
python scripts/provision_resources.py --root /data/operon-resources --plan

# fetch with a mirror, parallel downloads and resume
python scripts/provision_resources.py \
  --root /data/operon-resources \
  --only boltz --only esm3 \
  --mirror https://hf-mirror.com \
  --jobs 4 --retries 3 --timeout 60

# verify without touching the network
python scripts/provision_resources.py --root /data/operon-resources --offline
```

Rules the provisioner enforces:

- files are written atomically (`.part` then rename), so an interrupted run
  never leaves a truncated file under the final name;
- an existing file is verified by size and SHA-256 (when the manifest declares
  one) and skipped when valid;
- a failed checksum is deleted, never accepted;
- one provisioning process holds `.operon-provision.lock` in the root, so two
  agents cannot download the same file twice;
- `--jobs N` parallelises files, `--retries` bounds attempts, `--timeout` is a
  read timeout so a stalled socket fails instead of hanging forever.

## Slow or unstable server uplink

Downloading multi-GB weights directly onto a server with a bad uplink is the
most common source of "the agent hung". Prefer moving the bytes once:

1. On a machine with good bandwidth (or with an already provisioned cache),
   provision into a staging directory:
   `python scripts/provision_resources.py --root ~/operon-staging --only boltz`.
2. Transfer the staging directory with a resumable transfer
   (`rsync -avP --partial`, or `scp -C`), which survives disconnects.
3. On the server, copy from the staged tree and verify:
   `python scripts/provision_resources.py --root /data/operon-resources --from-dir ~/operon-staging --offline`.
   `--from-dir` re-checks size and SHA-256 before renaming each file.

If a mirror is acceptable, `--mirror https://hf-mirror.com` rewrites
`huggingface.co` URLs; `--rewrite OLD=NEW` handles any other prefix.

## Environment repair commands

```bash
python -m pip install -e . --no-deps --no-build-isolation   # editable install
python -m pip install <library>                              # missing import
apt-get install -y dssp prodigal vienna-rna                  # missing binary
python -m operon registry build && python -m operon registry check
```

Do not rebuild the registry by hand; run the two commands above and require
`errors []`. A stale registry is reported as
`ValueError: Implementation code hash mismatch: <operator>`.

## Recording the result

After provisioning, record in the task report:

- resource ids and file names provisioned, with their root paths;
- whether each file was `downloaded`, `copied` (from `--from-dir`) or `skipped`
  (already valid);
- remaining `missing` / `failed` entries and the exact remedy command;
- the environment variables that point to the roots (for example
  `OPERON_BOLTZ_CACHE=/data/operon-resources`), so a later agent finds the
  same files instead of downloading them again.

## Do not

- do not download multi-GB files inside a job step: jobs have wall-clock
  budgets and a lost connection wastes the whole job;
- do not bypass size or checksum verification to "make it work";
- do not install Linux NVIDIA drivers inside WSL, and do not assume a GPU is
  available — `device=cpu` must remain a supported path;
- do not write new defaults or absolute local paths into operator JSON; use the
  resource manifest (`src/task/step/steps/resources.json`) and environment variables;
- do not claim a resource works until a minimal real run succeeded; otherwise
  report it as gated, as `docs/design/hard_capability_status.md` does.
