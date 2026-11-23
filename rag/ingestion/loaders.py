from __future__ import annotations

import re
import logging
from collections import Counter
from datetime import date
from urllib.parse import urlsplit

from typing import Optional
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters.markdown import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.types import DocRecord, ChunkRecord
from config import RecursiveCharacterTextSplitterConfig
from common import _encode_string


logger = logging.getLogger(__name__)


HEADER_2_SPLIT = [
        ('#', 'Header 1'),
        ('##', 'Header 2'),
        ('###', 'Header 3'),
        ('####', 'Header 4'),
        ('#####', 'Header 5')
    ]

MARKDOWN_SPLITTER = MarkdownHeaderTextSplitter(
    headers_to_split_on=HEADER_2_SPLIT,
    strip_headers=False
)


def _to_json(page_content: str) -> dict:
    d: dict[str, str] = {}
    for r in re.finditer(r"(\w+):\s*(.+)", page_content):
        d[r.group(1)] = r.group(2) if not r.group(2).startswith("'") else r.group(2)[1:-1]
    return d


def _content_standardized(page_content: str) -> list[Document]:
    return re.sub(r'<!--\s*(\w+)\s*(\d*)\s*-->', '', page_content).strip()


def review_document(
    metadata: dict[str, str], body: str
) -> tuple[str, list[str]]:
    errors: list[str] = []

    for field in ("doc_id", "title", "url", "category", "publisher"):
        if not metadata.get(field, "").strip():
            errors.append(f"Thiếu {field}")

    url = metadata.get("url", "").strip()
    if url:
        try:
            source = urlsplit(url)
            if source.scheme not in ("http", "https") or not source.hostname:
                errors.append("URL nguồn phải có giao thức HTTP(S) và tên miền")
        except ValueError:
            errors.append("URL nguồn sai định dạng")

    if not re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip():
        errors.append("Nội dung tài liệu rỗng")

    dates: dict[str, date] = {}
    for field in ("published_date", "valid_until"):
        value = metadata.get(field, "").strip()
        if not value:
            continue
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError
            dates[field] = parsed
        except ValueError:
            errors.append(f"{field} phải là ngày hợp lệ dạng YYYY-MM-DD")

    if (
        "published_date" in dates
        and "valid_until" in dates
        and dates["valid_until"] < dates["published_date"]
    ):
        errors.append("Ngày hết hiệu lực sớm hơn ngày ban hành")

    if errors:
        return "needs_fix", errors
    if metadata.get("needs_review", "").strip().lower() == "true":
        return "pending_review", ["Cần đối chiếu với nguồn gốc"]
    return "passed_checks", []


def _review_markdown(text: str) -> tuple[str, list[str]]:
    frontmatter = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    if frontmatter is None:
        return "needs_fix", ["Thiếu khối metadata đầu tệp"]
    return review_document(_to_json(frontmatter[1]), text[frontmatter.end():])


def _build_section_path(docs: list[Document]) -> list[Document]:
    headers: dict[str: Optional[str]] = {h[1]: None for h in HEADER_2_SPLIT}
    
    for doc in docs:
        last_header = None
        for _, header in HEADER_2_SPLIT:
            if header in doc.metadata:
                headers[header] = str(doc.metadata[header])
                last_header = header
        if last_header:
            for _, header in HEADER_2_SPLIT:
                if headers[header]:
                    doc.metadata.setdefault('section_path', []).append(headers[header])
                if header == last_header:
                    break
    return docs


class Splitter:
    def __init__(
        self,
        *,
        recursive_config: RecursiveCharacterTextSplitterConfig
    ):
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " ", ""],
            chunk_size=recursive_config.chunk_size,
            chunk_overlap=recursive_config.chunk_overlap
        )
    
    
    def _load(self, path: str) -> Optional[str]:
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                return f.read().strip()
                
        except (FileExistsError, FileNotFoundError):
            logging.exception(f"Failed to load file {path}.")
            return None
        
    
    def _markdown_text_splitter(self, text: str):
        return MARKDOWN_SPLITTER.split_text(text=text)
    
    
    def _recursive_character_splitter(self, docs: list[Document]) -> list[Document]:
        return self.text_splitter.split_documents(docs)
    
    
    def _rebuild_docs(self, docs: list[Document]) -> list[Document]:
        new_docs = docs[1:]
        metadata = _to_json(docs[0].page_content)
        for doc in new_docs:
            doc.page_content = _content_standardized(doc.page_content)
            doc.metadata = {
                **doc.metadata,
                **metadata,
            }
            doc.metadata['doc_id'] = _encode_string(doc.metadata['title'])
            doc.metadata['page_content'] = doc.page_content
        new_docs = _build_section_path(new_docs)
        return new_docs
               
    
    def split_document(self, path: str) -> list[Document]:
        text = self._load(path)
        return self._split_text(text)

    def _split_text(self, text: str | None) -> list[Document]:
        if text:
            docs = self._markdown_text_splitter(text)
            docs = self._rebuild_docs(docs)
            
            # add chunk_id
            def _generate_id(doc_id, index: int) -> str:
                return doc_id + '+' + str(index).zfill(15)

            documents: dict[str, list[str]] = {}
            for doc in docs:
                documents.setdefault(doc.metadata['doc_id'], []).extend(self._recursive_character_splitter([doc]))
                
            full_docs = []
            for doc_id, _docs in documents.items():
                for i, doc in enumerate(_docs):
                    doc.metadata['chunk_id'] = _generate_id(doc_id, i)
                    full_docs.append(doc)
            
            return full_docs
        
        return []
            
    
    def split_documents(
        self, glob_path: str, *, review_only: bool = False, checked_only: bool = False
    ) -> list[Document]:
        logging.info("Starting to split documents.")
        sources: list[tuple[Path, str, str | None, str | None]] = []
        targets: dict[str, list[str | None]] = {}
        for file in Path(glob_path).rglob('*.md'):
            text = self._load(file)
            if text is None or (not text and not review_only):
                continue
            frontmatter = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
            metadata = _to_json(frontmatter[1]) if frontmatter else {}
            doc_id = metadata.get('doc_id')
            duplicate_of = metadata.get('duplicate_of')
            sources.append((file, text, doc_id, duplicate_of))
            if doc_id:
                targets.setdefault(doc_id, []).append(duplicate_of)

        skipped: dict[Path, str] = {}
        for file, _, doc_id, duplicate_of in sources:
            if not duplicate_of:
                continue
            visited = {doc_id}
            target = duplicate_of
            while True:
                if target in visited:
                    raise ValueError(f"{file}: duplicate_of cycle at {target!r}")
                matches = targets.get(target, [])
                if len(matches) != 1:
                    raise ValueError(
                        f"{file}: duplicate_of target {target!r} matches {len(matches)} documents"
                    )
                next_target = matches[0]
                if not next_target:
                    skipped[file] = target
                    break
                visited.add(target)
                target = next_target

        if review_only:
            counts: Counter[str] = Counter()
            for file, text, _, _ in sources:
                if file in skipped:
                    counts["duplicate"] += 1
                    print(f"[duplicate] {file} -> {skipped[file]}")
                    continue

                status, reasons = _review_markdown(text)

                counts[status] += 1
                detail = f" | {' / '.join(reasons)}" if reasons else ""
                print(f"[{status}] {file}{detail}")

            print("Tổng hợp")
            for status, count in sorted(counts.items()):
                print(f"  {status} = {count}")
            return []

        docs: list[Document] = []
        for file, text, doc_id, _ in sources:
            if file in skipped:
                logger.info(
                    "Skipping %s: duplicate_of resolves to %s.",
                    doc_id or file,
                    skipped[file],
                )
                continue
            if checked_only:
                status, reasons = _review_markdown(text)
                if status != "passed_checks":
                    logger.info("Skipping %s [%s]: %s", file, status, " / ".join(reasons))
                    continue
            docs.extend(self._split_text(text))
        logger.info(
            "Processed %d documents, skipped %d duplicates.",
            len(sources) - len(skipped),
            len(skipped),
        )
        return docs



class RecordItem:
    def __init__(self, data: ChunkRecord | None = None):
        self.data = data
        
    def tolist(self) -> str:
        "Return only page_content"
        return [self.data.page_content]
    
    def __getattr__(self, name):
        return self.data
    

class RecordList(list[RecordItem]):
    
    def tolist(self) -> list[str]:
        """Only take the page_content."""
        records = [rec.tolist()[0] for rec in self]
        return records
    
    def model_dump(self):
        records = [rec.model_dump for rec in self]
        return records

        

class Record:
    
    @staticmethod
    def build_chunk_records(docs: list[Document]) -> RecordList:
        logging.info("Starting to build ChunkRecord.")
        
        try:
            records = [ChunkRecord(**{**doc.metadata, 'page_content': doc.page_content}) for doc in docs]
            return RecordList([RecordItem(rec) for rec in records])
        except Exception as e:
            logging.exception(f'Failed at build DocRecord: {e}')
        
        return RecordList([RecordItem()])
