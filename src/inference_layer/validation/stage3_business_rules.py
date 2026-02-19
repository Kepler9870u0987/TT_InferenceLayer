"""
Stage 3: Business Rules Validation.

Validate business-specific constraints:
- candidateid must exist in input candidates (no keyword invention)
- labelid must be in TopicsEnum (no topic invention)
- dictionaryversion must match request

This is a hard-fail stage: violations trigger retry.
"""

import logging

from ..models.enums import TopicsEnum, SentimentEnum, PriorityEnum
from ..models.input_models import TriageRequest
from ..models.output_models import EmailTriageResponse
from .exceptions import BusinessRuleViolation

logger = logging.getLogger(__name__)


class Stage3BusinessRules:
    """
    Stage 3 validator: Business rules enforcement.
    
    Raises BusinessRuleViolation on rule violations (hard fail).
    """
    
    def validate(self, response: EmailTriageResponse, request: TriageRequest) -> None:
        """
        Validate business rules against LLM response.
        
        Args:
            response: Parsed and schema-validated EmailTriageResponse
            request: Original TriageRequest with candidates and version
            
        Raises:
            BusinessRuleViolation: If any business rule is violated
        """
        # Rule 1: Dictionary version must match
        self._validate_dictionary_version(response, request)
        
        # Rule 2: All topic labelids must be in TopicsEnum
        self._validate_topic_labels(response)
        
        # Rule 3: All candidateids must exist in input candidates
        self._validate_candidate_ids(response, request)
        
        # Rule 4: Sentiment and Priority must be valid enums (redundant with schema, but explicit check)
        self._validate_sentiment_priority(response)
        
        logger.debug("Stage 3: All business rules validated successfully")
    
    def _validate_dictionary_version(
        self, 
        response: EmailTriageResponse, 
        request: TriageRequest
    ) -> None:
        """
        Validate that dictionary version matches input request.
        
        Args:
            response: LLM response
            request: Input request
            
        Raises:
            BusinessRuleViolation: If versions don't match
        """
        if response.dictionary_version != request.dictionary_version:
            raise BusinessRuleViolation(
                f"Dictionary version mismatch: response has {response.dictionary_version}, "
                f"expected {request.dictionary_version}",
                rule_name="dictionary_version_match",
                invalid_value=response.dictionary_version,
                expected_values=[str(request.dictionary_version)],
                field_path="dictionaryversion"
            )
    
    def _validate_topic_labels(self, response: EmailTriageResponse) -> None:
        """
        Validate that all topic labels are in TopicsEnum.
        
        Args:
            response: LLM response
            
        Raises:
            BusinessRuleViolation: If any labelid is not in enum
        """
        valid_topics = set(topic.value for topic in TopicsEnum)
        
        for i, topic in enumerate(response.topics):
            if topic.label_id not in valid_topics:
                raise BusinessRuleViolation(
                    f"Topic labelid '{topic.label_id}' is not in TopicsEnum",
                    rule_name="topic_label_in_enum",
                    invalid_value=topic.label_id,
                    expected_values=sorted(valid_topics),
                    field_path=f"topics[{i}].labelid"
                )
    
    def _validate_candidate_ids(
        self, 
        response: EmailTriageResponse, 
        request: TriageRequest
    ) -> None:
        """
        Validate that all candidateids exist in input candidates.
        
        This prevents the LLM from inventing keywords.
        
        Args:
            response: LLM response
            request: Input request with candidate keywords
            
        Raises:
            BusinessRuleViolation: If any candidateid doesn't exist in input
        """
        # Build set of valid candidate IDs
        valid_candidate_ids = {candidate.candidate_id for candidate in request.candidate_keywords}
        
        # Check all keywords in all topics
        for topic_idx, topic in enumerate(response.topics):
            for kw_idx, keyword in enumerate(topic.keywords_in_text):
                if keyword.candidate_id not in valid_candidate_ids:
                    raise BusinessRuleViolation(
                        f"Keyword candidateid '{keyword.candidate_id}' not found in input candidates "
                        f"(LLM invented a keyword)",
                        rule_name="candidateid_exists_in_input",
                        invalid_value=keyword.candidate_id,
                        expected_values=None,  # Too many to list
                        field_path=f"topics[{topic_idx}].keywordsintext[{kw_idx}].candidateid"
                    )
    
    def _validate_sentiment_priority(self, response: EmailTriageResponse) -> None:
        """
        Validate sentiment and priority enum values.
        
        This is redundant with JSON Schema validation, but provides explicit check
        and better error messages.
        
        Args:
            response: LLM response
            
        Raises:
            BusinessRuleViolation: If sentiment or priority value is invalid
        """
        # Validate sentiment
        valid_sentiments = set(sentiment.value for sentiment in SentimentEnum)
        if response.sentiment.value not in valid_sentiments:
            raise BusinessRuleViolation(
                f"Sentiment value '{response.sentiment.value}' is not in SentimentEnum",
                rule_name="sentiment_in_enum",
                invalid_value=response.sentiment.value,
                expected_values=sorted(valid_sentiments),
                field_path="sentiment.value"
            )
        
        # Validate priority
        valid_priorities = set(priority.value for priority in PriorityEnum)
        if response.priority.value not in valid_priorities:
            raise BusinessRuleViolation(
                f"Priority value '{response.priority.value}' is not in PriorityEnum",
                rule_name="priority_in_enum",
                invalid_value=response.priority.value,
                expected_values=sorted(valid_priorities),
                field_path="priority.value"
            )
