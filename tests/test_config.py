from app.config import Settings


def test_settings_initializes_with_defaults():
    settings = Settings()
    assert settings.NEO4J_URI == "bolt://localhost:7687"
    assert settings.NEO4J_USER == "neo4j"
    assert settings.NEO4J_PASSWORD == "spatialpassword"
    assert settings.BASETEN_API_KEY == ""
    assert settings.META_API_KEY == ""
    assert settings.MODAL_TOKEN_ID == ""
    assert settings.MODAL_TOKEN_SECRET == ""


def test_settings_custom_overrides():
    custom = Settings(
        NEO4J_URI="bolt://127.0.0.1:7687",
        NEO4J_USER="custom_neo4j",
        NEO4J_PASSWORD="custom_password",
        BASETEN_API_KEY="test_baseten",
        META_API_KEY="test_meta",
        MODAL_TOKEN_ID="test_modal_id",
        MODAL_TOKEN_SECRET="test_modal_secret",
    )
    assert custom.NEO4J_URI == "bolt://127.0.0.1:7687"
    assert custom.NEO4J_USER == "custom_neo4j"
    assert custom.NEO4J_PASSWORD == "custom_password"
    assert custom.BASETEN_API_KEY == "test_baseten"
    assert custom.META_API_KEY == "test_meta"
    assert custom.MODAL_TOKEN_ID == "test_modal_id"
    assert custom.MODAL_TOKEN_SECRET == "test_modal_secret"

