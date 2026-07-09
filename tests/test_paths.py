from wallpaper_exporter.paths import export_folder_for, sanitize_windows_name


def test_sanitize_windows_name_replaces_invalid_characters():
    assert sanitize_windows_name('a:b*c?d"e<f>g|') == "a_b_c_d_e_f_g_"


def test_sanitize_windows_name_handles_empty_values():
    assert sanitize_windows_name("   ") == "untitled"


def test_export_folder_uses_chinese_group_folder(tmp_path):
    folder = export_folder_for(tmp_path, "星之砂浜")

    assert folder == tmp_path / "导出原图" / "星之砂浜"
