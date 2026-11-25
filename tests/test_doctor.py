from api import doctor


def test_suggest_uses_fake_llm_when_ollama_missing():
    rows = [(doctor.FAIL, "Ollama", "", ""), (doctor.WARN, "Qdrant", "", "")]
    assert doctor.suggest(rows).startswith("LLM=fake uv run uvicorn")


def test_suggest_real_mode_when_everything_ok():
    rows = [(doctor.OK, "Ollama", "", ""), (doctor.OK, "Model qwen3.5:4b", "", ""), (doctor.OK, "Qdrant", "", "")]
    assert doctor.suggest(rows).startswith("RETRIEVER=qdrant uv run uvicorn")


def test_check_data_finds_documents():
    status, _, detail, _ = doctor.check_data()
    assert status == doctor.OK and detail.startswith("49")


def test_check_packages_runs_in_fresh_interpreter():
    # lỗi cũ: chỉ "import importlib" rồi gọi importlib.util -> AttributeError khi import doctor trực tiếp
    # (trong pytest importlib.util đã được nạp sẵn nên phải chạy ở tiến trình mới mới bắt được)
    import os
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", "from api import doctor; print(doctor.check_packages()[1])"],
                         capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"})  # console Windows mặc định cp1252
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "Thư viện"
