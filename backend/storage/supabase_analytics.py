import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseAnalyticsError(RuntimeError):
    """Raised when Supabase analytics storage cannot complete a request."""


@dataclass(frozen=True)
class SupabaseAnalyticsConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseAnalyticsConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseAnalyticsRepository:
    def __init__(self, config: SupabaseAnalyticsConfig):
        self.config = config

    def upsert_recording(self, recording: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "game_id": str(recording["game_id"]),
            "game_type": str(recording.get("game_type") or ""),
            "start_time": recording.get("start_time"),
            "end_time": recording.get("end_time"),
            "duration_seconds": _float_or_none(recording.get("duration_seconds")),
            "player1_name": recording.get("player1_name"),
            "player2_name": recording.get("player2_name"),
            "winner": recording.get("winner"),
            "player1_score": int(recording.get("player1_score") or 0),
            "player2_score": int(recording.get("player2_score") or 0),
            "target_rounds": int(recording.get("target_rounds") or 0),
            "video_path": str(recording.get("video_path") or ""),
            "video_resolution": recording.get("video_resolution"),
            "video_fps": _int_or_none(recording.get("video_fps")),
            "file_size_mb": _float_or_none(recording.get("file_size_mb")),
        }
        rows = self._upsert("analytics_recordings", payload, "game_id")
        return rows[0] if rows else payload

    def upsert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "local_event_id": _int_or_none(event.get("local_event_id") or event.get("id")),
            "game_id": str(event["game_id"]),
            "event_time": float(event.get("timestamp") or event.get("event_time") or 0.0),
            "event_type": str(event.get("event_type") or event.get("event") or ""),
            "data": _json_value(event.get("data"), {}),
            "target_ball": _int_or_none(event.get("target_ball")),
            "potted_ball": _int_or_none(event.get("potted_ball")),
            "first_contact": _int_or_none(event.get("first_contact")),
        }
        if payload["local_event_id"] is not None:
            rows = self._upsert("analytics_events", payload, "local_event_id")
        else:
            rows = self._insert("analytics_events", payload)
        return rows[0] if rows else payload

    def upsert_shot_event(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "game_id": event.get("game_id"),
            "player_name": event.get("player_name"),
            "shot_index": int(event.get("shot_index") or 0),
            "created_at": event.get("created_at"),
            "mode": event.get("mode"),
            "target_ball": _int_or_none(event.get("target_ball")),
            "first_contact": _int_or_none(event.get("first_contact")),
            "potted_balls": _json_value(event.get("potted_balls"), []),
            "pocket_result": str(event.get("pocket_result") or "missed"),
            "cue_ball_potted": bool(event.get("cue_ball_potted")),
            "is_foul": bool(event.get("is_foul")),
            "foul_reason": event.get("foul_reason"),
            "impact_angle": _float_or_none(event.get("impact_angle")),
            "ideal_angle": _float_or_none(event.get("ideal_angle")),
            "thickness_result": str(event.get("thickness_result") or "unknown"),
            "distance_bucket": str(event.get("distance_bucket") or "unknown"),
            "difficulty_level": str(event.get("difficulty_level") or "unknown"),
            "success_prob": _float_or_none(event.get("success_prob")),
            "position_success_prob": _float_or_none(event.get("position_success_prob")),
            "planned_cue_landing": _json_value(event.get("planned_cue_landing"), None),
            "actual_cue_landing": _json_value(event.get("actual_cue_landing"), None),
            "cue_landing_error_px": _float_or_none(event.get("cue_landing_error_px")),
            "next_ball_quality": event.get("next_ball_quality"),
            "raw_event_json": _json_value(event.get("raw_event_json"), {}),
        }
        if payload["game_id"]:
            rows = self._upsert("analytics_shot_events", payload, "game_id,shot_index")
        else:
            rows = self._insert("analytics_shot_events", payload)
        return rows[0] if rows else payload

    def upsert_practice_stats(self, stats: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "game_id": str(stats["game_id"]),
            "practice_type": str(stats.get("practice_type") or ""),
            "pattern": stats.get("pattern"),
            "total_attempts": int(stats.get("total_attempts") or 0),
            "successful_attempts": int(stats.get("successful_attempts") or 0),
            "success_rate": _float_or_none(stats.get("success_rate")),
            "avg_shot_time": _float_or_none(stats.get("avg_shot_time")),
        }
        rows = self._upsert("analytics_practice_stats", payload, "game_id,practice_type,pattern")
        return rows[0] if rows else payload

    def delete_recording(self, game_id: str) -> None:
        query = parse.urlencode({"game_id": f"eq.{game_id}"})
        self._request_json(f"{self._table_url('analytics_recordings')}?{query}", method="DELETE")

    def get_recording(self, game_id: str) -> dict[str, Any] | None:
        query = parse.urlencode({"game_id": f"eq.{game_id}", "select": "*", "limit": "1"})
        rows = self._request_json(f"{self._table_url('analytics_recordings')}?{query}", method="GET")
        if not isinstance(rows, list) or not rows:
            return None
        return dict(rows[0])

    def get_recordings(
        self,
        game_type: str | None = None,
        game_types: list[str] | None = None,
        player: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        params: list[tuple[str, str]] = [
            ("select", "*"),
            ("order", "start_time.desc"),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ]
        if game_types:
            params.append(("game_type", f"in.({','.join(game_types)})"))
        elif game_type:
            params.append(("game_type", f"eq.{game_type}"))
        if start_date:
            params.append(("start_time", f"gte.{start_date}"))
        if end_date:
            params.append(("start_time", f"lte.{end_date}"))

        endpoint = f"{self._table_url('analytics_recordings')}?{parse.urlencode(params)}"
        headers = {"Prefer": "count=exact"}
        if player:
            params.append(("or", f"(player1_name.eq.{player},player2_name.eq.{player})"))
            endpoint = f"{self._table_url('analytics_recordings')}?{parse.urlencode(params)}"
        rows, total = self._request_json_with_count(endpoint, headers=headers)
        return [dict(row) for row in rows if isinstance(row, dict)], total

    def get_events(
        self,
        game_id: str,
        event_type: str | None = None,
        from_time: float | None = None,
        to_time: float | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "game_id": f"eq.{game_id}",
            "select": "*",
            "order": "event_time.asc",
        }
        if event_type:
            params["event_type"] = f"eq.{event_type}"
        if from_time is not None:
            params["event_time"] = f"gte.{from_time}"
        if to_time is not None:
            params["event_time"] = f"lte.{to_time}"
        rows = self._request_json(f"{self._table_url('analytics_events')}?{parse.urlencode(params)}", method="GET")
        events: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            events.append({
                "id": row.get("id"),
                "local_event_id": row.get("local_event_id"),
                "game_id": row.get("game_id"),
                "timestamp": row.get("event_time"),
                "event_type": row.get("event_type"),
                "data": row.get("data") or {},
                "target_ball": row.get("target_ball"),
                "potted_ball": row.get("potted_ball"),
                "first_contact": row.get("first_contact"),
            })
        return events

    def get_shot_events(
        self,
        player_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = [
            ("select", "*"),
            ("order", "created_at.desc"),
            ("limit", str(limit)),
        ]
        if start_date:
            params.append(("created_at", f"gte.{start_date}"))
        if end_date:
            params.append(("created_at", f"lte.{end_date}"))
        rows = self._request_json(f"{self._table_url('analytics_shot_events')}?{parse.urlencode(params)}", method="GET")
        events: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            if player_name:
                event_player = str(row.get("player_name") or "").strip()
                if event_player and event_player != player_name:
                    continue
            events.append(dict(row))
        return events

    def get_practice_stats(
        self,
        practice_type: str | None = None,
        pattern: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "select": "*,analytics_recordings(start_time,end_time)",
            "order": "created_at.desc",
        }
        if practice_type:
            params["practice_type"] = f"eq.{practice_type}"
        if pattern:
            params["pattern"] = f"eq.{pattern}"
        rows = self._request_json(f"{self._table_url('analytics_practice_stats')}?{parse.urlencode(params)}", method="GET")
        stats: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            recording = row.pop("analytics_recordings", {}) or {}
            item = dict(row)
            item["start_time"] = recording.get("start_time")
            item["end_time"] = recording.get("end_time")
            if start_date and str(item.get("start_time") or "") < start_date:
                continue
            if end_date and str(item.get("start_time") or "") > end_date:
                continue
            stats.append(item)
        return stats

    def get_player_analytics(self, player_name: str) -> dict[str, Any]:
        recordings, _ = self.get_recordings(limit=1000, offset=0)
        nine_ball = [
            item for item in recordings
            if item.get("game_type") == "nine_ball"
            and (item.get("player1_name") == player_name or item.get("player2_name") == player_name)
        ]
        total_games = len(nine_ball)
        total_wins = sum(1 for item in nine_ball if _winner_contains(item.get("winner"), player_name))
        recent_games = []
        for item in nine_ball[:5]:
            opponent = item.get("player2_name") if item.get("player1_name") == player_name else item.get("player1_name")
            is_win = _winner_contains(item.get("winner"), player_name)
            recent_games.append({
                "game_id": item.get("game_id"),
                "opponent": opponent,
                "result": "win" if is_win else "loss",
                "score": f"{int(item.get('player1_score') or 0)}-{int(item.get('player2_score') or 0)}",
                "date": item.get("start_time"),
            })
        practice = [
            item for item in recordings
            if item.get("game_type") in {"practice_single", "practice_pattern", "practice_accuracy"}
            and _practice_belongs_to_player(item, player_name)
        ]
        practice_durations = [float(item.get("duration_seconds") or 0) for item in practice]
        return {
            "name": player_name,
            "total_games": total_games,
            "total_wins": total_wins,
            "win_rate": round((total_wins / total_games) if total_games else 0.0, 2),
            "recent_games": recent_games,
            "total_practice_sessions": len(practice),
            "total_practice_seconds": round(sum(practice_durations), 2),
            "recent_practice": [
                {
                    "game_id": item.get("game_id"),
                    "practice_type": _practice_label(str(item.get("game_type") or "")),
                    "duration_seconds": item.get("duration_seconds") or 0,
                    "date": item.get("start_time"),
                }
                for item in practice[:5]
            ],
        }

    def get_stats_summary(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        recordings, _ = self.get_recordings(start_date=start_date, end_date=end_date, limit=1000, offset=0)
        total_games = len(recordings)
        practice = [
            item for item in recordings
            if item.get("game_type") in {"practice_single", "practice_pattern", "practice_accuracy"}
        ]
        durations = [float(item.get("duration_seconds") or 0) for item in recordings if item.get("duration_seconds") is not None]
        player_counts: dict[str, int] = {}
        player_wins: dict[str, int] = {}
        for item in recordings:
            for key in ("player1_name", "player2_name"):
                name = str(item.get(key) or "").strip()
                if not name:
                    continue
                player_counts[name] = player_counts.get(name, 0) + 1
                if item.get("game_type") == "nine_ball" and _winner_contains(item.get("winner"), name):
                    player_wins[name] = player_wins.get(name, 0) + 1
        rankings = []
        for name, count in sorted(player_counts.items(), key=lambda entry: entry[1], reverse=True):
            wins = player_wins.get(name, 0)
            rankings.append({
                "name": name,
                "total_games": count,
                "total_wins": wins,
                "win_rate": round((wins / count) if count else 0.0, 2),
            })
        return {
            "total_games": total_games,
            "total_practice_sessions": len(practice),
            "most_active_player": rankings[0]["name"] if rankings else None,
            "average_game_duration": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "player_rankings": rankings,
        }

    def sync_status(self) -> dict[str, Any]:
        table_checks = {}
        for table in ("analytics_recordings", "analytics_events", "analytics_shot_events", "analytics_practice_stats"):
            try:
                rows = self._request_json(
                    f"{self._table_url(table)}?{parse.urlencode({'select': 'id' if table != 'analytics_recordings' else 'game_id', 'limit': '1'})}",
                    method="GET",
                )
                table_checks[table] = {"ok": True, "sample_rows": len(rows) if isinstance(rows, list) else 0}
            except SupabaseAnalyticsError as exc:
                table_checks[table] = {"ok": False, "error": str(exc)[:240]}
        return {"ok": all(item.get("ok") for item in table_checks.values()), "tables": table_checks}

    def _insert(self, table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        endpoint = self._table_url(table)
        return self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )

    def _upsert(self, table: str, payload: dict[str, Any], conflict: str) -> list[dict[str, Any]]:
        endpoint = f"{self._table_url(table)}?on_conflict={parse.quote(conflict, safe=',')}"
        return self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )

    def _table_url(self, table: str) -> str:
        return f"{self.config.url}/rest/v1/{table}"

    def _request_json(
        self,
        endpoint: str,
        method: str,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = request.Request(endpoint, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SupabaseAnalyticsError(f"Supabase analytics request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseAnalyticsError(f"Supabase analytics request failed: {exc}") from exc
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseAnalyticsError("Supabase analytics response was not JSON.") from exc

    def _request_json_with_count(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[list[Any], int]:
        merged_headers = {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
        }
        if headers:
            merged_headers.update(headers)
        req = request.Request(endpoint, headers=merged_headers, method="GET")
        try:
            with request.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8", errors="replace")
                content_range = response.headers.get("Content-Range", "")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SupabaseAnalyticsError(f"Supabase analytics request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseAnalyticsError(f"Supabase analytics request failed: {exc}") from exc
        rows = json.loads(raw) if raw else []
        total = len(rows) if isinstance(rows, list) else 0
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass
        return rows if isinstance(rows, list) else [], total


def configured_supabase_analytics_repository() -> SupabaseAnalyticsRepository | None:
    config = SupabaseAnalyticsConfig.from_env()
    return SupabaseAnalyticsRepository(config) if config else None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value


def _winner_contains(winner: Any, player_name: str) -> bool:
    normalized = player_name.replace(" ", "")
    tokens = [token.strip().replace(" ", "") for token in str(winner or "").split(",") if token.strip()]
    return normalized in tokens


def _practice_belongs_to_player(item: dict[str, Any], player_name: str) -> bool:
    player1 = str(item.get("player1_name") or "").strip()
    player2 = str(item.get("player2_name") or "").strip()
    return player1 == player_name or player2 == player_name or (not player1 and not player2)


def _practice_label(game_type: str) -> str:
    if game_type == "practice_single":
        return "單球練習"
    if game_type == "practice_accuracy":
        return "準度訓練"
    return "球型練習"
