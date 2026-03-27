import pytest

from conftest import module_path, load_module_from_path


class SpecCaptured(Exception):
    pass


def _capture_ansible_spec(module):
    class FakeAnsibleModule:
        def __init__(self, **kwargs):
            raise SpecCaptured(kwargs)

    module.AnsibleModule = FakeAnsibleModule


def test_oracle_profile_required_together_is_correct():
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_profile.py"), "oracle_profile_spec")
    _capture_ansible_spec(mod)
    with pytest.raises(SpecCaptured) as exc:
        mod.main()
    kwargs = exc.value.args[0]
    required_together = kwargs["required_together"]
    assert ["attribute_name", "attribute_value"] in required_together


def test_oracle_ldapuser_marks_sensitive_fields_no_log():
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_ldapuser.py"), "oracle_ldapuser_spec")
    _capture_ansible_spec(mod)
    with pytest.raises(SpecCaptured) as exc:
        mod.main()
    spec = exc.value.args[0]["argument_spec"]
    assert spec["password"]["no_log"] is True
    assert spec["user_default_password"]["no_log"] is True
    assert spec["ldap_bindpassword"]["no_log"] is True


def test_oracle_awr_validation_fails_before_connection():
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_awr.py"), "oracle_awr_validation")

    class FakeAnsibleModule:
        def __init__(self, **_kwargs):
            self.params = {
                "user": "u",
                "password": "p",
                "mode": "normal",
                "hostname": "localhost",
                "port": 1521,
                "service_name": "svc",
                "dsn": None,
                "oracle_home": None,
                "snapshot_interval_min": 5,
                "snapshot_retention_days": 8,
            }

        def fail_json(self, **kwargs):
            raise RuntimeError(kwargs)

        def exit_json(self, **kwargs):
            raise RuntimeError(kwargs)

    mod.AnsibleModule = FakeAnsibleModule
    with pytest.raises(RuntimeError) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "Snapshot interval must be >= 10 or 0" in payload["msg"]
