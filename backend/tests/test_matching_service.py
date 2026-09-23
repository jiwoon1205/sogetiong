import shutil
import unittest
import uuid
from io import BytesIO

from fastapi import HTTPException, UploadFile

from app.core.security import create_access_token, decode_token
from app.deps import require_admin, require_role
from app.services.auth_service import AuthService
from app.services.matching_service import MatchingService
from app.services.storage_service import StorageService


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

    def test_require_role_accepts_string_role(self):
        user = {"id": "user-1", "role": "USER"}

        self.assertEqual(require_role(user, "USER"), user)

    def test_require_admin_accepts_photo_reviewer_role(self):
        user = {"id": "admin-1", "role": "PHOTO_REVIEWER"}

        self.assertEqual(require_admin(user), user)

    def test_require_admin_rejects_non_admin_user(self):
        user = {"id": "user-1", "role": "USER"}

        with self.assertRaises(HTTPException):
            require_admin(user)

    def test_require_admin_accepts_photo_reviewer(self):
        user = {"id": "admin-1", "role": "PHOTO_REVIEWER"}

        self.assertEqual(require_admin(user), user)

    def test_auth_service_accepts_hufs_email_and_rejects_other_domains(self):
        self.assertTrue(AuthService.is_valid_school_email("student@hufs.ac.kr"))
        self.assertTrue(AuthService.is_valid_school_email("STUDENT@hufs.ac.kr"))
        self.assertFalse(AuthService.is_valid_school_email("student@gmail.com"))
        self.assertFalse(AuthService.is_valid_school_email("student@naver.com"))

    def test_auth_service_verifies_password_hash(self):
        hashed = AuthService.register_user("user@example.com", "secret123")["password_hash"]

        self.assertTrue(AuthService.authenticate_user(hashed, "secret123"))
        self.assertFalse(AuthService.authenticate_user(hashed, "wrong-pass"))

    def test_storage_service_saves_photo_to_private_storage(self):
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        upload_file = UploadFile(filename="avatar.png", file=BytesIO(b"test-image-data"), headers={"content-type": "image/png"})

        storage_key = StorageService.save_uploaded_file(upload_file, user_id)
        saved_path = StorageService.STORAGE_ROOT / storage_key

        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.read_bytes(), b"test-image-data")
        self.assertTrue(storage_key.startswith(f"private/{user_id}/"))

        saved_path.unlink()
        shutil.rmtree(saved_path.parent.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
