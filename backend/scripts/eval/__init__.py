"""Offline accuracy harness for the detection and rule pipeline.

The harness exists so accuracy claims are measured, not assumed:

* ground truth and predictions are JSON Lines (see :mod:`scripts.eval.schema`);
* :mod:`scripts.eval.metrics` scores boxes (mAP) and events (P/R/F1);
* :mod:`scripts.eval.datasets` converts public datasets into GT records;
* :mod:`scripts.eval.run_eval` is the CLI that ties it together.
"""
