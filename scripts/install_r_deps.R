#!/usr/bin/env Rscript
# Install the R/Bioconductor packages used by BioPipe's optional R oracles.
#
# CRAN is fetched from the USTC mirror; Bioconductor has no working USTC/Tsinghua
# mirror for this R release, so its official HTTPS endpoint is the fallback.
# Packages are installed into the user library, so no sudo password is needed.
#
# `limma`, `fgsea`, `metafor` and `GSVA` are required by tests/test_r_oracles.py.
# `sva` and `Kendall` back the optional cross-checks in tests/test_r_oracles3.py.
# The other packages are optional references and may fail when system libraries
# (libcurl, OpenSSL, fontconfig, GSL, HiGHS, ...) are unavailable.

options(repos = c(CRAN = "https://mirrors.ustc.edu.cn/CRAN/"))
options(BioC_mirror = "https://bioconductor.org")
options(Ncpus = max(1L, min(2L, parallel::detectCores())))
options(timeout = 600)

lib <- Sys.getenv("R_LIBS_USER")
if (!nzchar(lib)) {
  lib <- file.path(path.expand("~"), "R", paste0(R.version$platform, "-library"),
                   paste(R.version$major, sub("\\..*$", "", R.version$minor), sep = "."))
}
dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))

if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager", lib = lib,
                   repos = "https://mirrors.ustc.edu.cn/CRAN/")
}
if (!requireNamespace("BiocManager", quietly = TRUE)) {
  stop("BiocManager installation failed")
}

bioc <- if (getRversion() >= "4.3") "3.18" else as.character(BiocManager::version())
message("Using Bioconductor ", bioc, " and library ", lib)

# Core oracle packages.  fgsea is handled separately because its 1.28.0
# Makevars forces C++11 while the current BH headers require C++14/17.
BiocManager::install(
  c("limma", "fgsea", "sva", "edgeR", "clusterProfiler", "ANCOMBC", "ALDEx2",
    "DESeq2", "GSVA"),
  lib = lib, version = bioc, ask = FALSE, update = FALSE,
  Ncpus = getOption("Ncpus", 2L)
)

for (pkg in c("metafor", "Kendall")) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, lib = lib,
                     repos = "https://mirrors.ustc.edu.cn/CRAN/")
  }
}

# fgsea 1.28.0's src/Makevars has no CXX_STD; R 4.3 defaults to C++11, which is
# too old for BH >= 1.90.  Patch the source to compile as C++17.
if (!requireNamespace("fgsea", quietly = TRUE)) {
  url <- paste0("https://bioconductor.org/packages/", bioc,
                "/bioc/src/contrib/fgsea_1.28.0.tar.gz")
  tarball <- tempfile(fileext = ".tar.gz")
  download.file(url, tarball, quiet = TRUE)
  src <- file.path(tempdir(), "fgsea-src")
  unlink(src, recursive = TRUE)
  dir.create(src, recursive = TRUE)
  utils::untar(tarball, exdir = src)
  pkg <- file.path(src, "fgsea")
  writeLines("CXX_STD = CXX17", file.path(pkg, "src", "Makevars"))
  status <- system2(file.path(R.home("bin"), "R"),
                    c("CMD", "INSTALL", paste0("--library=", lib), pkg))
  if (!identical(status, 0L)) {
    warning("fgsea C++17 rebuild failed; see output above")
  }
}

required <- c("limma", "fgsea", "metafor", "GSVA", "BiocManager")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  stop("Required R oracle packages still missing: ", paste(missing, collapse = ", "))
}

optional <- c("sva", "Kendall", "edgeR", "clusterProfiler", "ANCOMBC", "ALDEx2", "DESeq2")
missing_optional <- optional[
  !vapply(optional, requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing_optional)) {
  message("Optional R packages not installed (system libraries missing?): ",
          paste(missing_optional, collapse = ", "))
}
message("All required R oracle packages are installed.")
