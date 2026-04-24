from datetime import UTC, datetime
from uuid import uuid4


def make_task_payload(**overrides):
    payload = {
        "project_id": "ashrise",
        "title": "Ship dashboard tasks foundation",
        "status": "backlog",
        "priority": 2,
        "position": 0,
        "tags": ["dashboard", "tasks"],
    }
    payload.update(overrides)
    return payload


def test_tasks_migration_applied(db_conn):
    row = db_conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'tasks'
        """
    ).fetchone()

    assert row is not None
    assert row["table_name"] == "tasks"


def test_tasks_crud_happy_path(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    candidate_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, 'ashrise', 'Turn dashboard tasking into a real workspace', 'cli', 'triaged', %s)
        """,
        (idea_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (id, slug, name, category, hypothesis, status)
        VALUES (%s, %s, 'Task Candidate', 'learning', 'Keep task links honest', 'investigating')
        """,
        (candidate_id, f"task-candidate-{uuid4().hex[:8]}"),
    )

    created = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(
            idea_id=str(idea_id),
            candidate_id=str(candidate_id),
            title="  Define workspace + board  ",
        ),
    )
    assert created.status_code == 201
    task = created.json()
    assert task["title"] == "Define workspace + board"
    assert task["idea_id"] == str(idea_id)
    assert task["candidate_id"] == str(candidate_id)
    assert task["closed_at"] is None

    listing = app_client.get("/tasks", headers=auth_headers, params={"idea_id": str(idea_id)})
    assert listing.status_code == 200
    assert any(item["id"] == task["id"] for item in listing.json())

    done = app_client.patch(
        f"/tasks/{task['id']}",
        headers=auth_headers,
        json={
            "status": "done",
            "description": "  Validated end-to-end  ",
            "tags": [" dashboard ", " ux "],
        },
    )
    assert done.status_code == 200
    done_payload = done.json()
    assert done_payload["status"] == "done"
    assert done_payload["description"] == "Validated end-to-end"
    assert done_payload["tags"] == ["dashboard", "ux"]
    assert done_payload["closed_at"] is not None

    done_again = app_client.patch(
        f"/tasks/{task['id']}",
        headers=auth_headers,
        json={"title": "Define workspace + board v2"},
    )
    assert done_again.status_code == 200
    assert done_again.json()["closed_at"] == done_payload["closed_at"]

    reopened = app_client.patch(
        f"/tasks/{task['id']}",
        headers=auth_headers,
        json={"status": "progress"},
    )
    assert reopened.status_code == 200
    reopened_payload = reopened.json()
    assert reopened_payload["status"] == "progress"
    assert reopened_payload["closed_at"] is None

    detail = app_client.get(f"/tasks/{task['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == task["id"]

    deleted = app_client.delete(f"/tasks/{task['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = app_client.get(f"/tasks/{task['id']}", headers=auth_headers)
    assert missing.status_code == 404


def test_tasks_validation_errors(app_client, auth_headers):
    empty_title = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(title="   "),
    )
    assert empty_title.status_code == 422

    no_owner = app_client.post(
        "/tasks",
        headers=auth_headers,
        json={
            "title": "No owner task",
            "status": "backlog",
        },
    )
    assert no_owner.status_code == 422

    invalid_status = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(status="invalid"),
    )
    assert invalid_status.status_code == 422


def test_tasks_detail_not_found(app_client, auth_headers):
    missing_id = uuid4()
    response = app_client.get(f"/tasks/{missing_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Task '{missing_id}' not found"}


def test_dashboard_ideas_workspace_happy_path(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    sibling_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, tags, status, created_at)
        VALUES (%s, 'ashrise', 'Build an interactive ideas workspace for dashboard', 'cli', %s, 'triaged', %s)
        """,
        (idea_id, ["dashboard", "phase-2"], now),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, tags, status, created_at)
        VALUES (%s, 'ashrise', 'A sibling idea sharing the dashboard tag', 'telegram', %s, 'new', %s)
        """,
        (sibling_id, ["dashboard"], now),
    )
    db_conn.execute(
        """
        INSERT INTO tasks (idea_id, project_id, title, status, priority, position, tags)
        VALUES (%s, 'ashrise', 'Create the first task', 'ready', 3, 1, %s)
        """,
        (idea_id, ["dashboard"]),
    )

    response = app_client.get(f"/dashboard/ideas/{idea_id}/workspace", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["idea"]["id"] == str(idea_id)
    assert payload["idea"]["task_counts"]["total"] == 1
    assert payload["tasks"][0]["status"] == "ready"
    assert payload["sibling_ideas_in_same_tag"][0]["id"] == str(sibling_id)
    assert payload["suggested_next"] == []


def test_dashboard_ideas_workspace_not_found(app_client, auth_headers):
    missing_id = uuid4()
    response = app_client.get(f"/dashboard/ideas/{missing_id}/workspace", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Idea {missing_id} not found"}


def test_dashboard_tasks_board_empty(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM tasks")

    response = app_client.get("/dashboard/tasks/board", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "backlog": [],
        "ready": [],
        "progress": [],
        "blocked": [],
        "done": [],
    }


def test_dashboard_ideas_overview_task_counts_zero_when_no_tasks(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, 'ashrise', 'Idea without any tasks yet', 'cli', 'new', %s)
        """,
        (idea_id, now),
    )

    response = app_client.get("/dashboard/ideas/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    idea = next(item for item in payload["ideas"] if item["id"] == str(idea_id))
    assert idea["task_counts"] == {
        "total": 0,
        "backlog": 0,
        "ready": 0,
        "progress": 0,
        "blocked": 0,
        "done": 0,
    }


def test_tasks_positions_normalize_and_ordering_stays_consistent(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, 'ashrise', 'Normalize positions for board ordering', 'cli', 'triaged', %s)
        """,
        (idea_id, now),
    )

    first = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(idea_id=str(idea_id), title="First task", position=0),
    )
    second = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(idea_id=str(idea_id), title="Second task", position=0),
    )
    third = app_client.post(
        "/tasks",
        headers=auth_headers,
        json={
            key: value
            for key, value in make_task_payload(idea_id=str(idea_id), title="Third task").items()
            if key != "position"
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201

    listing = app_client.get("/tasks", headers=auth_headers, params={"idea_id": str(idea_id)})
    assert listing.status_code == 200
    payload = listing.json()
    assert [item["title"] for item in payload[:3]] == ["Second task", "First task", "Third task"]
    assert [item["position"] for item in payload[:3]] == [0, 1, 2]

    moved = app_client.patch(
        f"/tasks/{third.json()['id']}",
        headers=auth_headers,
        json={"position": 0},
    )
    assert moved.status_code == 200

    refreshed = app_client.get("/tasks", headers=auth_headers, params={"idea_id": str(idea_id), "status": "backlog"})
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert [item["title"] for item in refreshed_payload] == ["Third task", "Second task", "First task"]
    assert [item["position"] for item in refreshed_payload] == [0, 1, 2]


def test_dashboard_board_and_counts_reflect_status_and_position_changes(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    other_idea_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, 'ashrise', 'Board reflection idea', 'cli', 'triaged', %s)
        """,
        (idea_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, 'ashrise', 'Unrelated board idea', 'cli', 'triaged', %s)
        """,
        (other_idea_id, now),
    )

    first = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(idea_id=str(idea_id), title="Board backlog A", position=0),
    )
    second = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(idea_id=str(idea_id), title="Board backlog B", position=1),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    unrelated = app_client.post(
        "/tasks",
        headers=auth_headers,
        json=make_task_payload(idea_id=str(other_idea_id), title="Other idea backlog", position=0),
    )
    assert unrelated.status_code == 201

    moved = app_client.patch(
        f"/tasks/{second.json()['id']}",
        headers=auth_headers,
        json={"status": "ready", "position": 0},
    )
    assert moved.status_code == 200

    board = app_client.get("/dashboard/tasks/board", headers=auth_headers, params={"idea_id": str(idea_id)})
    assert board.status_code == 200
    board_payload = board.json()
    assert [item["title"] for item in board_payload["backlog"]] == ["Board backlog A"]
    assert [item["title"] for item in board_payload["ready"]] == ["Board backlog B"]
    assert board_payload["ready"][0]["position"] == 0
    assert all(item["idea_id"] == str(idea_id) for column in board_payload.values() for item in column)

    workspace = app_client.get(f"/dashboard/ideas/{idea_id}/workspace", headers=auth_headers)
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    assert workspace_payload["idea"]["task_counts"] == {
        "total": 2,
        "backlog": 1,
        "ready": 1,
        "progress": 0,
        "blocked": 0,
        "done": 0,
    }

    overview = app_client.get("/dashboard/ideas/overview", headers=auth_headers)
    assert overview.status_code == 200
    overview_payload = overview.json()
    idea = next(item for item in overview_payload["ideas"] if item["id"] == str(idea_id))
    assert idea["task_counts"]["backlog"] == 1
    assert idea["task_counts"]["ready"] == 1

    deleted = app_client.delete(f"/tasks/{first.json()['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    board_after_delete = app_client.get("/dashboard/tasks/board", headers=auth_headers, params={"idea_id": str(idea_id)})
    assert board_after_delete.status_code == 200
    assert board_after_delete.json()["backlog"] == []
