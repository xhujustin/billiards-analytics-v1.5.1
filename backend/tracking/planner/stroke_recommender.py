from __future__ import annotations

from .models import StrokeHint


class StrokeRecommender:
    def recommend(self, route_type: str, cut_angle: float, total_distance: float) -> StrokeHint:
        if route_type == "straight":
            return StrokeHint(
                type="center",
                power="low" if total_distance < 320 else "medium",
                spin="none",
                rationale="直線球以中桿為主，降低偏轉與失誤。",
            )
        if route_type == "cut":
            if cut_angle > 45:
                return StrokeHint(
                    type="soft_cut",
                    power="low",
                    spin="outside_english",
                    rationale="大角度切球採低力道，建議外塞提高容錯。",
                )
            return StrokeHint(
                type="cut_control",
                power="medium",
                spin="none",
                rationale="中等切角以中桿控制母球路線。",
            )
        if route_type == "bank":
            return StrokeHint(
                type="bank_shot",
                power="medium",
                spin="running_english",
                rationale="反彈球建議順塞，提升吃庫後前進穩定度。",
            )
        if route_type == "combo":
            return StrokeHint(
                type="combo",
                power="medium_high",
                spin="top_spin",
                rationale="組合球需穿透力，建議中高力道並帶些高桿。",
            )
        if route_type == "kick":
            return StrokeHint(
                type="kick_escape",
                power="medium",
                spin="running_english",
                rationale="解球路線建議中力道配順塞，提升母球吃庫後找目標球的穩定度。",
            )
        return StrokeHint(
            type="center",
            power="medium",
            spin="none",
            rationale="預設建議中桿中力道。",
        )
