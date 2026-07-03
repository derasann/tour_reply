from tlst_automation.spreadsheet_masker import mask_csv_text, mask_spreadsheet_cell, to_csv_export_url


def test_converts_google_sheet_url_to_csv_export_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=456"

    assert (
        to_csv_export_url(url)
        == "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=456"
    )


def test_masks_csv_cells_without_breaking_csv_shape() -> None:
    csv_text = "date,guest,email,phone\n2026-05-14,Mr Robert Cunningham,robert@example.com,+81 70-1234-5678\n"

    masked = mask_csv_text(csv_text, strength=3)

    assert "robert@example.com" not in masked
    assert "+81 70-1234-5678" not in masked
    assert "Mr. Ro" in masked
    assert masked.count(",") == csv_text.count(",")


def test_strength_max_masks_japanese_names_and_company_names() -> None:
    row = "***-***-***5,小野寺誠一,株式会社インアウトバウンド,onodera@example.com\n"

    masked = mask_csv_text(row, strength=5)

    assert "小野寺誠一" not in masked
    assert "株式会社インアウトバウンド" not in masked
    assert "小***一" in masked
    assert "株式会社イ********" in masked


def test_strength_max_masks_single_japanese_name_cell() -> None:
    assert mask_spreadsheet_cell("小野寺誠一", strength=5) == "小***一"
