"""CORS allowlist parsing."""

from backend.shared.config import Settings


def test_default_origins_are_local_vite_dev_and_preview():
    settings = Settings()
    origins = settings.cors_origin_list
    assert origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    assert "*" not in origins


def test_comma_separated_origins_are_stripped():
    settings = Settings(
        cors_allowed_origins=" https://dashboard.example.com , http://localhost:5173 "
    )
    assert settings.cors_origin_list == [
        "https://dashboard.example.com",
        "http://localhost:5173",
    ]


def test_empty_value_yields_no_origins():
    settings = Settings(cors_allowed_origins="")
    assert settings.cors_origin_list == []
