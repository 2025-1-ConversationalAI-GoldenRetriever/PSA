import os
from pathlib import Path
from collections import defaultdict
from datasets import load_dataset
import bm25s
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from utils import *
from utils import _build_or_load_bm25_index
from user_simulator_hw3 import user_simulator


# -- Assumes the following functions are defined earlier in this module:
# _build_or_load_bm25_index, rewrite_query, reformulate_query, ask_disambiguation, bm25_search

# Simulation parameters
MAX_TURNS = 10
TOP_K = 100          # Initial pool size for asking questions
THRESHOLD = 1.0      # BM25 score threshold for including in recommendations
N_REC = 10            # Number of items to satisfy before switching to recommendation phase

# Simulator loop implementing ask/recommend logic

def run_simulator(sim: user_simulator):
    # Build or load BM25 index
    bm25_idx = _build_or_load_bm25_index()
    llm = sim.llm

    disrec = set()           # IDs the simulator dislikes
    rec_list: list[tuple[str, str]] = []  # (id, text)
    history: list[tuple[str, str]] = []   # (question, answer)
    action = 'ask'
    turn = 0

    # Initial user query from simulator
    raw_query = sim.initial_ambiguous_query()
    current_query = rewrite_query(llm, raw_query)

    while turn < MAX_TURNS:
        turn += 1
        if action == 'ask':
            # Retrieve top-K for question generation
            hits = bm25_search(current_query, bm25_idx, TOP_K)
            question = ask_disambiguation(llm, hits, history)
            print(f"Agent: {question}")

            answer = sim.answer_clarification_question(question)
            print(f"Simulator: {answer}")
            history.append((question, answer))

            # Reformulate query based on history
            current_query = reformulate_query(llm, history)

            # Full BM25 scoring to filter by threshold
            all_scores = bm25_search(current_query, bm25_idx, len(bm25_idx[0]))

            scores = [score for _, _, score in all_scores]
            min_score = min(scores)
            max_score = max(scores)

            def min_max_scale(score, min_s, max_s):
                if max_s == min_s:
                    return 0.0
                return (score - min_s) / (max_s - min_s)

            scaled_scores = [
                (pid, txt, min_max_scale(score, min_score, max_score)) 
                for pid, txt, score in all_scores
            ]

            rec_list = [(pid, txt) for pid, txt, score in scaled_scores if score > 0.7]
            print(f"Number of items after filtering: {len(rec_list)}")

            if len(rec_list) - len(disrec) > N_REC:
                rec_list.clear()
                action = 'ask'
            else:
                action = 'rec'

        else:  # action == 'rec'
            to_show = [(pid, txt) for pid, txt in rec_list if pid not in disrec]
            print("Agent recommendations:")
            for pid, txt in to_show:
                print(f"- {pid}: {txt.split('Descriptions: ')[0]}")

            selection = sim.choose_item([pid for pid, _ in to_show])
            print(f"Simulator selection: {selection}")

            if selection in {pid for pid, _ in to_show}:
                print(f"Simulator selected target: {selection}")
                break
            else:
                disrec.update({pid for pid, _ in to_show})
                rec_list.clear()
                action = 'ask'


    print("Session ended after {} turns.".format(turn))

    return turn



# 시뮬레이터 파일 경로
SIMULATOR_JSONL_PATH = "/Users/jinseok/Documents/PSA/sample_data/magazine_users.jsonl"

# LLM 세팅
llm = ChatOpenAI(model_name=MODEL_NAME, temperature=TEMPERATURE)

# 모든 시뮬레이터 수행
def run_all_simulators():
    with open(SIMULATOR_JSONL_PATH, "r") as f:
        all_turns = []
        for idx, line in enumerate(f, start=1):
            data = json.loads(line)
            parent_asin = data["parent_asin"]
            meta = data["metadata"]
            review = data["reviews"]

            print(f"\n=== Running simulator {idx}: {paren