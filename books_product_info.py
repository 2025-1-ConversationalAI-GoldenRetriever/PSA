from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import json

@dataclass
class SeriesInfo:
    series_name: str
    position_in_series: int
    total_books_in_series: int
    related_books: List[str] = field(default_factory=list)  # ASINs

@dataclass
class BooksProductInfo:
    """구조화된 Books Product 정보 - 고도화 버전"""
    parent_asin: str
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    publication_year: Optional[int] = None
    pages: Optional[int] = None
    isbn: Optional[str] = None
    language: str = "English"
    image_url: Optional[str] = None
    average_rating: Optional[float] = None
    rating_count: Optional[int] = None
    price: Optional[float] = None
    categories: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    writing_style: Optional[str] = None
    complexity: Optional[str] = None
    target_audience: List[str] = field(default_factory=list)
    book_type: Optional[str] = None
    series_info: Optional[SeriesInfo] = None
    awards: List[str] = field(default_factory=list)
    description: Optional[str] = None
    liked_aspects: List[str] = field(default_factory=list)
    disliked_aspects: List[str] = field(default_factory=list)
    reading_experience_summary: Optional[str] = None
    comparison_mentions: Dict[str, List[str]] = field(default_factory=dict)  # 구조화
    use_cases: List[str] = field(default_factory=list)
    searchable_components: Dict[str, Any] = field(default_factory=dict)
    # 검색 최적화 필드
    search_boost_terms: List[str] = field(default_factory=list)
    negative_signals: List[str] = field(default_factory=list)

    def create_enhanced_book_document(self) -> Dict[str, Any]:
        primary_text = f"{self.title or ''} {' '.join(self.authors)}"
        secondary_text = f"{' '.join(self.genres)} {' '.join(self.themes)}"
        tertiary_text = f"{' '.join(self.target_audience)} {self.complexity or ''}"
        legacy_text_parts = [
            f"Title: {self.title}" if self.title else "",
            f"Authors: {', '.join(self.authors)}" if self.authors else "",
            f"Categories: {' '.join(self.categories)}" if self.categories else "",
            f"Genres: {' '.join(self.genres)}" if self.genres else "",
            f"Description: {self.description}" if self.description else "",
            f"Themes: {' '.join(self.themes)}" if self.themes else ""
        ]
        legacy_text = " ".join(filter(None, legacy_text_parts))
        return {
            "id": self.parent_asin,
            "text": legacy_text,
            "hierarchical": {
                "primary": primary_text,
                "secondary": secondary_text,
                "tertiary": tertiary_text
            },
            "structured": {
                "title": self.title,
                "authors": self.authors,
                "genres": self.genres,
                "themes": self.themes,
                "complexity": self.complexity,
                "target_audience": self.target_audience
            },
            "search_boost_terms": self.search_boost_terms,
            "negative_signals": self.negative_signals
        }

    def calculate_search_weights(self, query_context: str) -> Dict[str, float]:
        weights = {
            "title": 1.0,
            "authors": 0.8,
            "genres": 0.6,
            "themes": 0.5
        }
        if "by" in query_context or "author" in query_context:
            weights["authors"] = 1.2
        return weights

    def calculate_quality_score(self) -> Dict[str, float]:
        total = len(self.liked_aspects) + len(self.disliked_aspects)
        positive_ratio = len(self.liked_aspects) / total if total > 0 else 0.5
        confidence = (self.rating_count or 0) / 100
        # 예시: 일관성은 단순히 liked/disliked 분포로 대체
        consistency = 1.0 - abs(len(self.liked_aspects) - len(self.disliked_aspects)) / (total + 1)
        return {
            "overall_quality": positive_ratio,
            "confidence": confidence,
            "consistency": consistency
        }

class BooksProductInfoExtractor:
    """개선된 Books 정보 추출기"""
    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm
        self._genre_cache = {}
        self._theme_cache = {}

    def extract_product_info(self, parent_asin: str, raw_meta_data: Dict[str, Any], raw_review_data: List[Dict[str, Any]]) -> BooksProductInfo:
        product_info = BooksProductInfo(parent_asin=parent_asin)
        try:
            self._extract_basic_info_safe(product_info, raw_meta_data)
            self._extract_content_features_safe(product_info, raw_meta_data, raw_review_data)
            self._extract_user_insights_safe(product_info, raw_review_data)
            product_info.searchable_components = product_info.create_enhanced_book_document()
        except Exception as e:
            print(f"Error extracting product info for {parent_asin}: {e}")
            if not product_info.searchable_components:
                product_info.searchable_components = {"id": parent_asin, "text": ""}
        return product_info

    def _extract_basic_info_safe(self, product_info: BooksProductInfo, raw_meta: Dict):
        try:
            product_info.title = raw_meta.get("title", "").strip() or None
            product_info.authors = self._parse_author_from_str(raw_meta.get("author"))
            categories = raw_meta.get("categories", raw_meta.get("category", []))
            if isinstance(categories, str):
                categories = [categories]
            product_info.categories = [cat.strip() for cat in categories if isinstance(cat, str) and cat.strip()]
            desc = raw_meta.get("description", [])
            if isinstance(desc, list):
                product_info.description = " ".join(filter(None, desc)).strip() or None
            elif isinstance(desc, str):
                product_info.description = desc.strip() or None
            try:
                if raw_meta.get("average_rating"):
                    product_info.average_rating = float(raw_meta["average_rating"])
            except (ValueError, TypeError):
                pass
            try:
                if raw_meta.get("rating_number"):
                    product_info.rating_count = int(raw_meta["rating_number"])
            except (ValueError, TypeError):
                pass
            self._parse_price_safe(product_info, raw_meta.get("price"))
        except Exception as e:
            print(f"Error in basic info extraction: {e}")

    def _parse_author_from_str(self, author_data: Any) -> List[str]:
        if not author_data:
            return []
        authors = []
        if isinstance(author_data, str):
            try:
                import json
                json_data = json.loads(author_data)
                if isinstance(json_data, list):
                    authors = [str(a).strip() for a in json_data if str(a).strip()]
                elif isinstance(json_data, dict):
                    authors = [str(v).strip() for v in json_data.values() if str(v).strip()]
                else:
                    authors = [author_data.strip()]
            except Exception:
                authors = [author_data.strip()]
        elif isinstance(author_data, list):
            authors = [str(a).strip() for a in author_data if str(a).strip()]
        return [author for author in authors if len(author) > 1]

    def _parse_price_safe(self, product_info: BooksProductInfo, price_raw):
        if not price_raw:
            return
        try:
            import re
            price_str = str(price_raw).lower()
            price_match = re.search(r'(\d+\.?\d*)', price_str.replace(',', ''))
            if price_match:
                product_info.price = float(price_match.group(1))
        except:
            pass

    def _extract_content_features_safe(self, product_info: BooksProductInfo, raw_meta: Dict, raw_reviews: List[Dict]):
        try:
            product_info.genres = self._classify_genres_rule_based(
                product_info.categories, product_info.title or "", product_info.description or ""
            )
            product_info.themes = self._extract_themes_rule_based(raw_reviews)
            if self.llm and raw_reviews:
                try:
                    self._enhance_with_llm(product_info, raw_meta, raw_reviews)
                except Exception as llm_error:
                    print(f"LLM enhancement failed: {llm_error}")
        except Exception as e:
            print(f"Error in content features extraction: {e}")

    def _classify_genres_rule_based(self, categories: List[str], title: str, description: str) -> List[str]:
        cache_key = "|".join(categories + [title, description])
        if cache_key in self._genre_cache:
            return self._genre_cache[cache_key]
        genre_mapping = {
            'fiction': ['fiction', 'literature', 'novel', 'story'],
            'mystery': ['mystery', 'thriller', 'crime', 'detective'],
            'sci-fi': ['science fiction', 'sci-fi', 'fantasy', 'space'],
            'romance': ['romance', 'love', 'romantic'],
            'biography': ['biography', 'memoir', 'autobiography'],
            'history': ['history', 'historical'],
            'self-help': ['self-help', 'personal development', 'self improvement'],
            'business': ['business', 'economics', 'finance', 'management'],
            'academic': ['academic', 'textbook', 'university', 'scholarly']
        }
        text_lower = " ".join(categories + [title, description]).lower()
        identified_genres = []
        for genre, keywords in genre_mapping.items():
            if any(keyword in text_lower for keyword in keywords):
                identified_genres.append(genre)
        result = identified_genres[:5]
        self._genre_cache[cache_key] = result
        return result

    def _extract_themes_rule_based(self, reviews: List[Dict]) -> List[str]:
        if not reviews:
            return []
        review_text = " ".join([
            review.get('title', '') + ' ' + review.get('text', '')
            for review in reviews
        ]).lower()
        if review_text in self._theme_cache:
            return self._theme_cache[review_text]
        theme_keywords = {
            'coming-of-age': ['growing up', 'adolescence', 'teenager', 'youth'],
            'family': ['family', 'parents', 'children', 'home', 'mother', 'father'],
            'love': ['love', 'romance', 'relationship', 'heart', 'romantic'],
            'friendship': ['friendship', 'friends', 'companion', 'buddy'],
            'survival': ['survival', 'struggle', 'overcome', 'endure'],
            'adventure': ['adventure', 'journey', 'quest', 'travel'],
            'power': ['power', 'authority', 'control', 'dominance'],
            'justice': ['justice', 'fairness', 'right', 'wrong', 'law'],
            'war': ['war', 'battle', 'conflict', 'military', 'soldier'],
            'technology': ['technology', 'tech', 'digital', 'computer', 'ai']
        }
        theme_scores = []
        for theme, keywords in theme_keywords.items():
            score = sum(review_text.count(keyword) for keyword in keywords)
            if score >= 2:
                theme_scores.append((theme, score))
        theme_scores.sort(key=lambda x: x[1], reverse=True)
        result = [theme for theme, _ in theme_scores[:6]]
        self._theme_cache[review_text] = result
        return result

    def _llm_extract_string(self, text: str, prompt: str, field_name: str) -> Optional[str]:
        if not self.llm:
            return None
        response = self.llm.invoke(prompt.format(text=text))
        return response.content.strip() if hasattr(response, 'content') else str(response).strip()

    def _llm_extract_list(self, text: str, prompt: str, field_name: str) -> List[str]:
        result = self._llm_extract_string(text, prompt, field_name)
        if not result:
            return []
        # 콤마/줄바꿈 분리
        items = [x.strip() for x in re.split(r'[\n,]', result) if x.strip()]
        return items

    def _enhance_with_llm(self, product_info: BooksProductInfo, raw_meta: Dict, raw_reviews: List[Dict]):
        if not self.llm:
            return
        review_text = " ".join([
            review.get('text', '')[:200]
            for review in raw_reviews[:5]
        ])
        combined_text = f"""Title: {product_info.title or ''}\nDescription: {product_info.description or ''}\nCategories: {'; '.join(product_info.categories)}\nSample Reviews: {review_text}"""
        # 복잡도
        if not product_info.complexity:
            complexity_prompt = """
            Based on the following book information, determine the reading complexity level.\nRespond with only one word: beginner, medium, or advanced.\n{text}\nComplexity:"""
            try:
                complexity = self._llm_extract_string(combined_text, complexity_prompt, "complexity")
                if complexity and complexity.lower() in ['beginner', 'medium', 'advanced']:
                    product_info.complexity = complexity.lower()
            except:
                pass
        # 타겟 독자층 정교화
        target_prompt = """
        Based on the reviews, identify specific target audiences.\nExamples: 'mystery lovers', 'history buffs', 'young professionals'.\nTarget Audiences:"""
        try:
            target_aud = self._llm_extract_list(combined_text, target_prompt, "target_audience")
            if target_aud:
                product_info.target_audience = target_aud
        except:
            pass
        # 독특한 특징 추출
        unique_features_prompt = """
        What makes this book unique compared to others in its genre?\nExtract 2-3 distinctive features.\nUnique Features:"""
        try:
            unique_feats = self._llm_extract_list(combined_text, unique_features_prompt, "unique_features")
            if unique_feats:
                product_info.search_boost_terms.extend(unique_feats)
        except:
            pass
        # 비교 언급 구조화 예시
        comparison_prompt = """
        From the reviews, extract books or series that are mentioned as similar to, better than, or worse than this book.\nReturn as a JSON dict with keys: similar_to, better_than, worse_than.\nComparisons:"""
        try:
            comp_json = self._llm_extract_string(combined_text, comparison_prompt, "comparison_mentions")
            if comp_json:
                try:
                    product_info.comparison_mentions = json.loads(comp_json)
                except json.JSONDecodeError:
                    product_info.comparison_mentions = {
                        "similar_to": [],
                        "better_than": [],
                        "worse_than": []
                    }
        except:
            product_info.comparison_mentions = {
                "similar_to": [],
                "better_than": [],
                "worse_than": []
            }

    def _extract_series_info(self, title: str, description: str) -> Optional[SeriesInfo]:
        # "Book 1", "Volume 2" 등 패턴 매칭
        series_pattern = r'(Book|Volume|Part)\s+(\d+)'
        match = re.search(series_pattern, title)
        if match:
            return SeriesInfo(
                series_name=title.split(match.group())[0].strip(),
                position_in_series=int(match.group(2)),
                total_books_in_series=0  # 추후 API로 조회 가능
            )
        return None

    def _extract_user_insights_safe(self, product_info: BooksProductInfo, reviews: List[Dict]):
        try:
            product_info.liked_aspects = self._extract_liked_aspects(reviews)
            product_info.disliked_aspects = self._extract_disliked_aspects(reviews)
            if not product_info.complexity:
                product_info.complexity = self._analyze_complexity(reviews)
            if not product_info.target_audience:
                product_info.target_audience = self._identify_target_audience(reviews)
        except Exception as e:
            print(f"Error in user insights extraction: {e}")

    def _extract_liked_aspects(self, reviews: List[Dict]) -> List[str]:
        positive_keywords = [
            'engaging', 'compelling', 'well-written', 'fascinating', 'brilliant',
            'captivating', 'thought-provoking', 'insightful', 'entertaining',
            'gripping', 'touching', 'inspiring', 'educational', 'informative'
        ]
        all_text = ' '.join([
            review.get('title', '') + ' ' + review.get('text', '')
            for review in reviews if review.get('rating', 0) >= 4.0
        ]).lower()
        found_keywords = [kw for kw in positive_keywords if kw in all_text]
        return found_keywords[:10]

    def _extract_disliked_aspects(self, reviews: List[Dict]) -> List[str]:
        negative_keywords = [
            'boring', 'confusing', 'difficult', 'slow', 'repetitive',
            'predictable', 'disappointing', 'unclear', 'dry', 'verbose'
        ]
        all_text = ' '.join([
            review.get('title', '') + ' ' + review.get('text', '')
            for review in reviews if review.get('rating', 0) <= 2.0
        ]).lower()
        found_keywords = [kw for kw in negative_keywords if kw in all_text]
        return found_keywords[:5]

    def _analyze_complexity(self, reviews: List[Dict]) -> str:
        all_text = ' '.join([
            review.get('text', '') for review in reviews
        ]).lower()
        beginner_indicators = ['easy', 'simple', 'basic', 'beginner', 'accessible']
        advanced_indicators = ['complex', 'advanced', 'difficult', 'challenging', 'deep']
        beginner_count = sum(all_text.count(ind) for ind in beginner_indicators)
        advanced_count = sum(all_text.count(ind) for ind in advanced_indicators)
        if beginner_count > advanced_count * 2:
            return 'beginner'
        elif advanced_count > beginner_count * 2:
            return 'advanced'
        else:
            return 'medium'

    def _identify_target_audience(self, reviews: List[Dict]) -> List[str]:
        all_text = ' '.join([
            review.get('text', '') for review in reviews
        ]).lower()
        audience_keywords = {
            'students': ['student', 'college', 'university', 'academic'],
            'professionals': ['professional', 'work', 'career', 'business'],
            'general_readers': ['anyone', 'everyone', 'general'],
            'young_adults': ['young adult', 'teen', 'teenager'],
            'adults': ['adult', 'mature']
        }
        identified = [aud for aud, kws in audience_keywords.items() if any(kw in all_text for kw in kws)]
        return identified if identified else ['general_readers']

# ===== 기존 시스템 호환 함수 =====
def create_legacy_document(product_info: BooksProductInfo) -> Dict[str, str]:
    doc = product_info.create_enhanced_book_document()
    return {
        "id": product_info.parent_asin,
        "text": doc["text"]
    }

# ===== 통합 테스트 함수 =====
def test_extraction_pipeline():
    sample_meta = {
        "parent_asin": "B001TEST",
        "title": "Test Book Title",
        "author": ["Test Author"],
        "categories": ["Books", "Fiction", "Mystery"],
        "description": ["A thrilling mystery novel"],
        "average_rating": "4.5",
        "rating_number": "100",
        "price": "$12.99"
    }
    sample_reviews = [
        {"rating": 5.0, "title": "Great", "text": "Engaging and well-written mystery"},
        {"rating": 4.0, "title": "Good", "text": "Complex plot but enjoyable read"},
        {"rating": 3.0, "title": "OK", "text": "Slow start but gets better"}
    ]
    extractor = BooksProductInfoExtractor(llm=None)
    product_info = extractor.extract_product_info("B001TEST", sample_meta, sample_reviews)
    print("=== Product Info Test ===")
    print(f"Title: {product_info.title}")
    print(f"Authors: {product_info.authors}")
    print(f"Genres: {product_info.genres}")
    print(f"Themes: {product_info.themes}")
    print(f"Complexity: {product_info.complexity}")
    print(f"Liked: {product_info.liked_aspects}")
    from books_user_profile import BooksUserProfileGenerator
    profile_gen = BooksUserProfileGenerator()
    user_profile = profile_gen.generate_from_product_info(product_info)
    print("\n=== User Profile Test ===")
    print(f"Preferred Genres: {user_profile.preferred_genres}")
    print(f"Genre Weights: {user_profile.genre_weights}")
    print(f"Disliked Genres: {user_profile.disliked_genres}")
    print(f"Complexity Pref: {user_profile.complexity_preference}")
    legacy_doc = create_legacy_document(product_info)
    print("\n=== Legacy Compatibility Test ===")
    print(f"Legacy ID: {legacy_doc['id']}")
    print(f"Legacy Text (first 100 chars): {legacy_doc['text'][:100]}...")
    return product_info, user_profile, legacy_doc

if __name__ == "__main__":
    test_extraction_pipeline()
