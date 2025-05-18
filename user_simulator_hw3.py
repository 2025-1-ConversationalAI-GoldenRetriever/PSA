import random
import json
from typing import Dict, List, Any
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
import pandas as pd

class user_simulator:
    def __init__(self, parent_asin, meta, review, llm):
        self.parent_asin = parent_asin
        self.meta = meta
        self.review = review
        self.llm = llm
        self.retrieval_result = []
        self.retrieval_reciprocal_rank = []

    def initial_ambiguous_query(self):
        """
        generates an ambiguous query, which contains partial information about the wanted item
        """
        # in this prototype, we simply invoke an llm to generate an ambiguous initial query
        ambiguous_query_prompt = PromptTemplate(
            input_variables=["meta_title","meta_features","meta_description","review_title" 'review_text'],
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
        # generate the query
        # ambiguous_query = ambiguous_query_prompt.format(meta=self.meta, review=self.review)

        chain = ambiguous_query_prompt | self.llm  # chain = Runnable
        response = chain.invoke({
            "meta_title": self.meta['title'],
            "meta_features": self.meta['features'],
            "meta_description": self.meta['description'],
            "review_title": self.review['title'],
            "review_text": self.review['text'],
        })

        return response.content  # LLM 응답 텍스트만 반환

        # return ambiguous_query

    def answer_clarification_question(self, question_str):
        """
        generates an answer to a clarification question, which is asked by the system
        """
        answer_clarification_question_prompt = PromptTemplate(
            input_variables=["meta_title","meta_features","meta_description","review_title" 'review_text', "question"],
            template=(
                "You are a user who is looking for a product on an e-commerce website such as Amazon. "
                "You had already made an initial query, which only contains partial information about the wanted item. "
                "The system is asking you a clarification question to help you find the product. "
                "Your job is to answer the question to help the system better understand your needs. "
                "You are not allowed to return the full name of the product, since we're now simulating a real user query scenario. "
                "Choose one of the following options from the question"
                "The question is: {question}. "
                "you may use the product title and some features or reviews(if any) to answer the question"
                "The product title is {meta_title} and the features are {meta_features} and {meta_description}. "
                "The product review title is {review_title} and review text is {review_text}. "
                "Please return the option number without any additional text or explanation. "
            ),
        )
        # answer = answer_clarification_question_prompt.format(
        #     meta=self.meta, review=self.review, question=question_str
        # )


        chain = answer_clarification_question_prompt | self.llm  # chain = Runnable
        response = chain.invoke({
            "meta_title": self.meta['title'],
            "meta_features": self.meta['features'],
            "meta_description": self.meta['description'],
            "review_title": self.review['title'],
            "review_text": self.review['text'],
            "question": question_str
        })

        return response.content  # LLM 응답 텍스트만 반환
        # return answer
    
    def choose_item(self, rec_str):
        if self.parent_asin in rec_str:
            return self.parent_asin
        else:
            return 'none'

