from conftest import ExitJson, module_path, load_module_from_path


class FakeAnsibleModule:
    params = {}
    last = None

    def __init__(self, **_kwargs):
        self.params = dict(self.__class__.params)
        self.warnings = []
        self.__class__.last = self

    def warn(self, msg):
        self.warnings.append(msg)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeOracleHomes:
    def __init__(self, _module):
        self.facts_item = {
            "+ASM": {"ORACLE_HOME": "/nonexistent", "ORACLE_SID": "+ASM", "running": False},
        }
        self.homes = {}

    def list_crs_instances(self):
        return None

    def list_processes(self):
        return None

    def parse_oratab(self):
        return None

    def query_db_status(self, **_kwargs):
        return ["ASM", "STARTED"]


def test_oratab_running_only_does_not_warn_for_asm_false_down(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_oratab.py"), "oracle_oratab_test")
    FakeAnsibleModule.params = {
        "asm_only": False,
        "running_only": True,
        "open_only": False,
        "writable_only": False,
        "homes": None,
        "facts_item": {},
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["oracle_list"] == {}
        assert FakeAnsibleModule.last.warnings == []
    else:
        raise AssertionError("module should exit_json")


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_oratab.py"), "oracle_oratab_test2"
    )


def _base_params(**overrides):
    params = {
        "asm_only": False,
        "running_only": False,
        "open_only": False,
        "writable_only": False,
        "homes": None,
        "facts_item": {},
    }
    params.update(overrides)
    return params


def _patch(monkeypatch, mod, params, homes_cls):
    class Mod(FakeAnsibleModule):
        pass
    Mod.params = params
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", homes_cls, raising=False)
    return Mod


def _make_stat_raises(mod, monkeypatch):
    """Make mod.os.stat raise OSError (stat fails – owner won't be set)."""
    def _raising_stat(path):
        raise OSError("no oracle binary")
    monkeypatch.setattr(mod.os, "stat", _raising_stat)


def _make_stat_ok(mod, monkeypatch, uid=1001, pw_name="oracle"):
    """Make mod.os.stat succeed and mod.getpwuid return a fake pw entry."""
    class FakeStat:
        st_uid = uid

    class FakePwd:
        pass
    FakePwd.pw_name = pw_name

    monkeypatch.setattr(mod.os, "stat", lambda path: FakeStat())
    monkeypatch.setattr(mod, "getpwuid", lambda uid: FakePwd())


# ---------------------------------------------------------------------------
# Covers line 133: owner assignment when stat succeeds
# ---------------------------------------------------------------------------

def test_oratab_owner_assigned_when_stat_succeeds(monkeypatch):
    """When oracle binary stat works, owner is populated (line 133)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "ORCL": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "ORCL",
                    "running": False,
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return ["DOWN"]

    _make_stat_ok(mod, monkeypatch, uid=1001, pw_name="oracle")
    Mod = _patch(monkeypatch, mod, _base_params(), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert result["oracle_list"]["ORCL"]["owner"] == "oracle"
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers lines 141-148: ASM probe when process discovery is restricted
# ---------------------------------------------------------------------------

def test_oratab_asm_probe_when_not_running_sets_running_true(monkeypatch):
    """When +ASM has running=False but has owner, probe is attempted (lines 141-148)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": False,
                    "owner": "grid",   # owner already set
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw):
            return ["ASM", "STARTED"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        # probe happened → running becomes True, status set to ASM result
        assert result["oracle_list"]["+ASM"]["running"] is True
        assert "ASM" in result["oracle_list"]["+ASM"]["status"]
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers line 150: probe exception → status = ['DOWN']
# ---------------------------------------------------------------------------

def test_oratab_asm_probe_exception_yields_down_status(monkeypatch):
    """When query_db_status raises, status falls back to ['DOWN'] (line 150)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": True,
                    "owner": "grid",
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw):
            raise RuntimeError("probe failed")

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert result["oracle_list"]["+ASM"]["status"] == ["DOWN"]
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers line 158: running_only warns for non-ASM down SID
# ---------------------------------------------------------------------------

def test_oratab_running_only_warns_for_normal_down_sid(monkeypatch):
    """running_only=True with a down non-ASM SID emits a warning (line 158)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "ORCL": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "ORCL",
                    "running": False,
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return ["DOWN"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(running_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert result["oracle_list"] == {}
        assert any("ORCL" in w for w in Mod.last.warnings)
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers lines 161-164: asm_only filter removes non-ASM instances
# ---------------------------------------------------------------------------

def test_oratab_asm_only_removes_non_asm_and_warns(monkeypatch):
    """asm_only=True drops non-ASM SIDs and warns (lines 161-164)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "ORCL": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "ORCL",
                    "running": True,
                    "owner": "oracle",
                    "status": ["OPEN", "READ WRITE"],
                },
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": True,
                    "owner": "grid",
                    "status": ["ASM", "STARTED"],
                },
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return []

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(asm_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "ORCL" not in result["oracle_list"]
        assert "+ASM" not in result["oracle_list"]  # ASM not in status (probe returns [])
        assert any("ORCL" in w for w in Mod.last.warnings)
    else:
        raise AssertionError("should exit_json")


def test_oratab_asm_only_keeps_asm_instance(monkeypatch):
    """asm_only=True keeps a SID whose status contains 'ASM' (lines 161-163)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": True,
                    "owner": "grid",
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return ["ASM", "STARTED"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(asm_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "+ASM" in result["oracle_list"]
        assert Mod.last.warnings == []
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers lines 167-172: open_only filter
# ---------------------------------------------------------------------------

def test_oratab_open_only_removes_closed_db_and_warns(monkeypatch):
    """open_only=True drops databases that are not OPEN (lines 167-172)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "ORCL": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "ORCL",
                    "running": True,
                    "owner": "oracle",
                },
                "MOUNTED": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "MOUNTED",
                    "running": True,
                    "owner": "oracle",
                },
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, oracle_sid=None, **_kw):
            if oracle_sid == "ORCL":
                return ["OPEN", "READ WRITE"]
            return ["MOUNTED"]  # not OPEN

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(open_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "ORCL" in result["oracle_list"]
        assert "MOUNTED" not in result["oracle_list"]
        assert any("MOUNTED" in w for w in Mod.last.warnings)
    else:
        raise AssertionError("should exit_json")


def test_oratab_open_only_keeps_asm_regardless(monkeypatch):
    """open_only=True skips ASM instances (they are not checked for OPEN) (line 168-169)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": True,
                    "owner": "grid",
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return ["ASM", "STARTED"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(open_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "+ASM" in result["oracle_list"]
        assert Mod.last.warnings == []
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers lines 175-180: writable_only filter
# ---------------------------------------------------------------------------

def test_oratab_writable_only_removes_read_only_db(monkeypatch):
    """writable_only=True drops non-READ WRITE databases (lines 175-180)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "ORCL": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "ORCL",
                    "running": True,
                    "owner": "oracle",
                },
                "READONLY": {
                    "ORACLE_HOME": "/fake/home",
                    "ORACLE_SID": "READONLY",
                    "running": True,
                    "owner": "oracle",
                },
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, oracle_sid=None, **_kw):
            if oracle_sid == "ORCL":
                return ["OPEN", "READ WRITE"]
            return ["OPEN", "READ ONLY"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(writable_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "ORCL" in result["oracle_list"]
        assert "READONLY" not in result["oracle_list"]
        assert any("READONLY" in w for w in Mod.last.warnings)
    else:
        raise AssertionError("should exit_json")


def test_oratab_writable_only_keeps_asm_regardless(monkeypatch):
    """writable_only=True skips ASM instances (line 176-177)."""
    mod = _load()

    class Homes:
        def __init__(self, _m):
            self.facts_item = {
                "+ASM": {
                    "ORACLE_HOME": "/fake/grid",
                    "ORACLE_SID": "+ASM",
                    "running": True,
                    "owner": "grid",
                }
            }
            self.homes = {}

        def list_crs_instances(self): return None
        def list_processes(self): return None
        def parse_oratab(self): return None
        def query_db_status(self, **_kw): return ["ASM", "STARTED"]

    _make_stat_raises(mod, monkeypatch)
    Mod = _patch(monkeypatch, mod, _base_params(writable_only=True), Homes)

    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert "+ASM" in result["oracle_list"]
        assert Mod.last.warnings == []
    else:
        raise AssertionError("should exit_json")


# ---------------------------------------------------------------------------
# Covers lines 184-195: homes filter
# ---------------------------------------------------------------------------

def _homes_base_params(homes_val):
    return _base_params(homes=homes_val)


class _HomesWithTypes:
    """OracleHomes stub with multiple home types for filter tests."""

    def __init__(self, _m):
        self.facts_item = {}
        self.homes = {
            "/oh/client":  {"home_type": "client",  "ORACLE_HOME": "/oh/client"},
            "/oh/server":  {"home_type": "server",  "ORACLE_HOME": "/oh/server"},
            "/oh/crs":     {"home_type": "crs",     "ORACLE_HOME": "/oh/crs"},
            "/oh/gateway": {"home_type": "gateway", "ORACLE_HOME": "/oh/gateway"},
        }

    def list_crs_instances(self): return None
    def list_processes(self): return None
    def parse_oratab(self): return None
    def query_db_status(self, **_kw): return []


def test_oratab_homes_all_keeps_everything(monkeypatch):
    """homes='all' → all home types retained (line 186-187)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params("all"), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert len(result["OracleHomes"]) == 4
    else:
        raise AssertionError("should exit_json")


def test_oratab_homes_client_filter(monkeypatch):
    """homes='client' → only client homes retained (lines 188-189)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params("client"), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert all(v["home_type"] == "client" for v in result["OracleHomes"].values())
        assert len(result["OracleHomes"]) == 1
    else:
        raise AssertionError("should exit_json")


def test_oratab_homes_server_filter(monkeypatch):
    """homes='server' → only server homes retained (lines 190-191)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params("server"), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert all(v["home_type"] == "server" for v in result["OracleHomes"].values())
        assert len(result["OracleHomes"]) == 1
    else:
        raise AssertionError("should exit_json")


def test_oratab_homes_crs_filter(monkeypatch):
    """homes='crs' → only crs homes retained (lines 192-193)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params("crs"), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert all(v["home_type"] == "crs" for v in result["OracleHomes"].values())
        assert len(result["OracleHomes"]) == 1
    else:
        raise AssertionError("should exit_json")


def test_oratab_homes_gateway_filter(monkeypatch):
    """homes='gateway' → only gateway homes retained (lines 194-195)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params("gateway"), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        assert all(v["home_type"] == "gateway" for v in result["OracleHomes"].values())
        assert len(result["OracleHomes"]) == 1
    else:
        raise AssertionError("should exit_json")


def test_oratab_homes_none_keeps_all(monkeypatch):
    """homes=None (default) → homes dict untouched, exit_json called (line 197/201)."""
    mod = _load()
    _make_stat_raises(mod, monkeypatch)
    _patch(monkeypatch, mod, _homes_base_params(None), _HomesWithTypes)
    try:
        mod.main()
    except ExitJson as exc:
        result = exc.args[0]
        # All homes present when no filter applied
        assert len(result["OracleHomes"]) == 4
        assert result["changed"] is False
    else:
        raise AssertionError("should exit_json")
