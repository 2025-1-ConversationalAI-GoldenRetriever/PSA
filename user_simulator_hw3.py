import random
import json
from typing import Dict, List, Any
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
import pandas as pd
from books_user_profile import BooksUserProfileGenerator

# Simulator file path
SIMULATOR_JSONL_PATH = "./sample_data/books_users.jsonl"

class user_simulator:
    def __init__(self, parent_asin, meta, review, llm):
        self.parent_asin = parent_asin
        self.meta = meta
        self.review = review
        self.llm = llm
        self.retrieval_result: list[int] = [] 
        self.retrieval_reciprocal_rank: list[float] = []
        # UserProfile 생성
        profile_gen = BooksUserProfileGenerator()
        self.user_profile = profile_gen.generate_from_product_info(meta)

    def initial_ambiguous_query(self):
        # 프로필 기반 쿼리 생성 (fallback: 기존 LLM 방식)
        if self.user_profile.preferred_genres and self.user_profile.reading_purposes:
            if self.user_profile.interaction_style == "brief":
                return f"{self.user_profile.preferred_genres[0]} book"
            else:
                return f"good {self.user_profile.preferred_genres[0]} for {self.user_profile.reading_purposes[0]}"
        # fallback: 기존 LLM 방식
        ambiguous_query_prompt = PromptTemplate(
            input_variables=["meta_title", "meta_features", "meta_description", "review_title", "review_text"],
            template=(
                "You are a user who is looking for a product on an e-commerce website such as Amazon. "
                "You probably know what you want, but you are not sure about the exact name or description. "
                "Although you are given the full name of the product, you cannot return it as the query. "
                "Your job is to generate a query that is still ambiguous, but contains key partial information about the wanted item. "
                "This resembles a real user query that is not too specific and does not contain the full name of the product. "
                "For example, if the product is a 'Samsung Galaxy S21 silver smartphone with 128GB storage', "
                "you may return 'Galaxy S21' or 'Samsung smartphone' for example. "
                "you may use the product title and some features or reviews(if any) to generate the query, which is at most two to five words. "
                "The product title is {meta_title} and the features are {meta_features} and {meta_description}. "
                "The product review title is {review_title} and review text is {review_text}. "
                "Please return the query in a single line without any additional text or explanation. "
                "The query should be a short phrase(2-5 words) and should not contain punctuation or special characters. "
            ),
        )
        chain = ambiguous_query_prompt | self.llm
        response = chain.invoke({
            "meta_title": self.meta['title'],
            "meta_features": self.meta['features'],
            "meta_description": self.meta['description'],
            "review_title": self.review['title'],
            "review_text": self.review['text'],
        })
        return response.content

    def answer_clarification_question(self, question_str):
        # 프로필 기반 답변 (fallback: 기존 LLM 방식)
        # 옵션 추출 (간단히 숫자 1~4 또는 텍스트 옵션 추출)
        import re
        options = re.findall(r'\d+\.\s*([^\n]+)', question_str)
        if not options:
            # fallback: 기존 LLM 방식
            answer_clarification_question_prompt = PromptTemplate(
                input_variables=["meta_title", "meta_features", "meta_description", "review_title", "review_text", "question"],
                template=(
                    "You are a user who is looking for a product on an e-commerce website such as Amazon. "
                    "You had already made an initial query, which only contains partial information about the wanted item. "
                    "The system is asking you a clarification question to help you find the product. "
                    "Your job is to answer the question to help the system better understand your needs. "
                    "You are not allowed to return the full name of the product, since we're now simulating a real user query scenario. "
                    "Look at the question carefully and choose the most appropriate option number that best matches your target product.\n"
                    "The question is: {question}\n"
                    "You may use the product title and some features or reviews(if any) to answer the question.\n"
                    "The product title is {meta_title} and the features are {meta_features} and {meta_description}. "
                    "The product review title is {review_title} and review text is {review_text}. "
                    "Please return ONLY the option number (1, 2, 3, or 4) without any additional text or explanation. "
                ),
            )
            chain = answer_clarification_question_prompt | self.llm
            response = chain.invoke({
                "meta_title": self.meta['title'],
                "meta_features": self.meta['features'],
                "meta_description": self.meta['description'],
                "review_title": self.review['title'],
                "review_text": self.review['text'],
                "question": question_str
            })
            return response.content
        # 프로필 기반 응답
        return self.user_profile.answer_based_on_profile(question_str, options)

    def choose_item(self, rec_str):
        # 프로필 기반 선택 (fallback: 기존 방식)
        if isinstance(rec_str, list):
            # 추천 리스트에서 선호 장르/저자/테마 우선 선택
            for pid in rec_str:
                if any(g in pid for g in getattr(self.user_profile, 'preferred_genres', [])):
                    return pid
            # 없으면 첫 번째
            return rec_str[0] if rec_str else 'none'
        if self.parent_asin in rec_str:
            return self.parent_asin
        else:
            return 'none'

