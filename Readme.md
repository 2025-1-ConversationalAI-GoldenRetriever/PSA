# Conversational Product Search Agent

본 프로젝트는 메타데이터와 리뷰 데이터를 결합한 대화형 상품 검색 시스템을 구현합니다. 사용자의 초기 질문을 기반으로, 에이전트가 적절한 질의로 변환하고 검색 결과를 바탕으로 반복적으로 질문을 생성하여 사용자 요구를 구체화하는 인터랙티브한 검색 환경을 제공합니다.

## Overview

### Workflow

| 단계               | 역할                                 | Input      | Output                          |
| ---------------- | ---------------------------------- | ---------- | ------------------------------- |
| **Generation 1** | 사용자 질의를 에이전트가 초깃값으로 변환             | 유저 → 에이전트  | 초기 질문 → **초기 쿼리**               |
| **Retrieval 1**  | 초기 쿼리로 상품 검색 수행                    | 에이전트 → 검색기 | 초기 쿼리 → **상품 관련 문서 10개**        |
| **Generation 2** | 검색 결과 기반으로 새로운 질문 생성               | 검색기 → 에이전트 | 상품 문서 → **새로운 질문**              |
| **User Prompt**  | 사용자로부터 응답 입력 받음                    | 에이전트 → 유저  | 질문 → **답변**                     |
| **Generation 3** | 응답과 대화 이력 기반 쿼리 재구성                | 유저 → 에이전트  | 질문 + 답변 + history → **재구성된 쿼리** |
| **Retrieval 2**  | 재구성된 쿼리로 다시 검색                     | 에이전트 → 검색기 | 재구성된 쿼리 → **상품 관련 문서 10개**      |
| **Generation 4** | 결과 및 이력을 기반으로 추가 질문 생성             | 검색기 → 에이전트 | 문서 + history → **새로운 질문**       |
| **반복**           | 4\~7단계를 2번 반복 수행하여 질의 정교화 및 검색 정확도 향상 |            |                                 |

> 마지막 iteration에서는 질문 생성을 생략하고, 관련 문서 4개를 요약하여 사용자에게 제공합니다.


## Dataset

The agent utilizes the **Amazon Reviews 2023** dataset from Hugging Face, specifically Toys_and_Games.

- **Dataset**: [McAuley-Lab/Amazon-Reviews-2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)
- **Subset**: `raw_meta_Toys_and_Games`, `raw_review_Toys_and_Games`


### Index Structure

- **ID**: `parent_asin`
- **Content**: Concatenation of `title`, `features`, `description` from metadata and `title`, `text` from review data.

## Retrieval Models

### 1. **BM25** (Lexical Retrieval)

* 키워드 중심의 전통적인 텍스트 일치 기반 검색
* `bm25s` 라이브러리를 통해 구현
* 초기 질의 혹은 재구성된 질의에 대해 빠르게 관련 문서를 찾아냄

### 2. **BAAI/bge-small-en-v1.5** (Dense Retrieval)

* Hugging Face의 [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) 모델 사용
* 질의와 문서를 저차원 벡터로 변환한 후, **FAISS**를 통해 유사도 기반 검색 수행
* 의미 기반의 유사도를 반영하여 키워드 일치만으로는 어려운 검색 결과를 보완

### 🔁 Hybrid Retrieval

* 두 방식의 결과를 결합하여, **정확성과 다양성**을 동시에 확보
* 최종 검색 결과는 다음과 같이 구성:

  * BM25 Top-K 문서
  * BGE 임베딩 Top-K 문서
  * 두 결과를 통합하거나 점수 기반으로 재정렬


## Usage

### Dependencies Installation

```bash
pip install -r requirements.txt
```

### Environment Setup

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

---

## 🧾 실행 방법

본 시스템은 두 가지 방식으로 실행할 수 있습니다:

### ▶️ 실사용자와의 대화 (Interactive 모드)

* 터미널에서 직접 사용자 입력을 받아 대화를 진행합니다.

```bash
python run_agent_v2_user.py
```
---

### 🧪 시뮬레이터 기반 평가 (Simulation 모드)

* LLM simulator가 자동 평가를 수행합니다.

```bash
python run_agent_v2_simulator.py
```
---
