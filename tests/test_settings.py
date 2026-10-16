from locallibrary import config as config_module
from locallibrary.config import load_settings, save_settings


def test_round_trip_and_bad_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "settings_path", lambda: tmp_path / "settings.json")
    assert load_settings() == {}
    save_settings({"background": "/x.png"})
    assert load_settings() == {"background": "/x.png"}
    (tmp_path / "settings.json").write_text("{not json")
    assert load_settings() == {}
