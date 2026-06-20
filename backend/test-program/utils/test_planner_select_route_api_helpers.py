import ast
from pathlib import Path
from typing import Any


def _load_main_helpers(names: set[str]) -> dict[str, Any]:
    main_py = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(main_py.read_text(encoding="utf-8"))
    selected_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {"Any": Any}
    exec(compile(module, str(main_py), "exec"), namespace)
    return namespace


def test_select_route_falls_back_to_route_intent_when_id_changed():
    helpers = _load_main_helpers(
        {
            "_route_terminal_bucket_from_dict",
            "_route_intent_key_from_dict",
            "_route_stable_intent_key_from_dict",
            "_select_route_in_plan",
        }
    )
    select_route = helpers["_select_route_in_plan"]
    stale_route = {
        "id": "route-1-old",
        "route_type": "cut",
        "target_ball_number": 1,
        "first_contact_ball_number": 1,
        "path_points": [[100, 100], [200, 120], [60, 420]],
        "metadata": {"route_class": "potting_route", "target_pocket_id": "bottom-left"},
    }
    current_route = {
        **stale_route,
        "id": "route-1-new",
        "path_points": [[104, 100], [203, 122], [58, 418]],
    }
    plan = {
        "best_route": {"id": "route-2-new"},
        "selected_route_id": "route-2-new",
        "routes": [
            {"id": "route-2-new", "route_type": "cut", "target_ball_number": 1},
            current_route,
        ],
    }

    updated = select_route(plan, "route-1-old", stale_route)

    assert updated["best_route"]["id"] == "route-1-new"
    assert updated["selected_route_id"] == "route-1-new"
