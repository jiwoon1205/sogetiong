class ProfileService:
    @staticmethod
    def public_profile_payload(profile: dict) -> dict:
        return {
            "id": profile.get("id"),
            "nickname": profile.get("nickname"),
            "campus_id": profile.get("campus_id"),
            "age": profile.get("age"),
            "gender": profile.get("gender"),
            "mbti": profile.get("mbti"),
            "bio": profile.get("bio"),
            "profile_status": profile.get("profile_status", "ACTIVE"),
        }
