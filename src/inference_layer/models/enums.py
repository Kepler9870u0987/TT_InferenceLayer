"""
Enumerations for LLM Inference Layer data models.

All enums are closed taxonomies - no values outside these sets are permitted.
"""

from enum import Enum


class TopicsEnum(str, Enum):
    """
    Closed taxonomy of email topics.
    
    Multi-label classification: each email can have 1-5 topics.
    UNKNOWNTOPIC is a valid label when the email doesn't fit any other category.
    """
    
    FATTURAZIONE = "FATTURAZIONE"
    ASSISTENZATECNICA = "ASSISTENZATECNICA"
    RECLAMO = "RECLAMO"
    INFOCOMMERCIALI = "INFOCOMMERCIALI"
    DOCUMENTI = "DOCUMENTI"
    APPUNTAMENTO = "APPUNTAMENTO"
    CONTRATTO = "CONTRATTO"
    GARANZIA = "GARANZIA"
    SPEDIZIONE = "SPEDIZIONE"
    UNKNOWNTOPIC = "UNKNOWNTOPIC"


class SentimentEnum(str, Enum):
    """
    Email sentiment classification.
    
    Sentiment is single-label (exactly one value per email).
    """
    
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class PriorityEnum(str, Enum):
    """
    Email priority/urgency classification.
    
    Priority is single-label (exactly one value per email).
    Ordered from low to urgent (can be used for ordinal comparisons).
    """
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    
    @classmethod
    def get_ordinal(cls, priority: "PriorityEnum") -> int:
        """Get ordinal value for priority (0=low, 1=medium, 2=high, 3=urgent)."""
        order = [cls.LOW, cls.MEDIUM, cls.HIGH, cls.URGENT]
        return order.index(priority)
