from rag.generation import CourseCatalog, default_catalog


def test_catalog_matches_curriculum_totals():
    c = default_catalog()
    assert len(c.courses) == 85
    assert c.courses["2101631"].name == "Máy học" and c.courses["2101631"].semester == 6
    assert sum(x.credits for x in c.courses.values() if x.required) == 133  # + 29 TC tự chọn = 162


def test_flags_invented_code_and_wrong_semester():
    r = default_catalog().check("| Học kỳ 6 | 2101631 | Máy học |\n| HK 5 | 2101650 | Học sâu |\n| HK2 | 2109999 | Rust |")
    assert r.unknown == ["2109999"]
    assert r.semester_mismatch == [{"code": "2101650", "name": "Học sâu", "said": 5, "actual": 7}]
    assert not r.ok


def test_ignores_lines_with_several_semesters_or_no_codes():
    r = default_catalog().check("Học sâu 2101650 học sau Máy học 2101631, từ học kỳ 6 sang học kỳ 7.\nKhông có mã nào.")
    assert r.ok and r.codes == ["2101650", "2101631"]


def test_from_markdown(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("## Học kỳ 1 (2 tín chỉ)\n| Mã | Tên | EN | TC | Loại |\n|---|---|---|---|---|\n"
                 "| 2100001 | Môn A | A | 2(2,0,4) | Bắt buộc |\n## Danh mục\n| 2100002 | Không tính | B | 3 | Bắt buộc |\n",
                 encoding="utf-8")
    c = CourseCatalog.from_markdown(p)
    assert list(c.courses) == ["2100001"] and c.courses["2100001"].credits == 2


def test_flags_code_paired_with_another_course_name():
    # lỗi thật từ Ollama 23/11: mã 2101685 (Tối ưu hóa cho KHDL) ghép với tên "Thống kê máy tính và ứng dụng"
    r = default_catalog().check("| **Phân tích chuyên sâu** | 2101685 | Thống kê máy tính và ứng dụng | ... [1] |")
    assert r.name_mismatch == [{"code": "2101685", "said_name": "Thống kê máy tính và ứng dụng",
                                "actual_name": "Tối ưu hóa cho Khoa học dữ liệu", "said_name_code": "2101624"}]


def test_name_check_ignores_abbreviations_and_multi_code_lines():
    r = default_catalog().check("| 2101685 | Tối ưu hóa cho KHDL |\n| 2101685, 2101686 | Thống kê máy tính và ứng dụng |\n"
                                "| 2101624 | Thống kê máy tính và ứng dụng |")
    assert r.name_mismatch == [] and r.ok
