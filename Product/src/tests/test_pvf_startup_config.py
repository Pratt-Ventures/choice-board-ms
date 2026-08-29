"""Tests for pvf startup YAML configuration: loading, validation, readonly settings injection."""
from enum import StrEnum

import pytest

from src.pvf.config.pvf_config_settings import PvfGlobalSettings
from src.pvf.bindings.pvf_startup_config import (
    PvfStartupConfig,
    PvfStartupConfigError,
    apply_startup_config,
    find_startup_config_path,
    load_startup_config,
    normalize_str_list,
)


class _SampleAction(StrEnum):
    vote = "vote"
    report = "report"


# --- normalize_str_list -----------------------------------------------------

def test_normalize_str_list_accepts_enums_strings_and_lists():
    assert normalize_str_list(None) == []
    assert normalize_str_list("vote") == ["vote"]
    assert normalize_str_list("vote, report ,,") == ["vote", "report"]
    assert normalize_str_list(_SampleAction.vote) == ["vote"]
    assert normalize_str_list([_SampleAction.vote, "report", _SampleAction.report]) == ["vote", "report", "report"]
    assert normalize_str_list([]) == []


# --- YAML loading -------------------------------------------------------------

def test_load_startup_config_reads_repo_startup_file():
    config = load_startup_config()  # discovers src/pvf_app_startup.yaml
    assert config.application.shell_module == "src.app_shell"
    assert config.application.entry_point == "app_startup"
    assert config.env_file == ".env"
    assert config.share.object_actions == ["not_set", "vote", "vote_view", "report"]
    assert config.share.access_operations == ["not_set", "vote", "view", "report"]
    assert isinstance(config.features.activate_share_links, bool)
    assert config.features.activate_customer_communication is True
    assert config.features.activate_ai_agents is True


def test_find_startup_config_path_honors_env_override(tmp_path, monkeypatch):
    override = tmp_path / "custom_startup.yaml"
    monkeypatch.setenv("PVF_STARTUP_CONFIG", str(override))
    assert find_startup_config_path() == override


def test_load_startup_config_missing_file_is_descriptive(tmp_path):
    with pytest.raises(PvfStartupConfigError, match="not found"):
        load_startup_config(tmp_path / "does_not_exist.yaml")


def test_load_startup_config_invalid_yaml_is_descriptive(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("features: [unclosed\n")
    with pytest.raises(PvfStartupConfigError, match="not valid YAML"):
        load_startup_config(bad)


def test_load_startup_config_non_mapping_is_descriptive(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- just\n- a\n- list\n")
    with pytest.raises(PvfStartupConfigError, match="must be a YAML mapping"):
        load_startup_config(bad)


def test_load_startup_config_bad_value_type_is_descriptive(tmp_path):
    bad = tmp_path / "badtype.yaml"
    bad.write_text("features:\n  activate_stripe_integration: not-a-bool\n")
    with pytest.raises(PvfStartupConfigError, match="is invalid"):
        load_startup_config(bad)


def test_load_startup_config_empty_file_uses_defaults(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    config = load_startup_config(empty)
    assert config.env_file == ".env"
    assert config.features.activate_stripe_integration is False
    assert config.features.activate_customer_communication is True
    assert config.share.object_actions == ["not_set"]


# --- readonly injection -------------------------------------------------------

def _fresh_settings() -> PvfGlobalSettings:
    # fresh instance so injection never touches the process-global settings
    return PvfGlobalSettings()


def test_apply_startup_config_injects_values():
    settings_obj = _fresh_settings()
    config = PvfStartupConfig.model_validate({
        "features": {
            "activate_stripe_integration": True,
            "activate_external_api": False,
            "activate_customer_communication": False,
            "activate_ai_agents": True,
        },
        "share": {"object_actions": ["alpha", "beta"]},
    })
    apply_startup_config(config, settings_obj)
    assert settings_obj.ACTIVATE_STRIPE_INTEGRATION is True
    assert settings_obj.ACTIVATE_EXTERNAL_API is False
    assert settings_obj.ACTIVATE_CUSTOMER_COMMUNICATION is False
    assert settings_obj.ACTIVATE_AI_AGENTS is True
    assert settings_obj.SHARE_OBJECT_ACTIONS == ["alpha", "beta"]


def test_startup_owned_values_reject_ordinary_assignment():
    settings_obj = _fresh_settings()
    for name in ("ACTIVATE_STRIPE_INTEGRATION", "ACTIVATE_SHARE_LINKS", "ACTIVATE_CUSTOMER_COMMUNICATION", "ACTIVATE_AI_AGENTS", "SHARE_OBJECT_ACTIONS"):
        with pytest.raises(RuntimeError, match="read-only"):
            setattr(settings_obj, name, True)


def test_startup_owned_values_ignore_process_environment(monkeypatch):
    # even when present in the environment, startup-owned values keep their
    # declared defaults — only the YAML startup path may set them
    monkeypatch.setenv("ACTIVATE_STRIPE_INTEGRATION", "1")
    monkeypatch.setenv("ACTIVATE_BRANDING_IMAGE_STORE", "1")
    monkeypatch.setenv("ACTIVATE_CUSTOMER_COMMUNICATION", "0")
    settings_obj = _fresh_settings()
    assert settings_obj.ACTIVATE_STRIPE_INTEGRATION is False
    assert settings_obj.ACTIVATE_BRANDING_IMAGE_STORE is False
    assert settings_obj.ACTIVATE_CUSTOMER_COMMUNICATION is True


def test_inject_startup_values_rejects_unknown_names():
    settings_obj = _fresh_settings()
    with pytest.raises(KeyError, match="not a startup-owned setting"):
        settings_obj._inject_startup_values({"BOOTSTRAP_SAMPLE_DATA": 1})
