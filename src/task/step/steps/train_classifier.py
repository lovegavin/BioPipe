# src/task/step/steps/train_classifier.py
"""Supervised classification with feature importance.

Trains a classifier on a feature matrix and a categorical label, then
reports test-set metrics and cross-validation scores. The output is a
per-feature importance table suitable for ranking or plotting.

Inputs
------
    features : 2D Form [sample, feature]
    labels   : 2D Form [sample, label_dim]
               ``label_dim`` must contain ``target_label``.

Output
------
    data   2D float32 [feature, statistic]
    dims   [feature_dim, "statistic"]
    statistic = [importance, signed_score]

``importance`` is ``|coef|`` for linear models and
``feature_importances_`` for tree ensembles. ``signed_score`` is the
raw coefficient (positive = larger feature values push toward the
last class in ``classes``); it is 0 for tree ensembles.

Params:
    sample_dim    : observation axis (default "sample")
    feature_dim   : feature axis (default "feature")
    label_dim     : label axis on the label form (default "label")
    target_label  : column on label_dim to classify (required)
    method        : "logistic" | "rf" | "svm" | "gb" (default logistic)
    test_size     : held-out fraction (default 0.25)
    cv_folds      : K-fold cross-validation (default 5)
    random_state  : seed for the split, CV and model (default 0)
    class_weight  : "balanced" or None (default None)
    scale         : z-score features inside the pipeline (default True)
    output        : context key (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


_METHODS = ("logistic", "rf", "svm", "gb")
_STATS = ("importance", "signed_score")


class TrainClassifierStep(Step):
    """Train a classifier and report per-feature importance."""

    name = "train_classifier"
    category = "analysis"
    icon = "Brain"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "label_dim": {"type": "string", "default": "label"},
            "target_label": {"type": "string"},
            "method": {
                "type": "string",
                "enum": list(_METHODS),
                "default": "logistic",
            },
            "test_size": {
                "type": "number", "minimum": 0.05, "maximum": 0.5,
                "default": 0.25,
            },
            "cv_folds": {"type": "integer", "minimum": 2, "default": 5},
            "random_state": {"type": "integer", "default": 0},
            "class_weight": {
                "type": ["string", "null"],
                "enum": ["balanced", None],
                "default": None,
            },
            "scale": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }
    input_contracts = [
        port(ndim=2,
             dims=[param("sample_dim", "sample"),
                   param("feature_dim", "feature")]),
        port(ndim=2,
             dims=[param("sample_dim", "sample"),
                   param("label_dim", "label")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True,
        "info_open": True, "axis_info_open": True,
    }}

    def run(self, ctx: Context, inputs) -> None:
        features, labels_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        target_label = ctx.step_params["target_label"]
        method = ctx.step_params.get("method", "logistic")
        test_size = float(ctx.step_params.get("test_size", 0.25))
        cv_folds = int(ctx.step_params.get("cv_folds", 5))
        random_state = int(ctx.step_params.get("random_state", 0))
        class_weight = ctx.step_params.get("class_weight")
        scale = bool(ctx.step_params.get("scale", True))
        out_name = ctx.step_params.get("output", self.name)

        try:
            from sklearn.ensemble import (
                GradientBoostingClassifier, RandomForestClassifier,
            )
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import (
                accuracy_score, confusion_matrix, f1_score,
                precision_score, recall_score, roc_auc_score,
            )
            from sklearn.model_selection import (
                StratifiedKFold, cross_val_score, train_test_split,
            )
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.svm import SVC
        except ImportError as exc:
            raise StepError(
                "train_classifier: scikit-learn is required."
            ) from exc

        if method not in _METHODS:
            raise StepError(
                f"train_classifier: method must be one of "
                f"{list(_METHODS)}, got {method!r}"
            )
        if not (0.0 < test_size < 1.0):
            raise StepError(
                f"train_classifier: test_size must be in (0, 1), "
                f"got {test_size}"
            )
        if cv_folds < 2:
            raise StepError(
                f"train_classifier: cv_folds must be >= 2, "
                f"got {cv_folds}"
            )

        for label, form in (("features", features), ("labels", labels_form)):
            if form.data.ndim != 2:
                raise StepError(
                    f"train_classifier: {label} must be 2D, "
                    f"got ndim={form.data.ndim}"
                )
            if sample_dim not in form.dims:
                raise StepError(
                    f"train_classifier: sample_dim '{sample_dim}' "
                    f"not in {label} dims {form.dims}"
                )

        if features.dims[0] != sample_dim:
            raise StepError(
                f"train_classifier: features must have sample_dim "
                f"as the first axis, got {features.dims}"
            )
        if labels_form.dims[0] != sample_dim:
            raise StepError(
                f"train_classifier: labels must have sample_dim as "
                f"the first axis, got {labels_form.dims}"
            )
        if feature_dim not in features.dims:
            raise StepError(
                f"train_classifier: feature_dim '{feature_dim}' not "
                f"in features dims {features.dims}"
            )
        if label_dim not in labels_form.dims:
            raise StepError(
                f"train_classifier: label_dim '{label_dim}' not in "
                f"labels dims {labels_form.dims}"
            )

        label_cols = labels_form.labels[label_dim]
        if target_label not in label_cols:
            raise StepError(
                f"train_classifier: target_label '{target_label}' "
                f"not in '{label_dim}'. Available: "
                f"{sorted(label_cols)}"
            )

        feature_labels = features.labels[feature_dim]
        sample_labels = features.labels[sample_dim]

        # Restrict to sample labels shared with the label form.
        label_sample_labels = labels_form.labels[sample_dim]
        common = [s for s in sample_labels if s in label_sample_labels]
        if len(common) < 4:
            raise StepError(
                f"train_classifier: only {len(common)} samples shared "
                f"between features and labels"
            )

        feat_positions = [sample_labels[s] for s in common]
        label_positions = [label_sample_labels[s] for s in common]
        # Contract enforces features.dims == [sample_dim, feature_dim],
        # so data is already [n_samples, n_features].
        X = np.take(features.data, feat_positions, axis=0)
        X = X.astype(np.float64)

        label_axis = labels_form.dims.index(label_dim)
        y_raw = np.take(labels_form.data, label_positions, axis=0)
        y_raw = np.take(y_raw, label_cols[target_label], axis=label_axis)
        y_raw = np.asarray(y_raw).reshape(len(common))

        label_encoders = labels_form.info.get("encoders", {}).get(label_dim, {})
        target_encoder = label_encoders.get(target_label)
        if target_encoder is not None:
            y_labels = [
                target_encoder.inverse.get(int(round(float(v))), str(int(v)))
                if np.isfinite(v) else None
                for v in y_raw
            ]
        else:
            y_labels = [
                str(int(round(float(v)))) if np.isfinite(v) else None
                for v in y_raw
            ]

        valid_mask = np.array([lbl is not None for lbl in y_labels])
        if valid_mask.sum() < 4:
            raise StepError(
                f"train_classifier: only {int(valid_mask.sum())} "
                f"samples have a non-missing label"
            )
        X = X[valid_mask]
        y_labels = [lbl for lbl, keep in zip(y_labels, valid_mask) if keep]

        classes = sorted(set(y_labels))
        n_classes = len(classes)
        if n_classes < 2:
            raise StepError(
                f"train_classifier: need at least 2 classes in "
                f"'{target_label}', got {classes}"
            )
        y = np.array([classes.index(lbl) for lbl in y_labels])

        # Fill missing with column mean.
        col_mean = np.nanmean(X, axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
        X = np.where(np.isfinite(X), X, col_mean)

        n_samples, n_features = X.shape
        n_test = max(2, int(round(n_samples * test_size)))
        n_train = n_samples - n_test
        if n_train < n_classes or n_test < n_classes:
            raise StepError(
                f"train_classifier: not enough samples per class "
                f"(n_train={n_train}, n_test={n_test}, "
                f"n_classes={n_classes})"
            )
        if cv_folds > n_train:
            raise StepError(
                f"train_classifier: cv_folds={cv_folds} exceeds "
                f"training set size {n_train}"
            )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y,
            random_state=random_state,
        )

        def build_model():
            if method == "logistic":
                return LogisticRegression(
                    max_iter=1000, class_weight=class_weight,
                    random_state=random_state,
                )
            if method == "rf":
                return RandomForestClassifier(
                    n_estimators=100, class_weight=class_weight,
                    random_state=random_state,
                )
            if method == "svm":
                return SVC(
                    kernel="linear", probability=True,
                    class_weight=class_weight,
                    random_state=random_state,
                )
            return GradientBoostingClassifier(
                n_estimators=100, random_state=random_state,
            )

        def build_pipeline():
            steps = []
            if scale:
                steps.append(("scaler", StandardScaler()))
            steps.append(("model", build_model()))
            return Pipeline(steps)

        pipe = build_pipeline()
        pipe.fit(X_train, y_train)

        y_pred = pipe.predict(X_test)
        try:
            proba = pipe.predict_proba(X_test)
        except AttributeError:
            proba = None

        acc = float(accuracy_score(y_test, y_pred))
        cm = confusion_matrix(y_test, y_pred).tolist()
        try:
            precision = float(precision_score(
                y_test, y_pred, average="macro", zero_division=0,
            ))
            recall = float(recall_score(
                y_test, y_pred, average="macro", zero_division=0,
            ))
            f1 = float(f1_score(
                y_test, y_pred, average="macro", zero_division=0,
            ))
        except Exception:
            precision = recall = f1 = None

        auc_value = None
        if proba is not None:
            try:
                if n_classes == 2:
                    auc_value = float(roc_auc_score(y_test, proba[:, 1]))
                else:
                    auc_value = float(roc_auc_score(
                        y_test, proba, multi_class="ovr",
                        average="macro",
                    ))
            except Exception:
                auc_value = None

        cv = StratifiedKFold(
            n_splits=cv_folds, shuffle=True,
            random_state=random_state,
        )
        cv_scores = cross_val_score(
            build_pipeline(), X_train, y_train, cv=cv,
            scoring="accuracy",
        )
        cv_scores = [float(s) for s in cv_scores]

        final_model = pipe.named_steps["model"]
        signed = np.zeros(n_features, dtype=np.float64)
        importance = np.zeros(n_features, dtype=np.float64)
        if hasattr(final_model, "coef_"):
            coef = np.asarray(final_model.coef_)
            if coef.ndim == 1:
                signed = coef
            elif coef.shape[0] == 1:
                signed = coef[0]
            else:
                signed = coef.mean(axis=0)
            importance = np.abs(signed)
        elif hasattr(final_model, "feature_importances_"):
            importance = np.asarray(
                final_model.feature_importances_, dtype=np.float64,
            )
            signed = np.zeros_like(importance)
        else:
            raise StepError(
                f"train_classifier: model {method} has neither "
                f"coef_ nor feature_importances_"
            )

        stat_matrix = np.column_stack([
            importance.astype(np.float32),
            signed.astype(np.float32),
        ])

        out = Form(
            data=stat_matrix,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: dict(features.labels[feature_dim]),
                "statistic": {n: i for i, n in enumerate(_STATS)},
            },
            info={"missing_code": np.nan},
        )
        ctx[out_name] = out

        top_idx = np.argsort(-importance)[:20]
        inv = {v: k for k, v in feature_labels.items()}
        top_features = [
            {
                "feature": inv[int(i)],
                "importance": float(importance[i]),
                "signed_score": float(signed[i]),
            }
            for i in top_idx
        ]

        self._export_data = {
            "method": method,
            "target_label": target_label,
            "classes": classes,
            "n_samples": int(n_samples),
            "n_features": int(n_features),
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
            "test_accuracy": acc,
            "test_precision_macro": precision,
            "test_recall_macro": recall,
            "test_f1_macro": f1,
            "test_auc": auc_value,
            "confusion_matrix": cm,
            "cv_folds": cv_folds,
            "cv_scores": cv_scores,
            "cv_mean_accuracy": float(np.mean(cv_scores)),
            "cv_std_accuracy": float(np.std(cv_scores)),
            "top_features": top_features,
            "class_weight": class_weight,
            "scale": scale,
            "test_size": test_size,
            "random_state": random_state,
        }

        print(
            f"[train_classifier] {method}: {n_samples} samples, "
            f"{n_features} features, {n_classes} classes, "
            f"test_accuracy={acc:.3f}, cv_mean={np.mean(cv_scores):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
