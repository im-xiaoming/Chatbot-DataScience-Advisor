"""Kiểm tra câu trả lời có nhắc tới môn học không có trong niên giám (đề bài: "không tự bịa môn").

Đọc bảng các học kỳ trong kế hoạch đào tạo (data/normalized/curriculum/...-ke-hoach-dao-tao-2023.md),
rồi đối chiếu mã môn 7 chữ số và học kỳ mà câu trả lời ghi trên cùng một dòng.
Chạy sau khi sinh xong câu trả lời: api/main.py gửi kết quả trong sự kiện "done" để giao diện cảnh báo,
eval/run_answers.py đếm thành chỉ số invented_codes / semester_mismatch / name_mismatch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .types import CourseCheckDict, NameMismatch, SemesterMismatch

DEFAULT_PLAN = "data/normalized/curriculum/iuh-khdl-ke-hoach-dao-tao-2023.md"
CODE_RE = re.compile(r"(?<!\d)(2\d{6})(?!\d)")  # mã môn IUH: 7 chữ số bắt đầu bằng 2
SEMESTER_RE = re.compile(r"(?:học kỳ|học kì|hk)\s*(\d)", re.I)


@dataclass(frozen=True)
class Course:
    """Một dòng trong bảng học kỳ của niên giám."""

    code: str
    name: str
    semester: int
    credits: int
    required: bool


@dataclass
class CourseCheck:
    """Kết quả đối chiếu một câu trả lời với niên giám."""

    codes: list[str] = field(default_factory=list)            # mã môn có trong câu trả lời
    unknown: list[str] = field(default_factory=list)          # mã không có trong niên giám
    semester_mismatch: list[SemesterMismatch] = field(default_factory=list)  # ghi sai học kỳ
    name_mismatch: list[NameMismatch] = field(default_factory=list)      # mã của môn này ghép với tên môn khác

    @property
    def ok(self) -> bool:
        """Không có lỗi nào trong ba loại."""
        return not self.unknown and not self.semester_mismatch and not self.name_mismatch

    def as_dict(self) -> CourseCheckDict:
        """Dạng JSON gửi cho giao diện (khoá course_check của sự kiện "done")."""
        return {"codes": self.codes, "unknown": self.unknown, "semester_mismatch": self.semester_mismatch,
                "name_mismatch": self.name_mismatch}


class CourseCatalog:
    """Danh mục môn học tra theo mã, dựng từ niên giám.

    Args:
        courses: mã môn -> Course.
    """

    def __init__(self, courses: dict[str, Course]) -> None:
        self.courses = courses
        # tên dài trước để "Thống kê máy tính và ứng dụng" không bị khớp nhầm thành tên ngắn hơn
        self._names = sorted(((c.name.lower(), c) for c in courses.values()), key=lambda x: -len(x[0]))

    @classmethod
    def from_markdown(cls, path: str | Path = DEFAULT_PLAN) -> "CourseCatalog":
        """Đọc các bảng "## Học kỳ N" trong file Markdown của niên giám.

        Mỗi dòng bảng cần ít nhất 5 cột: mã | tên | ... | tín chỉ | Bắt buộc/Tự chọn.

        Raises:
            FileNotFoundError: không có file niên giám (default_catalog() bắt lỗi này và trả None).
        """
        courses: dict[str, Course] = {}
        semester = None
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):  # "## Học kỳ N" mở bảng của học kỳ N; mục "##" khác thì dừng
                m = re.match(r"^## Học kỳ (\d+)", line)
                semester = int(m.group(1)) if m else None
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if semester and len(cells) >= 5 and CODE_RE.fullmatch(cells[0]):
                # mypy không biết lần re.match thứ hai trả cùng kết quả với lần kiểm tra ngay sau "if"
                credits = int(re.match(r"\d+", cells[3]).group(0)) if re.match(r"\d+", cells[3]) else 0  # type: ignore[union-attr]
                courses[cells[0]] = Course(cells[0], cells[1], semester, credits, cells[4].startswith("Bắt buộc"))
        return cls(courses)

    def check(self, answer: str) -> CourseCheck:
        """Đối chiếu từng dòng của câu trả lời với niên giám.

        Xét theo dòng vì LLM thường viết mỗi môn một dòng (bảng hoặc gạch đầu dòng). Mã lạ luôn bị ghi
        vào unknown; sai học kỳ và ghép sai tên chỉ kết luận khi dòng có đúng một mã môn, để tránh
        báo nhầm ở câu dài nhắc nhiều môn.
        """
        res = CourseCheck()
        for line in answer.splitlines():
            codes = CODE_RE.findall(line)
            if not codes:
                continue
            sem = SEMESTER_RE.findall(line)
            for code in codes:
                if code not in res.codes:
                    res.codes.append(code)
                course = self.courses.get(code)
                if course is None:
                    if code not in res.unknown:
                        res.unknown.append(code)
                    continue
                if len(codes) != 1:  # chỉ kết luận khi dòng có đúng 1 mã môn (tránh hiểu nhầm câu dài)
                    continue
                # sai học kỳ: dòng có đúng 1 học kỳ và khác niên giám
                if len(sem) == 1 and int(sem[0]) != course.semester:
                    res.semester_mismatch.append({"code": code, "name": course.name,
                                                  "said": int(sem[0]), "actual": course.semester})
                # ghép sai tên: dòng không có tên đúng của mã này nhưng lại có tên một môn khác
                low = line.lower()
                if course.name.lower() not in low:
                    other = next((c for name, c in self._names if c.code != code and name in low), None)
                    if other:
                        res.name_mismatch.append({"code": code, "said_name": other.name, "actual_name": course.name,
                                                  "said_name_code": other.code})
        return res


@lru_cache(maxsize=1)
def default_catalog() -> CourseCatalog | None:
    """Niên giám mặc định, đọc một lần rồi dùng lại; None nếu chạy ngoài thư mục gốc repo (không thấy file)."""
    try:
        return CourseCatalog.from_markdown(DEFAULT_PLAN)
    except FileNotFoundError:
        return None
