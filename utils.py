from __future__ import annotations


import json
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv


import numpy as np
import faiss
import bm25s
from datasets import load_dataset
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from sentence_transformers import SentenceTransformer
from Stemmer import Stemmer
from tqdm import tqdm
import warnings
import os
from books_product_info import BooksProductInfoExtractor

os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings('ignore')
from datasets import load_dataset
from collections import defaultdict

load_dotenv()

MODEL_NAME = "gpt-4.1-mini"
TEMPERATURE = 0.2
# INDEX_DIR = Path("cellphones_bm25s_index")
INDEX_DIR = Path("magazine_bm25s_index")
VEC_DIR = Path("magazine_faiss")
TOP_KS = [20, 20, 20, 4]        # pool sizes per round
MAX_PRODUCTS = None                # None → full split; set small for demo
SEM_K_FACTOR = 2                  # retrieve k*factor from each modality
HYBRID_WEIGHT = 0.5               # 0.5 lexical + 0.5 semantic
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


def _iter_products(limit: int | None = None):
    # 1) 메타 정보
    meta_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        'raw_meta_Magazine_Subscriptions',
        split="full",
        trust_remote_code=True,
    )

    # 2) 리뷰 정보 →  parent_asin ➜ [review dicts]
    review_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        'raw_review_Magazine_Subscriptions',
        split="full",
        trust_remote_code=True,
    )

    reviews_by_pid: dict[str, list[dict]] = defaultdict(list)
    for row in review_ds:
        pid = row["parent_asin"]
        reviews_by_pid[pid].append(row)

    # 3) 메타 + 리뷰를 합쳐서 ProductInfo로 변환
    extractor = BooksProductInfoExtractor(llm=None)  # LLM 연결 시 인자 변경
    for i, row in enumerate(meta_ds):
        if limit and i >= limit:
            break
        pid = row["parent_asin"]
        product_info = extractor.extract_product_info(
            pid,
            row,
            reviews_by_pid.get(pid, [])
        )
        doc = product_info.create_enhanced_book_document()
        yield doc  # {"id": ..., "text": ..., "hierarchical": ..., ...}


# ──────────────────────────────────────────────────
# Index build / load
# ──────────────────────────────────────────────────

def _build_or_load_bm25_index(limit: int | None = None):
    """Load cached BM25s index or build it if absent."""
    stemmer = Stemmer("english")
    tokenizer = bm25s.tokenization.Tokenizer(stemmer=stemmer, stopwords='en')
    if INDEX_DIR.exists():
        print("[+] Loading cached BM25s index…")
        retriever = bm25s.BM25.load(INDEX_DIR, mmap=True, load_corpus=True)
        tokenizer.load_vocab(INDEX_DIR)
        tokenizer.load_stopwords(INDEX_DIR)
        return retriever.corpus, tokenizer, retriever

    print("[+] Building BM25s index (first run — please wait)…")
    corpus = list(_iter_products(limit))
    texts = [d["text"] for d in corpus]

    tokens = tokenizer.tokenize(texts)
    retriever = bm25s.BM25(corpus=corpus, backend="numba")
    retriever.index(tokens)
    retriever.vocab_dict = {str(k): v for k, v in retriever.vocab_dict.items()}

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    retriever.save(INDEX_DIR, corpus=corpus)
    tokenizer.save_vocab(INDEX_DIR)
    tokenizer.save_stopwords(INDEX_DIR)
    print(f"[✓] Saved index ({len(corpus):,} docs) → {INDEX_DIR}")
    return corpus, tokenizer, retriever


def _build_or_load_vector_index(corpus: List[Dict[str, str]]):
    """Load or build FAISS index with BGE embeddings."""
    if (VEC_DIR / "index.faiss").exists():
        print("[+] Loading cached FAISS vector index…")
        index = faiss.read_index(str(VEC_DIR / "index.faiss"))
        id_map = json.loads((VEC_DIR / "id_map.json").read_text())
        model = SentenceTransformer(EMBED_MODEL_NAME)
        return index, id_map, model

    print("[+] Building FAISS vector index (first run — please wait)…")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    model.max_seq_length = 512
    texts = [d["text"] for d in corpus]

    # Embed in batches to avoid OOM
    embeddings = []
    for i in tqdm(range(0, len(texts), 256), desc="Embedding"):
        batch_emb = model.encode(texts[i:i+256], show_progress_bar=False, normalize_embeddings=True)
        embeddings.append(batch_emb)
    embeddings = np.vstack(embeddings).astype('float32')

    # Build FAISS index (inner product on unit vectors == cosine sim)
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(embeddings)

    # Persist
    VEC_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(VEC_DIR / "index.faiss"))
    (VEC_DIR / "id_map.json").write_text(json.dumps([d["id"] for d in corpus]))
    print(f"[✓] Saved FAISS index ({len(corpus):,} vectors) → {VEC_DIR}")
    return index, [d["id"] for d in corpus], model

def bm25_search(query: str, idx_tuple, k: int) -> List[Tuple[str, str, float]]:
    _, tok, ret = idx_tuple
    q_tokens = tok.tokenize([query], update_vocab=False)
    docs_mat, scores_mat = ret.retrieve(q_tokens, k=k)
    docs, scores = docs_mat[0], scores_mat[0]
    return [(d["id"], d["text"], float(s)) for d, s in zip(docs, scores)]


def semantic_search(query: str, vec_tuple, k: int) -> List[Tuple[str, float]]:
    index, id_map, model = vec_tuple
    q_emb = model.encode([query], normalize_embeddings=True)[0].astype('float32')
    scores, idxs = index.search(q_emb[None, :], k)
    return [(id_map[int(i)], float(s)) for i, s in zip(idxs[0], scores[0])]


def hybrid_search(query: str, idx_tuple, vec_tuple, k: int, w: float = HYBRID_WEIGHT):
    # Retrieve from each modality
    bm25_hits = bm25_search(query, idx_tuple, k=k*SEM_K_FACTOR)
    sem_hits = semantic_search(query, vec_tuple, k=k*SEM_K_FACTOR)

    # Build score dicts
    bm25_dict = {pid: s for pid, _, s in bm25_hits}
    sem_dict = {pid: s for pid, s in sem_hits}

    # Normalise scores [0,1] within each modality
    if bm25_dict:
        bm_min, bm_max = min(bm25_dict.values()), max(bm25_dict.values())
    else:
        bm_min = bm_max = 0
    if sem_dict:
        sm_min, sm_max = min(sem_dict.values()), max(sem_dict.values())
    else:
        sm_min = sm_max = 0

    def norm(val, vmin, vmax):
        return 0.0 if vmax == vmin else (val - vmin) / (vmax - vmin)

    # Union of document ids
    docs_all = set(bm25_dict) | set(sem_dict)

    # Compute hybrid score
    scored_docs = []
    for pid in docs_all:
        bm = norm(bm25_dict.get(pid, bm_min), bm_min, bm_max)
        sm = norm(sem_dict.get(pid, sm_min), sm_min, sm_max)
        hybrid = w * bm + (1 - w) * sm
        scored_docs.append((pid, hybrid))

    # Sort by hybrid score desc
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    # Retrieve full text for top‑k
    corpus, _, _ = idx_tuple
    id_to_text = {d["id"]: d["text"] for d in corpus}
    topk = [(
        pid,
        id_to_text.get(pid, ""),
        score,
    ) for pid, score in scored_docs[:k]]
    return topk


# ──────────────────────────────────────────────────
# ❶ 초기 질문 ‑> 검색용 쿼리로 ‘재작성’
# ──────────────────────────────────────────────────
REWRITE_PROMPT = PromptTemplate(
    input_variables=["user_input"],
    template=(
        "You are an expert e‑commerce search assistant.\n\n"
        "Rewrite the user's input as a short, precise search query.\n"
        "If the input is already an optimal search query, return it unchanged.\n\n"
        "User: {user_input}\n"
        "Search‑query:"
    )
)
def rewrite_query(llm: ChatOpenAI, user_input: str) -> str:
    return llm.invoke(REWRITE_PROMPT.format(user_input=user_input)).content.strip()


# ──────────────────────────────────────────────────
# ❷ 대화 이력 + 새 답변 -> ‘재구성된 쿼리’ 생성
# ──────────────────────────────────────────────────
REFORM_PROMPT = PromptTemplate(
    input_variables=["history"],
    template=(
        "You are refining a product‑search query.\n\n"
        "Conversation so far:\n{history}\n\n"
        "Compose ONE refined search query that captures all constraints implicit "
        "or explicit in the conversation. Return ONLY the query."
    )
)
def reformulate_query(llm: ChatOpenAI, turns: list[tuple[str, str]]) -> str:
    """turns = [(question, answer), ...]"""
    history_txt = "\n".join(f"Q: {q}\nA: {a}" for q, a in turns)
    return llm.invoke(REFORM_PROMPT.format(history=history_txt)).content.strip()


# ──────────────────────────────────────────────────
# ❸ 마지막 iteration: 문서 4개 요약
# ──────────────────────────────────────────────────
SUMMARY_PROMPT = PromptTemplate(
    input_variables=["docs"],
    template=(
        "Summarise the following 4 product descriptions in bullet points (≤ 40 words each).\n\n"
        "{docs}\n\n"
        "Start with item id for each description."
        "Return exactly 4 bullet points."
    )
)
def summarise_docs(llm: ChatOpenAI, docs: list[tuple[str, str]]) -> str:
    flat = "\n\n".join(f"[{pid}]\n{text}" for pid, text in docs)
    return llm.invoke(SUMMARY_PROMPT.format(docs=flat)).content.strip()


QUESTION_PROMPT = PromptTemplate(
    input_variables=["items", "context"],
    template=(
        # 역할
        "You are a helpful product-search assistant.\n\n"
        # 컨텍스트 설명
        "The products listed below were retrieved after considering the entire prior conversation with the user.\n\n"
        # 상품 목록
        "Products (id · snippet):\n{items}\n\n"
        # 대화 맥락
        "Conversation context:\n{context}\n\n"
        # 요청
        "Using BOTH the conversation context and the product list, do the following:\n"
        "1. Ask **one** concise follow-up question that will help the user narrow down their search significantly.\n"
        "   • The question should distinguish between the remaining products effectively.\n"
        "   • The question should not repeat or be too similar to previous questions.\n"
        "   • Focus on the most important differentiating factors among the products.\n"
        "   • Do **not** recommend any specific item.\n\n"
        "2. Provide a list of **meaningful and mutually exclusive answer choices**, up to **4 choices maximum**.\n"
        "   • Begin each choice with a number (1. 2. 3. 4.).\n"
        "   • The options should reflect significant differences that help narrow down the search.\n"
        "   • Make choices broad enough to be useful but specific enough to filter products.\n"
        "   • Do not include redundant or overlapping options.\n\n"
        "Format your output as follows:\n"
        "Question: <your generated question here>\n"
        "1. <first option>\n"
        "2. <second option>\n"
        "3. <third option>\n"
        "4. <fourth option>\n"
        "(Only include as many as are appropriate; fewer than 4 is fine)"
    ),
)

def ask_disambiguation(llm: ChatOpenAI, docs, qa_turns):
    # build product snippets
    snippets = []
    for pid, text, _ in docs:
        # head = " ".join(text.split()[:20]) + (" …" if len(text.split()) > 20 else "")
        head = text
        snippets.append(f"{pid} · {head}")

    context =  "None so far." if not qa_turns else "\n".join(f"Q: {turn[0]} A: {turn[1]}" for turn in qa_turns)
    # history = "None so far." if not prev_qs else "\n".join(f"- {q}" for q in prev_qs)
    prompt = QUESTION_PROMPT.format(items="\n".join(snippets), context=context)
    return llm.invoke(prompt).content.strip()


#### main loop



def conversational_search():
    # ㊀ 인덱스 / LLM 초기화
    bm25_idx = _build_or_load_bm25_index(MAX_PRODUCTS)
    vec_idx  = _build_or_load_vector_index(bm25_idx[0])
    llm      = ChatOpenAI(model_name=MODEL_NAME,
                          temperature=TEMPERATURE,
                          streaming=True)

    print("=== Hybrid Conversational Product‑Search ===")
    raw_input = input("You: ").strip()
    if not raw_input or raw_input == "/exit":
        return

    # ㊁ Generation‑1: 초기 쿼리 재작성
    search_query = rewrite_query(llm, raw_input)
    print(f"[ rewritten‑query ] → {search_query}")

    # 대화 이력
    qa_turns: list[tuple[str, str]] = []
    # prev_questions: list[str] = []

    # ㊂‑㊇ 반복
    for round_idx, k in enumerate(TOP_KS, start=1):

        # Retrieval
        docs_k = hybrid_search(search_query, bm25_idx, vec_idx, k)
        # Generation: Clarifying question
        question = ask_disambiguation(llm, docs_k, qa_turns)
        # prev_questions.append(question)

        if question == "[END]" or round_idx == len(TOP_KS):
            #   ↳ 마지막 iteration: 문서 4개 요약 후 종료
            final_hits = hybrid_search(search_query, bm25_idx, vec_idx, 4)

            pids = [pid for pid, _, _ in final_hits]   # keep order if you like
            # images_by_pid = fetch_images_for_pids(pids)

            summary = summarise_docs(llm, [(pid, txt) for pid, txt, _ in final_hits])
            print("\n🔎  Top‑4 summary\n" + summary)

            # print("\n🖼  Image URLs for the Top‑4 products")
            # print(str(images_by_pid))
            # for pid in pids:
            #     print(images_by_pid)
            #     # print(f"{pid}: {images_by_pid.get(pid, [])[:3]}")   # first 3 URLs (or tweak)

            return

        # User prompt ↔ answer 수집
        print(f"Agent: {question}")
        answer = input("You: ").strip()

        qa_turns.append((question, answer))
        # Generation: 대화 이력 기반 쿼리 재구성
        search_query = reformulate_query(llm, qa_turns)
        # print(f"[ refined‑query ] → {search_query}\n")
