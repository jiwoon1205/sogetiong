import unittest

from fastapi import HTTPException

from app.core.security import create_access_token, decode_token
from app.deps import require_admin
from app.services.auth_service import AuthService
from app.services.matching_service import MatchingService


class MatchingServiceTests(unittest.TestCase):
    def test_hard_filter_excludes_blocked_candidates(self):
        current_user = {
            "id": "user-1",
            "campus_id": "campus-a",
            "gender": "female",
            "age": 22,
            "department_id": "dept-1",
        }
        candidate = {
            "id": "user-2",
            "campus_id": "campus-a",
            "gender": "male",
            "age": 23,
            "department_id": "dept-2",
            "interests": ["coffee", "movies"],
        }
        preferences = {
            "preferred_gender": "male",
            "min_age": 18,
            "max_age": 26,
            "excluded_department_ids": [],
        }

        result = MatchingService.apply_hard_filters(
            current_user=current_user,
            candidate=candidate,
            blocked_user_ids={"user-2"},
            passed_user_ids=set(),
            matched_user_ids=set(),
            preferences=preferences,
        )

        self.assertFalse(result)

    def test_hard_filter_excludes_excluded_department(self):
        current_user = {
            "id": "user-1",
            "campus_id": "campus-a",
            "gender": "female",
            "age": 22,
            "department_id": "dept-1",
        }
        candidate = {
            "id": "user-3",
            "campus_id": "campus-a",
            "gender": "male",
            "age": 24,
            "department_id": "dept-9",
            "interests": ["travel"],
        }
        preferences = {
            "preferred_gender": "male",
            "min_age": 18,
            "max_age": 26,
            "excluded_department_ids": ["dept-9"],
        }

        result = MatchingService.apply_hard_filters(
            current_user=current_user,
            candidate=candidate,
            blocked_user_ids=set(),
            passed_user_ids=set(),
            matched_user_ids=set(),
            preferences=preferences,
        )

        self.assertFalse(result)

    def test_score_prefers_more_similar_profile(self):
        current_user = {
            "id": "user-1",
            "campus_id": "campus-a",
            "gender": "female",
            "age": 22,
            "department_id": "dept-1",
            "interests": ["coffee", "movies", "travel"],
        }
        candidate_a = {
            "id": "user-2",
            "campus_id": "campus-a",
            "gender": "male",
            "age": 23,
            "department_id": "dept-2",
            "interests": ["coffee", "movies"],
        }
        candidate_b = {
            "id": "user-3",
            "campus_id": "campus-a",
            "gender": "male",
            "age": 25,
            "department_id": "dept-4",
            "interests": ["reading"],
        }

        score_a = MatchingService.calculate_score(current_user, candidate_a)
        score_b = MatchingService.calculate_score(current_user, candidate_b)

        self.assertGreater(score_a, score_b)

    def test_create_access_token_includes_role_claim(self):
        token = create_access_token("user-1", role="USER")
        payload = decode_token(token)

        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["role"], "USER")

    def test_require_admin_rejects_non_admin_user(self):
        user = {"id": "user-1", "role": "USER"}

        with self.assertRaises(HTTPException):
            require_admin(user)

    def test_auth_service_verifies_password_hash(self):
        hashed = AuthService.register_user("user@example.com", "secret123")["password_hash"]

        self.assertTrue(AuthService.authenticate_user(hashed, "secret123"))
        self.assertFalse(AuthService.authenticate_user(hashed, "wrong-pass"))


if __name__ == "__main__":
    unittest.main()
