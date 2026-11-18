"""RAG: 색인(문서 읽기 -> 조각내기 -> 임베딩 -> numpy 저장)과 검색(질문 -> 비슷한 조각).
사용: `python rag.py` = 색인 만들기 / `python rag.py 질문` = 검색 후 답변.
벡터DB·RAG 프레임워크는 쓰지 않는다."""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

ROOT = Path(__file__).parent  # rag.py가 있는 폴더 = 문서가 있는 폴더(손효민)
load_dotenv(ROOT / ".env")  # 환경변수는 .env에서 읽는다
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EMBEDDING_MODEL = os.environ["EMBEDDING_MODEL"]  # 예: gemini-embedding-2
EMBEDDING_DIM = int(os.environ["EMBEDDING_DIM"])  # 벡터 차원 (공식 권장값: 768/1536/3072)
MODEL_NAME = os.environ["MODEL_NAME"]  # 답변을 만드는 모델 (예: gemini-3.5-flash-lite)

CHUNK_SIZE = 700  # 조각 본문 최대 글자 수
CHUNK_OVERLAP = 100  # 앞 조각의 끝 글자를 다음 조각 앞에 겹쳐 붙이는 글자 수
BATCH_SIZE = 50  # 임베딩 API를 한 번 부를 때 보내는 조각 수
TOP_K = 8  # 검색할 때 가져올 조각 수 (두 문서 비교 질문의 정답 조각이 4~8위에 있어 늘림)
MAX_RETRY = 6  # 429가 나올 때 한 배치당 최대 재시도 횟수
INDEX_DIR = ROOT / "rag_index"  # 색인 저장 폴더

# 실습에 쓰기로 확정한 문서 10개 (다른 파일·폴더는 색인하지 않는다)
DOC_FILES = [
    "버틴집_기획서_v1.md", "대구_야간관광명소_정리.md", "동네가 먹여살린 가게_종합정리.md",
    "시장하시죠.md", "대구10미_가게이름_통합본_1차.md", "사이트_프롬프트_정리.md",
    "01_따로국밥_대구육개장_1차.xlsx", "대구_구군별_착한가격업소_현황.docx",
    "버틴집_발표_v2.pptx", "대구로페이_할인지원금_완판속도_정리.docx",
]

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"  # docx XML 이름공간
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"  # pptx XML 이름공간
client = genai.Client(api_key=GEMINI_API_KEY)


def text_of(node, ns: str) -> str:
    """XML 노드 안의 글자(<t>)를 모두 이어 붙인다."""
    return "".join(t.text or "" for t in node.iter(ns + "t"))


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    lines = []
    for el in body:  # 본문 순서대로: 문단은 한 줄, 표는 행마다 한 줄
        if el.tag == W + "p":
            lines.append(text_of(el, W))
        elif el.tag == W + "tbl":
            lines += [" | ".join(text_of(c, W) for c in row.findall(W + "tc"))
                      for row in el.iter(W + "tr")]
    return "\n".join(lines)


def read_pptx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        names.sort(key=lambda n: int(re.findall(r"\d+", n)[0]))  # 슬라이드 번호순
        slides = [ET.fromstring(z.read(n)) for n in names]
    return "\n".join(text_of(p, A) for s in slides for p in s.iter(A + "p"))


def read_xlsx(path: Path) -> str:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"[시트: {ws.title}]")
        lines += [" | ".join("" if v is None else str(v) for v in row).strip(" |")
                  for row in ws.iter_rows(values_only=True)]
    return "\n".join(lines)


def read_document(path: Path) -> str:
    """확장자에 맞는 방법으로 문서의 글자를 읽는다."""
    readers = {".docx": read_docx, ".pptx": read_pptx, ".xlsx": read_xlsx}
    reader = readers.get(path.suffix.lower())
    return reader(path) if reader else path.read_text(encoding="utf-8")


def expand_long_lines(lines: list, size: int) -> list:
    """size보다 긴 줄은 size 글자씩 잘라 여러 줄로 만든다."""
    return [line[i:i + size] for line in lines for i in range(0, len(line), size)]


def split_text(text: str, size: int, overlap: int) -> list:
    """줄 단위로 size까지 모아 조각을 만들고, 앞 조각의 끝 overlap글자를 다음 조각 앞에 붙인다."""
    lines = expand_long_lines([l.strip() for l in text.splitlines() if l.strip()], size)
    chunks, cur = [], ""
    for line in lines:
        if cur and len(cur) + len(line) + 1 > size:  # 이 줄을 넣으면 size 초과 -> 조각 마감
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    chunks.append(cur)
    # 겹침: 둘째 조각부터 앞 조각 끝 글자를 앞에 붙인다
    return chunks[:1] + [prev[-overlap:] + "\n" + c for prev, c in zip(chunks, chunks[1:])]


def build_chunks() -> list:
    """문서 10개를 조각내고, 조각마다 출처(폴더명/파일명)와 번호를 붙인다."""
    chunks = []
    for name in DOC_FILES:
        pieces = split_text(read_document(ROOT / name), CHUNK_SIZE, CHUNK_OVERLAP)
        chunks += [{"source": f"{ROOT.name}/{name}", "chunk_id": i, "text": t}
                   for i, t in enumerate(pieces)]
    return chunks


def embed_batch(texts: list) -> list:
    # gemini-embedding-2는 입력마다 별도 Content로 감싸야 조각별 벡터가 나온다(공식 문서)
    contents = [types.Content(parts=[types.Part.from_text(text=t)]) for t in texts]
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
    result = client.models.embed_content(model=EMBEDDING_MODEL, contents=contents, config=config)
    if len(result.embeddings) != len(texts):  # 조각 수와 벡터 수가 다르면 중단
        raise ValueError(f"벡터 {len(result.embeddings)}개 != 조각 {len(texts)}개")
    return [e.values for e in result.embeddings]


def with_retry(fn, *args):
    """API 호출 fn이 429(분당 한도 초과)이면 오류가 알려 준 시간만큼 기다렸다가 다시 부른다."""
    for attempt in range(MAX_RETRY + 1):
        try:
            return fn(*args)
        except errors.ClientError as e:
            if e.code != 429 or attempt == MAX_RETRY:  # 429가 아니거나 재시도를 다 썼으면 그대로 실패
                raise
            found = re.search(r"retry in ([\d.]+)s", str(e))  # 메시지의 '13.3s 뒤 재시도' 읽기
            wait = float(found.group(1)) + 1 if found else 30
            print(f"429: {wait:.0f}초 기다린 뒤 재시도 ({attempt + 1}/{MAX_RETRY})", flush=True)
            time.sleep(wait)


def embed_all(texts: list) -> np.ndarray:
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        vectors += with_retry(embed_batch, texts[i:i + BATCH_SIZE])
    matrix = np.array(vectors, dtype=np.float32)
    # 길이를 1로 맞춰 두면 내적이 곧 코사인 유사도가 된다
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def doc_input(chunk: dict) -> str:
    """문서용 임베딩 입력. 공식 형식: title: {제목} | text: {내용}"""
    return f"title: {Path(chunk['source']).stem} | text: {chunk['text']}"


def save_index(chunks: list, matrix: np.ndarray) -> None:
    INDEX_DIR.mkdir(exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", matrix)  # 벡터 (조각 수 x 차원)
    (INDEX_DIR / "chunks.json").write_text(  # 조각 글과 출처 (벡터와 같은 순서)
        json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")


def print_summary(chunks: list, matrix: np.ndarray) -> None:
    print(f"조각 {len(chunks)}개 / 벡터 {matrix.shape} / 모델 {EMBEDDING_MODEL}")
    lengths = [len(c["text"]) for c in chunks]
    print(f"조각 길이: 최소 {min(lengths)} / 평균 {sum(lengths) // len(lengths)} / 최대 {max(lengths)}")
    for name in DOC_FILES:
        n = sum(c["source"].endswith("/" + name) for c in chunks)
        print(f"  {n:3d}개  {name}")
    print("저장:", INDEX_DIR)


def load_index() -> tuple:
    """저장해 둔 조각과 벡터를 읽는다 (같은 순서)."""
    matrix = np.load(INDEX_DIR / "embeddings.npy")
    chunks = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
    return chunks, matrix


def query_input(query: str) -> str:
    """질문용 임베딩 입력. 공식 형식: task: search result | query: {질문}"""
    return f"task: search result | query: {query}"


def search(query: str, chunks: list, matrix: np.ndarray, top_k: int = TOP_K) -> list:
    """질문과 가장 비슷한 조각 top_k개를 (점수, 조각) 목록으로 돌려준다."""
    q = embed_all([query_input(query)])[0]
    scores = matrix @ q  # 길이가 1인 벡터끼리의 내적 = 코사인 유사도
    best = np.argsort(-scores)[:top_k]  # 점수가 높은 순서
    return [(float(scores[i]), chunks[i]) for i in best]


def print_results(query: str, results: list) -> None:
    print(f"질문: {query}")
    for rank, (score, c) in enumerate(results, 1):
        preview = c["text"].replace("\n", " ")[:70]
        print(f"  {rank}. {score:.3f}  {c['source']} #{c['chunk_id']}  {preview}")


ANSWER_PROMPT = """너는 문서 질의응답 도우미다. 아래 [자료]에 적힌 내용만 근거로 한국어로 답한다.
- 자료에 답이 전혀 없으면 지어내지 말고 "문서에서 찾을 수 없습니다"라고 답한다.
- 질문의 일부만 자료에 있으면, 있는 부분(숫자·사실)을 반드시 먼저 답한다. 이유를 묻는데 이유가 자료에 없으면 숫자와 사실은 그대로 말하고 "이유는 문서에 없다"고만 덧붙인다. 자료에 숫자가 있는데도 "찾을 수 없다"고만 답하지 않는다.
- 숫자는 자료에 적힌 그대로 쓴다. 자료에 없는 이유나 원인은 덧붙이지 않는다. 추정이라고 적힌 내용은 추정이라고 밝힌다.
- 서로 다른 문서의 값이 다르면 각 값을 출처 파일명과 함께 말하고, 두 값의 차이(뺄셈)는 계산해서 알려 준다. 자료에 없는 합계·평균 같은 계산값은 직접 만들지 않는다. 한쪽 값을 자료에서 찾지 못하면 찾은 값만 말하고 나머지는 "문서에서 찾지 못했다"고 한다.
- 예시: 질문이 "A문서와 B문서의 가게 수가 다른 이유는?"인데 자료에 A문서 100곳, B문서 80곳만 있고 이유가 없으면, "A문서는 100곳, B문서는 80곳입니다. 두 수가 다른 이유는 문서에 없습니다."라고 답한다.
- 답은 짧고 분명하게 쓴다."""


def build_context(results: list) -> str:
    """검색된 조각을 출처와 함께 모델에게 줄 [자료] 문자열로 만든다."""
    return "\n\n".join(f"[출처: {c['source']} #{c['chunk_id']}]\n{c['text']}" for _, c in results)


def generate(query: str, results: list) -> str:
    """검색된 조각만 근거로 답을 만든다 (RAG의 생성 단계)."""
    prompt = f"[자료]\n{build_context(results)}\n\n[질문]\n{query}"
    config = types.GenerateContentConfig(system_instruction=ANSWER_PROMPT)
    response = with_retry(lambda: client.models.generate_content(
        model=MODEL_NAME, contents=prompt, config=config))
    return response.text


def answer(query: str, chunks: list, matrix: np.ndarray) -> tuple:
    """질문 하나에 대해 검색 -> 생성까지 하고 (답변, 검색 결과)를 돌려준다."""
    results = search(query, chunks, matrix)
    return generate(query, results), results


def main() -> None:
    if len(sys.argv) > 1:  # 질문을 주면 검색+답변, 안 주면 색인 만들기
        query = " ".join(sys.argv[1:])
        text, results = answer(query, *load_index())
        print_results(query, results)
        print("\n답변:\n" + text)
        return
    chunks = build_chunks()
    matrix = embed_all([doc_input(c) for c in chunks])
    save_index(chunks, matrix)
    print_summary(chunks, matrix)


if __name__ == "__main__":
    main()
