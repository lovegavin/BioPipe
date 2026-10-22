"""Shared logic for single-model machine learning operators.

Every concrete operator subclasses ``_ClassificationBase`` or
``_RegressionBase`` and provides only:

- ``name``, ``title``
- ``extra_properties`` (model-specific schema fields)
- ``_build_model(params, random_state)`` returning an sklearn estimator

Files starting with ``_`` are skipped by the operator scanner, so
this module is not registered.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


_BASE_PROPERTIES = {
    "sample_dim": {"type": "string", "default": "sample"},
    "feature_dim": {"type": "string", "default": "feature"},
    "label_dim": {"type": "string", "default": "label"},
    "target_label": {"type": "string"},
    "test_size": {
        "type": "number", "minimum": 0.05, "maximum": 0.5,
        "default": 0.25,
    },
    "cv_folds": {"type": "integer", "minimum": 2, "default": 5},
    "random_state": {"type": "integer", "default": 0},
    "scale": {"type": "boolean", "default": True},
    "output": {"type": "string"},
}


class _MLBase(Step):
    category = "analysis"
    icon = "Brain"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"

    _target_kind = None
    extra_properties = {}

    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"),
                            param("feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"),
                            param("label_dim", "label")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2, "numeric": True,
            "info_open": True, "axis_info_open": True,
        },
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        props = dict(_BASE_PROPERTIES)
        if cls._target_kind == "classification":
            props["valid_labels"] = {
                "type": "array", "items": {"type": "string"},
            }
        props.update(cls.extra_properties)
        cls.parameters_schema = {
            "type": "object",
            "properties": props,
            "required": ["target_label"],
            "additionalProperties": False,
        }

    def _build_model(self, params, random_state):
        raise NotImplementedError

    def run(self, ctx: Context, inputs) -> None:
        features, labels_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        target_label = ctx.step_params["target_label"]
        test_size = float(ctx.step_params.get("test_size", 0.25))
        cv_folds = int(ctx.step_params.get("cv_folds", 5))
        random_state = int(ctx.step_params.get("random_state", 0))
        scale = bool(ctx.step_params.get("scale", True))
        out_name = ctx.step_params.get("output", self.name)
        valid_labels = ctx.step_params.get("valid_labels")

        if not (0.0 < test_size < 1.0):
            raise StepError(
                f"{self.name}: test_size must be in (0, 1), "
                f"got {test_size}"
            )
        if cv_folds < 2:
            raise StepError(
                f"{self.name}: cv_folds must be >= 2, got {cv_folds}"
            )
        if features.data.ndim != 2:
            raise StepError(f"{self.name}: features must be 2D")
        if labels_form.data.ndim != 2:
            raise StepError(f"{self.name}: labels must be 2D")
        if features.dims[0] != sample_dim:
            raise StepError(
                f"{self.name}: features must have {sample_dim!r} as "
                f"first axis, got {features.dims}"
            )
        if labels_form.dims[0] != sample_dim:
            raise StepError(
                f"{self.name}: labels must have {sample_dim!r} as "
                f"first axis, got {labels_form.dims}"
            )
        if feature_dim not in features.dims:
            raise StepError(
                f"{self.name}: feature_dim {feature_dim!r} not in "
                f"{features.dims}"
            )
        if label_dim not in labels_form.dims:
            raise StepError(
                f"{self.name}: label_dim {label_dim!r} not in "
                f"{labels_form.dims}"
            )
        label_cols = labels_form.labels[label_dim]
        if target_label not in label_cols:
            raise StepError(
                f"{self.name}: target_label {target_label!r} not in "
                f"{sorted(label_cols)}"
            )

        sample_labels = features.labels[sample_dim]
        label_sample_labels = labels_form.labels[sample_dim]
        common = [s for s in sample_labels if s in label_sample_labels]
        if len(common) < 8:
            raise StepError(
                f"{self.name}: only {len(common)} shared samples"
            )

        feat_positions = [sample_labels[s] for s in common]
        label_positions = [label_sample_labels[s] for s in common]
        X = features.data[feat_positions, :].astype(np.float64)

        label_axis = labels_form.dims.index(label_dim)
        y_raw = np.take(labels_form.data, label_positions, axis=0)
        y_raw = np.take(y_raw, label_cols[target_label], axis=label_axis)
        y_raw = np.asarray(y_raw).reshape(len(common))

        feature_labels = features.labels[feature_dim]
        n_features = X.shape[1]

        col_mean = np.nanmean(X, axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
        X = np.where(np.isfinite(X), X, col_mean)

        encoders = labels_form.info.get("encoders", {}).get(label_dim, {})
        target_enc = encoders.get(target_label)

        if self._target_kind == "classification":
            if target_enc is not None:
                y_labels = []
                for v in y_raw:
                    if not np.isfinite(v):
                        y_labels.append(None)
                        continue
                    lbl = target_enc.inverse.get(int(round(float(v))), None)
                    y_labels.append(lbl if isinstance(lbl, str) else None)
            else:
                y_labels = [
                    str(int(round(float(v)))) if np.isfinite(v) else None
                    for v in y_raw
                ]
            if valid_labels is not None:
                allowed = set(valid_labels)
                y_labels = [
                    lbl if lbl in allowed else None for lbl in y_labels
                ]
            valid_mask = np.array([lbl is not None for lbl in y_labels])
            if valid_mask.sum() < 8:
                raise StepError(
                    f"{self.name}: only {int(valid_mask.sum())} "
                    f"samples with a valid class"
                )
            X = X[valid_mask]
            y_labels = [lbl for lbl, k in zip(y_labels, valid_mask) if k]
            classes = sorted(set(y_labels))
            if len(classes) < 2:
                raise StepError(
                    f"{self.name}: need >= 2 classes, got {classes}"
                )
            y = np.array([classes.index(lbl) for lbl in y_labels])
        else:
            if target_enc is not None:
                # The column was encoded because at least one raw
                # value was non-numeric (for example a
                # ``data_type`` declaration row at the top of a
                # clinical table). Try to recover numeric values
                # from the encoder inverse; treat any inverse that
                # does not parse as a float as missing.
                recovered = []
                for v in y_raw:
                    if not np.isfinite(v):
                        recovered.append(np.nan)
                        continue
                    raw = target_enc.inverse.get(int(round(float(v))))
                    try:
                        recovered.append(float(raw))
                    except (TypeError, ValueError):
                        recovered.append(np.nan)
                y = np.asarray(recovered, dtype=np.float64)
            else:
                y = y_raw.astype(np.float64)
            valid_mask = np.isfinite(y)
            if valid_mask.sum() < 8:
                raise StepError(
                    f"{self.name}: only {int(valid_mask.sum())} "
                    f"numeric target values"
                )
            X = X[valid_mask]
            y = y[valid_mask]
            classes = None

        n_samples, n_features_actual = X.shape
        if n_features_actual != n_features:
            raise StepError(f"{self.name}: feature count changed")

        try:
            from sklearn.model_selection import (
                KFold, StratifiedKFold, cross_val_score,
                train_test_split,
            )
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError as exc:
            raise StepError(
                f"{self.name}: scikit-learn is required."
            ) from exc

        if self._target_kind == "classification":
            counts = np.bincount(y)
            n_classes = len(counts)
            if n_classes > 1 and counts.min() < 2:
                raise StepError(
                    f"{self.name}: every class needs >= 2 samples, "
                    f"got counts {counts.tolist()}"
                )
            split_kwargs = {"stratify": y}
        else:
            split_kwargs = {}

        try:
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y, test_size=test_size, random_state=random_state,
                **split_kwargs,
            )
        except ValueError as exc:
            raise StepError(
                f"{self.name}: train/test split failed: {exc}"
            ) from exc

        def build_pipeline():
            model = self._build_model(ctx.step_params, random_state)
            if scale:
                return Pipeline([("scaler", StandardScaler()),
                                 ("model", model)])
            return Pipeline([("model", model)])

        pipe = build_pipeline()
        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_te)

        if self._target_kind == "classification":
            from sklearn.metrics import (
                accuracy_score, confusion_matrix, f1_score,
                precision_score, recall_score, roc_auc_score,
            )
            acc = float(accuracy_score(y_te, y_pred))
            precision = float(precision_score(
                y_te, y_pred, average="macro", zero_division=0,
            ))
            recall = float(recall_score(
                y_te, y_pred, average="macro", zero_division=0,
            ))
            f1 = float(f1_score(
                y_te, y_pred, average="macro", zero_division=0,
            ))
            cm = confusion_matrix(y_te, y_pred).tolist()
            auc_value = None
            try:
                proba = pipe.predict_proba(X_te)
                if proba.shape[1] == 2:
                    auc_value = float(roc_auc_score(y_te, proba[:, 1]))
                else:
                    auc_value = float(roc_auc_score(
                        y_te, proba, multi_class="ovr",
                        average="macro",
                    ))
            except Exception:
                auc_value = None
            scoring = "accuracy"
            cv_splitter = StratifiedKFold(
                n_splits=cv_folds, shuffle=True,
                random_state=random_state,
            )
        else:
            from sklearn.metrics import (
                mean_absolute_error, mean_squared_error, r2_score,
            )
            rmse = float(np.sqrt(mean_squared_error(y_te, y_pred)))
            mae = float(mean_absolute_error(y_te, y_pred))
            r2 = float(r2_score(y_te, y_pred))
            scoring = "r2"
            cv_splitter = KFold(
                n_splits=cv_folds, shuffle=True,
                random_state=random_state,
            )

        try:
            cv_scores = cross_val_score(
                build_pipeline(), X_tr, y_tr, cv=cv_splitter,
                scoring=scoring,
            )
            cv_scores = [float(s) for s in cv_scores]
        except Exception:
            cv_scores = []

        final_model = pipe.named_steps["model"]
        importance = np.zeros(n_features, dtype=np.float64)
        signed = np.zeros(n_features, dtype=np.float64)
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
        else:
            raise StepError(
                f"{self.name}: model has neither coef_ nor "
                f"feature_importances_"
            )

        stat_matrix = np.column_stack([
            importance.astype(np.float32),
            signed.astype(np.float32),
        ])
        ctx[out_name] = Form(
            data=stat_matrix,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: dict(feature_labels),
                "statistic": {"importance": 0, "signed_score": 1},
            },
            info={"missing_code": np.nan},
        )

        inv = {v: k for k, v in feature_labels.items()}
        top_idx = np.argsort(-importance)[:20]
        top_features = [
            {
                "feature": inv[int(i)],
                "importance": float(importance[i]),
                "signed_score": float(signed[i]),
            }
            for i in top_idx
        ]

        export = {
            "name": self.name,
            "target_label": target_label,
            "n_samples": int(n_samples),
            "n_features": int(n_features),
            "n_train": int(X_tr.shape[0]),
            "n_test": int(X_te.shape[0]),
            "cv_folds": cv_folds,
            "cv_scores": cv_scores,
            "cv_mean": float(np.mean(cv_scores)) if cv_scores else None,
            "cv_std": float(np.std(cv_scores)) if cv_scores else None,
            "top_features": top_features,
            "scale": scale,
            "test_size": test_size,
            "random_state": random_state,
        }
        if self._target_kind == "classification":
            export.update({
                "classes": classes,
                "test_accuracy": acc,
                "test_precision_macro": precision,
                "test_recall_macro": recall,
                "test_f1_macro": f1,
                "test_auc": auc_value,
                "confusion_matrix": cm,
                "valid_labels": (
                    list(valid_labels) if valid_labels else None
                ),
            })
            print(
                f"[{self.name}] {n_samples} samples, "
                f"{n_features} features, {len(classes)} classes, "
                f"test_accuracy={acc:.3f}, "
                f"cv_mean={np.mean(cv_scores) if cv_scores else 0:.3f}"
            )
        else:
            export.update({
                "test_rmse": rmse,
                "test_mae": mae,
                "test_r2": r2,
            })
            print(
                f"[{self.name}] {n_samples} samples, "
                f"{n_features} features, test_rmse={rmse:.3f}, "
                f"test_r2={r2:.3f}, "
                f"cv_mean_r2={np.mean(cv_scores) if cv_scores else 0:.3f}"
            )
        self._export_data = export

    def export(self, ctx: Context) -> dict:
        return self._export_data


class _ClassificationBase(_MLBase):
    _target_kind = "classification"


class _RegressionBase(_MLBase):
    _target_kind = "regression"
