"""
Intent Recognition for Workflow System
Detects user intents to trigger appropriate workflows
"""

from typing import Dict, List, Optional, Tuple
import re

class IntentRecognizer:
    """Recognizes user intents from messages to trigger workflows"""

    def __init__(self):
        # Intent patterns for workflow detection
        self.intent_patterns = {
            'rma_process_v1': [
                r'need to return.*laptop',
                r'return.*device',
                r'laptop.*broken',
                r'device.*defective',
                r'rma.*request',
                r'return merchandise',
                r'faulty.*equipment'
            ],
            'employee_onboarding_v1': [
                r'new employee.*starting',
                r'onboard.*employee',
                r'employee.*onboarding',
                r'hiring.*new.*person',
                r'new.*hire',
                r'start.*employee',
                r'employee.*setup'
            ],
            'system_info_v1': [
                r'tell me.*what.*system',
                r'what.*system.*we.*on',
                r'system.*information',
                r'get.*system.*info',
                r'show.*system.*details',
                r'check.*system.*specs',
                r'system.*diagnostic'
            ],
            'contract_analysis_v1': [
                r'analyze.*contract',
                r'review.*contract',
                r'check.*contract.*compliance',
                r'contract.*analysis',
                r'dutch.*construction.*contract',
                r'vat.*compliance',
                r'safety.*plan.*check',
                r'payment.*terms.*review',
                r'bank.*guarantee.*verification',
                r'construction.*contract.*review'
            ]
        }

    def recognize_intent(self, message: str) -> List[Tuple[str, float]]:
        """
        Recognize intents from a message

        Args:
            message: User message to analyze

        Returns:
            List of (intent_name, confidence) tuples sorted by confidence desc
        """
        message_lower = message.lower()
        results = []

        for intent_name, patterns in self.intent_patterns.items():
            confidence = 0.0
            matches = 0

            for pattern in patterns:
                if re.search(pattern, message_lower):
                    matches += 1
                    confidence = max(confidence, 0.8)  # Base confidence for pattern match

            # Boost confidence based on multiple pattern matches
            if matches > 1:
                confidence = min(0.95, confidence + (matches - 1) * 0.1)

            if confidence > 0:
                results.append((intent_name, confidence))

        # Sort by confidence descending
        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_best_intent(self, message: str, threshold: float = 0.7) -> Optional[Tuple[str, float]]:
        """
        Get the best matching intent above threshold

        Args:
            message: User message to analyze
            threshold: Minimum confidence threshold

        Returns:
            (intent_name, confidence) or None if no match above threshold
        """
        intents = self.recognize_intent(message)
        if intents and intents[0][1] >= threshold:
            return intents[0]
        return None