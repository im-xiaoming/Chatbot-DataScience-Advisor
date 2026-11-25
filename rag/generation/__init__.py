"""Khâu Generation: dựng prompt, gọi LLM stream câu trả lời, kiểm tra môn học trong câu trả lời.

Dùng bởi api/main.py (chat thật) và eval/run_answers.py (chấm điểm). Kiểu dữ liệu dùng chung ở rag/generation/types.py.
"""
from .course_check import CourseCatalog, CourseCheck, default_catalog
from .generator import Generator, ThinkFilter, detect_intent, extract_citations
from .prompts import NO_CONTEXT_ANSWER

__all__ = ["Generator", "ThinkFilter", "detect_intent", "extract_citations", "NO_CONTEXT_ANSWER",
           "CourseCatalog", "CourseCheck", "default_catalog"]
