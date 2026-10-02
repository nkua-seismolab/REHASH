"""SeisComP comment-to-SKHASH boundary tests."""

import csv
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_skhash_input import make_task

from rehash.config import SKHashConfig
from rehash.core.skhash_input import AMPLITUDE_FILE, write_inputs
from rehash.scclient import LOAD_INVENTORY, OUTPUT_GROUP, SUBSCRIPTIONS

datamodel = pytest.importorskip("seiscomp.datamodel")
fm_io = pytest.importorskip("rehash.scclient.fm_io")
listener = pytest.importorskip("rehash.scclient.listener")
sp_ratio_from_comments = fm_io.sp_ratio_from_comments


def make_pick(text, suffix="repol"):
    pick = datamodel.Pick.Create()
    comment = datamodel.Comment()
    comment.setId(f"{pick.publicID()}/comment/{suffix}")
    comment.setText(text)
    pick.add(comment)
    return pick


@pytest.mark.parametrize("value", [2.5, "2.5000"])
def test_json_ratio_reaches_skhash(tmp_path, value):
    pick = make_pick(json.dumps({"sp_ratio": value}))
    task = make_task(with_sp=False)
    task.observations[0].sp_ratio = sp_ratio_from_comments(pick)
    control = write_inputs(task, tmp_path, SKHashConfig())
    assert "$ampfile\n" in control.read_text()
    with (tmp_path / AMPLITUDE_FILE).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert float(rows[0]["sp_ratio"]) == 2.5


@pytest.mark.parametrize(
    "text",
    [
        "sp=2.5",
        "invalid",
        "[]",
        "null",
        "{}",
        '{"sp_ratio": null}',
        '{"sp_ratio": {"value": 2.5}}',
        '{"sp_ratio": true}',
        '{"sp_ratio": 0}',
        '{"sp_ratio": -1}',
        '{"sp_ratio": "nan"}',
        '{"sp_ratio": "inf"}',
        '{"sp_ratio": []}',
    ],
)
def test_invalid_or_legacy_ratio_rejected(text):
    assert sp_ratio_from_comments(make_pick(text)) is None


def test_unrelated_json_comment_ignored():
    pick = make_pick('{"sp_ratio": 2.5}', suffix="other")
    assert sp_ratio_from_comments(pick) is None


def test_fixed_topology_and_event_only_trigger():
    assert SUBSCRIPTIONS == ("EVENT", "LOCATION")
    assert OUTPUT_GROUP == "FOCMECH"
    assert LOAD_INVENTORY is True
    app = SimpleNamespace(pending_events={}, processed_events=set(), wait_time=300)
    for kind in (datamodel.Pick, datamodel.Origin, datamodel.FocalMechanism):
        listener.EventListenerApp.addObject(app, "", kind.Create())
    assert app.pending_events == {}
    event = datamodel.Event.Create()
    listener.EventListenerApp.addObject(app, "", event)
    first_seen = app.pending_events[event.publicID()][1]
    listener.EventListenerApp.addObject(app, "", event)
    assert len(app.pending_events) == 1
    assert app.pending_events[event.publicID()][1] == first_seen


def test_database_children_loaded():
    origin = datamodel.Origin.Create()
    pick = datamodel.Pick.Create()
    query = Mock()
    query.getPicks.return_value = iter([pick])
    app = SimpleNamespace(query=lambda: query)
    assert listener.EventListenerApp._load_origin(app, origin.publicID()) == origin
    query.loadArrivals.assert_called_once_with(origin)
    assert listener.EventListenerApp._load_picks(app, origin) == [pick]
    query.loadComments.assert_called_once_with(pick)
