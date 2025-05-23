from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class BooksUserProfile:
    """
    구조화된 Books 사용자 프로필 (동적 업데이트 및 컨텍스트 인식 개선 포함)
    """
    # 장르 선호도
    preferred_genres: List[str] = field(default_factory=list)
    disliked_genres: List[str] = field(default_factory=list)
    genre_weights: Dict[str, float] = field(default_factory=dict)

    # 작가 선호도
    preferred_authors: List[str] = field(default_factory=list)
    disliked_authors: List[str] = field(default_factory=list)

    # 테마 선호도
    preferred_themes: List[str] = field(default_factory=list)
    disliked_themes: List[str] = field(default_factory=list)

    # 독서 선호도
    complexity_preference: Optional[str] = None  # beginner, medium, advanced
    length_preference: str = "any"  # short, medium, long, any
    recency_preference: str = "any"  # recent, classic, any

    # 상황별 선호도
    reading_purposes: List[str] = field(default_factory=list)  # entertainment, learning, professional
    reading_contexts: List[str] = field(default_factory=list)  # commute, bedtime, vacation

    # 대화 패턴
    interaction_style: str = "balanced"  # brief, detailed, balanced
    question_answering_pattern: Dict[str, str] = field(default_factory=dict)

    # 세션 정보
    current_session_context: Dict[str, Any] = field(default_factory=dict)

    # 신뢰도 및 동적 업데이트 관련 필드
    profile_confidence: Dict[str, float] = field(default_factory=dict)  # 예: {"mystery": 0.9, ...}
    last_updated: Optional[datetime] = None
    interaction_count: int = 0
    # 컨텍스트 인식 선호도
    contextual_preferences: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def update_from_interaction(self, action: str, item: str, feedback: str):
        """사용자 상호작용으로부터 프로필 업데이트"""
        if action == "selected":
            self._strengthen_preference(item)
        elif action == "rejected":
            self._weaken_preference(item)
        self.interaction_count += 1
        self.last_updated = datetime.now()
        self._recalculate_confidence()

    def _strengthen_preference(self, item: str):
        # 장르/작가/테마 등 선호 강화 (간단 예시)
        if item in self.genre_weights:
            self.genre_weights[item] = min(self.genre_weights[item] + 0.1, 1.0)
        else:
            self.genre_weights[item] = 0.7
        self.profile_confidence[item] = min(self.profile_confidence.get(item, 0.5) + 0.1, 1.0)

    def _weaken_preference(self, item: str):
        if item in self.genre_weights:
            self.genre_weights[item] = max(self.genre_weights[item] - 0.2, 0.0)
        self.profile_confidence[item] = max(self.profile_confidence.get(item, 0.5) - 0.2, 0.0)

    def _recalculate_confidence(self):
        # 간단 예시: 상호작용 수에 따라 전체 confidence 소폭 증가
        for k in self.profile_confidence:
            self.profile_confidence[k] = min(self.profile_confidence[k] + 0.01, 1.0)

    def analyze_qa_pattern(self) -> str:
        """질문 응답 패턴으로 독자 유형 파악 (예시)"""
        if hasattr(self, 'always_chooses_first') and self.always_chooses_first:
            return "impulsive_reader"
        elif hasattr(self, 'varies_choices') and self.varies_choices:
            return "exploratory_reader"
        return "balanced_reader"

    def answer_based_on_profile(self, question, options):
        """프로필 기반 응답 예시"""
        if self.interaction_style == "brief":
            # 선호 장르와 빠른 매칭
            for opt in options:
                if any(g in opt for g in self.preferred_genres):
                    return opt
            return options[0]
        else:
            # 상세 분석 (예시)
            scored = [(opt, sum(self.genre_weights.get(g, 0) for g in self.preferred_genres if g in opt)) for opt in options]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0] if scored else options[0]

    def get_context_based_preference(self, context: str) -> Dict[str, Any]:
        """컨텍스트(상황)별 선호도 반환"""
        return self.contextual_preferences.get(context, {})

    def resolve_preference_conflicts(self):
        """선호/비선호 장르 충돌 해결"""
        conflicts = set(self.preferred_genres) & set(self.disliked_genres)
        for conflict in conflicts:
            if self.genre_weights.get(conflict, 0) > 0.7:
                self.disliked_genres.remove(conflict)

class BooksUserProfileGenerator:
    """개선된 사용자 프로필 생성기"""
    def __init__(self):
        self.genre_relationships = self._init_genre_relationships()
        self.contrast_genres = self._init_contrast_genres()

    def generate_from_product_info(self, product_info: Any) -> BooksUserProfile:
        """안전한 프로필 생성"""
        try:
            base_genres = (product_info.genres or [])[:3]
            base_themes = (product_info.themes or [])[:3]
            base_authors = (product_info.authors or [])[:1]
            complexity = product_info.complexity or "medium"
            expanded_genres, genre_weights = self._expand_genres_safely(base_genres)
            disliked_genres = self._generate_contrast_genres_safely(expanded_genres)
            reading_pattern = self._generate_reading_pattern(complexity)
            profile_confidence = {g: 0.8 for g in expanded_genres}
            user_profile = BooksUserProfile(
                preferred_genres=expanded_genres,
                disliked_genres=disliked_genres,
                genre_weights=genre_weights,
                preferred_authors=base_authors,
                disliked_authors=[],
                preferred_themes=base_themes,
                disliked_themes=[],
                complexity_preference=complexity,
                profile_confidence=profile_confidence,
                **reading_pattern
            )
            user_profile.resolve_preference_conflicts()
            return user_profile
        except Exception as e:
            print(f"Error generating user profile: {e}")
            return BooksUserProfile()

    def _expand_genres_safely(self, base_genres: List[str]) -> tuple[list, dict]:
        expanded = base_genres[:]
        weights = {}
        for genre in base_genres:
            weights[genre] = 0.9
        for genre in base_genres:
            related = self.genre_relationships.get(genre, [])
            for rel_genre in related[:2]:
                if rel_genre not in expanded:
                    expanded.append(rel_genre)
                    weights[rel_genre] = 0.6
        return expanded, weights

    def _generate_contrast_genres_safely(self, preferred_genres: List[str]) -> List[str]:
        disliked = []
        for genre in preferred_genres:
            contrasts = self.contrast_genres.get(genre, [])
            disliked.extend(contrasts[:1])
        return list(set(disliked))

    def _generate_reading_pattern(self, complexity: str) -> Dict[str, Any]:
        patterns = {
            'beginner': {
                'length_preference': 'short',
                'reading_purposes': ['entertainment'],
                'reading_contexts': ['bedtime', 'commute'],
                'interaction_style': 'brief'
            },
            'medium': {
                'length_preference': 'medium',
                'reading_purposes': ['entertainment', 'learning'],
                'reading_contexts': ['evening', 'weekend'],
                'interaction_style': 'balanced'
            },
            'advanced': {
                'length_preference': 'long',
                'reading_purposes': ['learning', 'professional'],
                'reading_contexts': ['study_time'],
                'interaction_style': 'detailed'
            }
        }
        return patterns.get(complexity, patterns['medium'])

    def _init_genre_relationships(self) -> Dict[str, List[str]]:
        return {
            'mystery': ['thriller', 'crime', 'suspense'],
            'thriller': ['mystery', 'suspense', 'crime'],
            'sci-fi': ['fantasy', 'dystopian'],
            'fantasy': ['sci-fi', 'urban_fantasy'],
            'romance': ['contemporary_fiction', 'drama'],
            'biography': ['memoir', 'history'],
            'self-help': ['psychology', 'personal_development'],
            'business': ['economics', 'management'],
            'fiction': ['literary_fiction', 'contemporary_fiction']
        }

    def _init_contrast_genres(self) -> Dict[str, List[str]]:
        return {
            'mystery': ['romance', 'self-help'],
            'sci-fi': ['biography', 'history'],
            'romance': ['mystery', 'academic'],
            'biography': ['fantasy', 'sci-fi'],
            'self-help': ['fiction'],
            'business': ['fiction'],
            'fiction': ['academic', 'business']
        }
