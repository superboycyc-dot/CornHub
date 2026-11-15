from argparse import Namespace
import json

import pytest

from satellite.batch import make_plan, run_batch
from test_contracts import inputs


def test_batch_uses_a_labels_and_preserves_common_sample(tmp_path):
    fields, sample, _, request = inputs(tmp_path)
    labels = tmp_path / "labels.csv"
    labels.write_text("field_id,year,label,label_raw,source_dataset_id\nbarc_0001_unit_only,2022,grain,Grain,unit_only\n")
    plan = make_plan(Namespace(fields=fields, sample=sample, labels=labels))
    assert plan == [request]
    labels.write_text(labels.read_text() + "barc_0001_unit_only,2022,grain,Grain,unit_only\n")
    with pytest.raises(ValueError, match="Duplicate"):
        make_plan(Namespace(fields=fields, sample=sample, labels=labels))


def test_batch_is_gated_on_real_smoke_success(tmp_path):
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps(dict(status="blocked", real_sample_computed=False, valid_obs_count=None)))
    args = Namespace(smoke_report=proof, reports=tmp_path / "reports")
    assert run_batch(args) == 2
    report = json.loads((args.reports / "batch_report.json").read_text())
    assert report["status"] == "blocked"
