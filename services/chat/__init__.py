"""Chat Package — 20-Level Conversational System for Advanced Screening.

Provides a comprehensive multi-level architecture:
  1-5: Base NLP (normalization, intent, entities, filters, context)
  6:   BERT integration (optional)
  7:   Slot filling
  8:   Context management (DialogManager)
  9:   Compound intent splitting
  10:  Dynamic filter generation
  11:  Explanations (Explainer)
  12:  Chart generation
  13:  Speech input/output
  14:  Sentiment analysis
  15:  Personalization
  16:  News integration
  17:  Advanced comparison
  18:  Active suggestions
  19:  Learning from interactions
  20:  Complex mixed queries
"""

from services.chat.chart_generator import ChartGenerator
from services.chat.chat_engine import ChatEngine
from services.chat.comparison_engine import ComparisonEngine
from services.chat.compound_splitter import CompoundSplitter
from services.chat.dialog_manager import DialogManager
from services.chat.entity_extractor import EntityExtractor
from services.chat.intent_classifier import IntentClassifier
from services.chat.learning_engine import LearningEngine
from services.chat.news_analyzer import NewsAnalyzer
from services.chat.news_fetcher import NewsFetcher
from services.chat.news_integration import NewsIntegration
from services.chat.personalizer import Personalizer
from services.chat.sentiment_analyzer import SentimentAnalyzer
from services.chat.suggestion_engine import SuggestionEngine

__all__ = [
    "ChatEngine",
    "IntentClassifier",
    "EntityExtractor",
    "CompoundSplitter",
    "DialogManager",
    "SentimentAnalyzer",
    "Personalizer",
    "NewsFetcher",
    "NewsAnalyzer",
    "NewsIntegration",
    "ComparisonEngine",
    "ChartGenerator",
    "SuggestionEngine",
    "LearningEngine",
]
