class MatchingService:
    @staticmethod
    def apply_hard_filters(
        *,
        current_user: dict,
        candidate: dict,
        blocked_user_ids: set[str],
        passed_user_ids: set[str],
        matched_user_ids: set[str],
        preferences: dict,
    ) -> bool:
        if candidate["id"] == current_user["id"]:
            return False
        if candidate["id"] in blocked_user_ids:
            return False
        if candidate["id"] in passed_user_ids:
            return False
        if candidate["id"] in matched_user_ids:
            return False
        if current_user["campus_id"] != candidate["campus_id"]:
            return False
        if candidate["gender"] != preferences.get("preferred_gender"):
            return False
        if not (preferences.get("min_age") <= candidate["age"] <= preferences.get("max_age")):
            return False
        excluded = set(preferences.get("excluded_department_ids", []))
        if candidate["department_id"] in excluded:
            return False
        return True

    @staticmethod
    def calculate_score(current_user: dict, candidate: dict) -> float:
        candidate_interests = set(candidate.get("interests", []))
        current_interests = set(current_user.get("interests", []))
        overlap = len(candidate_interests & current_interests)
        base_score = overlap * 10.0
        if current_user.get("department_id") == candidate.get("department_id"):
            base_score += 5
        return base_score
