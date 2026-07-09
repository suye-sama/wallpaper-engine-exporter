from wallpaper_exporter.app import main


def test_app_main_exists_without_launching_qt():
    assert callable(main)
