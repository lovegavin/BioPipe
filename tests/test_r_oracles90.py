import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.glmm_logistic import GlmmLogisticStep
from src.task.step.steps.manova import ManovaStep
from src.task.step.steps.knn import _knn_predict
from src.task.step.steps.qda import _fit, _log_posterior

R_CODE = r"""
suppressMessages(library(MASS))
suppressMessages(library(class))
suppressMessages(library(lme4))
g <- factor(rep(c("a", "b", "c"), each = 5))
y1 <- c(2.1, 1.8, 2.4, 2.0, 1.9, 4.2, 4.0, 4.6, 3.8, 4.4,
        6.1, 5.8, 6.4, 6.0, 5.9)
y2 <- c(1.0, 1.4, 0.9, 1.2, 1.1, 2.2, 2.5, 2.0, 2.3, 2.1,
        3.3, 3.6, 3.1, 3.4, 3.2)
fit <- manova(cbind(y1, y2) ~ g)
s <- summary(fit, test = "Pillai")$stats[1, ]
cat("manova", sprintf("%.15g", s), "\n")
train <- data.frame(
  x1 = c(0.2, 0.5, 0.3, 0.8, 0.1, 2.0, 2.4, 2.2, 2.6, 2.1,
         4.1, 4.5, 4.3, 4.7, 4.2),
  x2 = c(0.4, 0.1, 0.6, 0.2, 0.5, 1.1, 1.4, 1.2, 1.5, 1.3,
         3.1, 3.5, 3.3, 3.6, 3.2),
  y = factor(rep(c("p", "q", "r"), each = 5))
)
qd <- qda(y ~ x1 + x2, data = train)
test <- data.frame(x1 = c(0.4, 2.2, 4.4, 1.0),
                   x2 = c(0.3, 1.3, 3.4, 2.5))
pr <- predict(qd, test)
cat("qda", paste(as.character(pr$class), collapse = ","), "\n")
ktrain <- data.frame(x1 = c(0.0, 1.0, 0.2, 3.0, 3.2, 2.8),
                     x2 = c(0.0, 0.1, 0.3, 3.0, 3.2, 2.9))
ktest <- data.frame(x1 = c(0.1, 3.1, 0.5, 2.9),
                    x2 = c(0.2, 3.0, 1.5, 3.3))
kp <- knn(ktrain, ktest, factor(c("a", "a", "a", "b", "b", "b")), k = 3)
cat("knn", paste(as.character(kp), collapse = ","), "\n")
d <- read.csv(commandArgs(TRUE)[1])
gl <- glmer(y ~ x + (1 | g), data = d, family = binomial, nAGQ = 1)
values <- c(fixef(gl), sqrt(as.numeric(VarCorr(gl)$g[1, 1])),
            as.numeric(logLik(gl)))
cat("glmm", sprintf("%.15g", values), "\n")
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=float), dims=dims, labels=labels,
                info={"missing_code": np.nan})
    form.validate()
    return form


def _run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


@pytest.mark.skipif(
    subprocess.run(["bash", "-lc", "command -v Rscript"],
                   capture_output=True).returncode != 0,
    reason="Rscript is unavailable",
)
def test_quantitative_oracles(tmp_path):
    base = tmp_path
    rng = np.random.default_rng(11)
    ng, ni = 20, 8
    g = np.repeat(np.arange(ng), ni)
    x = rng.normal(size=ng * ni)
    u = rng.normal(scale=0.7, size=ng)[g]
    y = rng.binomial(1, 1 / (1 + np.exp(-(0.5 + x + u))))
    data_path = base / "glmm.csv"
    with data_path.open("w", encoding="utf-8") as handle:
        handle.write("y,x,g\n")
        for row in zip(y, x, g):
            handle.write(f"{int(row[0])},{row[1]:.17g},{int(row[2])}\n")

    result = subprocess.run(
        ["Rscript", "-e", R_CODE, str(data_path)],
        capture_output=True, text=True, check=True,
    )
    lines = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) == 2:
            lines[parts[0]] = parts[1]

    # MANOVA
    samples = [f"s{i}" for i in range(15)]
    y1 = [2.1, 1.8, 2.4, 2.0, 1.9, 4.2, 4.0, 4.6, 3.8, 4.4,
          6.1, 5.8, 6.4, 6.0, 5.9]
    y2 = [1.0, 1.4, 0.9, 1.2, 1.1, 2.2, 2.5, 2.0, 2.3, 2.1,
          3.3, 3.6, 3.1, 3.4, 3.2]
    values = _form(np.column_stack([y1, y2]), ["sample", "response"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "response": {"y1": 0, "y2": 1}})
    meta = _form(np.array([0] * 5 + [1] * 5 + [2] * 5, dtype=float)[:, None],
                 ["sample", "feature"],
                 {"sample": {s: i for i, s in enumerate(samples)},
                  "feature": {"group": 0}})
    out, _ = _run(ManovaStep(), (values, meta),
                  {"group_label": "group", "output": "output"})
    ours = np.asarray(out.data, dtype=np.float64).ravel()[1:]
    r_values = [float(v) for v in lines["manova"].split()][1:]
    assert ours[0] == pytest.approx(r_values[0], rel=5e-7)
    assert ours[1] == pytest.approx(r_values[1], rel=1e-5)
    assert ours[2] == pytest.approx(r_values[2])
    assert ours[3] == pytest.approx(r_values[3])
    assert ours[4] == pytest.approx(r_values[4], rel=1e-5)

    # QDA
    train_x = np.array([
        [0.2, 0.4], [0.5, 0.1], [0.3, 0.6], [0.8, 0.2], [0.1, 0.5],
        [2.0, 1.1], [2.4, 1.4], [2.2, 1.2], [2.6, 1.5], [2.1, 1.3],
        [4.1, 3.1], [4.5, 3.5], [4.3, 3.3], [4.7, 3.6], [4.2, 3.2],
    ])
    train_y = ["p"] * 5 + ["q"] * 5 + ["r"] * 5
    classes, means, covs, priors = _fit(train_x, train_y, 0.0)
    test_x = np.array([[0.4, 0.3], [2.2, 1.3], [4.4, 3.4], [1.0, 2.5]])
    predicted = [classes[i] for i in
                 _log_posterior(test_x, means, covs, priors).argmax(axis=1)]
    assert ",".join(predicted) == lines["qda"]

    # KNN
    ktrain = np.array([[0.0, 0.0], [1.0, 0.1], [0.2, 0.3],
                       [3.0, 3.0], [3.2, 3.2], [2.8, 2.9]])
    ktest = np.array([[0.1, 0.2], [3.1, 3.0], [0.5, 1.5], [2.9, 3.3]])
    kpred = _knn_predict(ktrain, np.array(["a", "a", "a", "b", "b", "b"]),
                         ktest, 3, "uniform")
    assert ",".join(kpred) == lines["knn"]

    # GLMM on the exact CSV rows
    rows = [line.split(",") for line in
            data_path.read_text(encoding="utf-8").strip().splitlines()[1:]]
    y_arr = np.array([float(r[0]) for r in rows])
    x_arr = np.array([float(r[1]) for r in rows])
    g_arr = np.array([float(r[2]) for r in rows])
    names = [f"o{i}" for i in range(len(rows))]
    table = _form(np.column_stack([y_arr, x_arr]), ["sample", "feature"],
                  {"sample": {n: i for i, n in enumerate(names)},
                   "feature": {"y": 0, "x": 1}})
    groups = _form(g_arr[:, None], ["sample", "feature"],
                   {"sample": {n: i for i, n in enumerate(names)},
                    "feature": {"grp": 0}})
    _, export = _run(GlmmLogisticStep(), (table, groups),
                     {"target_label": "y", "predictor_label": "x",
                      "group_label": "grp", "output": "output"})
    r_glmm = [float(v) for v in lines["glmm"].split()]
    assert export["coef"]["(Intercept)"] == pytest.approx(r_glmm[0], abs=1e-4)
    assert export["coef"]["x"] == pytest.approx(r_glmm[1], abs=1e-4)
    assert export["sigma"] == pytest.approx(r_glmm[2], abs=1e-4)
    assert export["loglik"] == pytest.approx(r_glmm[3], abs=1e-4)
