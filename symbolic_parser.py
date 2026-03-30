import re


class SymbolicDefinitionParser:
    """
    A neuro-symbolic parser to validate terminological definitions
    based on ISO 1087-1:2000 structural rules.

    Checks: circularity, genus presence, differentia presence,
    negation, encyclopedic content, conciseness, and genus-in-termbase.
    """

    def __init__(self, known_terms=None):
        """
        Args:
            known_terms: optional list of terms in the project's termbase.
                         Used for genus-in-termbase validation.
        """
        self.known_terms = [t.lower() for t in (known_terms or [])]

        # Genus indicators
        self.genus_indicators_en = [
            r"\bis an?\b", r"\brefers to\b", r"\bdenotes\b",
            r"\ba type of\b", r"\ba kind of\b", r"\ba form of\b",
            r"\ba class of\b", r"\ba method of\b", r"\ba process of\b",
            r"\bdefined as\b",
            # Catch definitions starting with "A/An [noun]" (genus-first pattern)
            r"^an?\s+\w+", r"^the\s+\w+",
        ]
        self.genus_indicators_el = [
            r"\bείναι\b", r"\bαναφέρεται\b", r"\bαποτελεί\b",
            r"\bορίζεται\b", r"\bσυνιστά\b",
            r"\bείδος\b", r"\bμορφή\b", r"\bτύπος\b",
            r"\bμέθοδος\b", r"\bδιαδικασία\b", r"\bδιαταραχή\b",
            r"\bκατάσταση\b", r"\bπάθηση\b",
        ]

        # Differentia indicators — words that signal distinguishing characteristics
        self.differentia_indicators_en = [
            r"\bthat\b", r"\bwhich\b", r"\bcharacterized by\b",
            r"\bcaused by\b", r"\bresulting from\b", r"\binvolving\b",
            r"\bused for\b", r"\bused to\b", r"\bdesigned to\b",
            r"\bconsisting of\b", r"\bdistinguished by\b",
            r"\bwhere\b", r"\bwherein\b", r"\bthrough\b",
            r"\btriggered by\b", r"\bassociated with\b",
            r"\bleading to\b", r"\bcausing\b", r"\baffecting\b",
        ]
        self.differentia_indicators_el = [
            r"\bπου\b", r"\bο οποίος\b", r"\bη οποία\b", r"\bτο οποίο\b",
            r"\bχαρακτηρίζεται από\b", r"\bπροκαλείται από\b",
            r"\bοφείλεται σε\b", r"\bαποτελείται από\b",
            r"\bχρησιμοποιείται για\b", r"\bμέσω\b",
        ]

        # Negation patterns — definitions should not be phrased negatively
        self.negation_patterns_en = [
            r"\bis\s+not\b", r"\bnot\s+a\b", r"\bdoes\s+not\b",
            r"\bunlike\b", r"\bcannot\b", r"\bdo\s+not\b",
            r"\bnever\b", r"\bnor\b",
        ]
        self.negation_patterns_el = [
            r"\bδεν\s+είναι\b", r"\bδεν\s+αποτελεί\b", r"\bδεν\s+αναφέρεται\b",
            r"\bδεν\b", r"\bούτε\b",
        ]

        # Encyclopedic content indicators — definitions should not contain these
        self.encyclopedic_indicators_en = [
            r"\bfor example\b", r"\bfor instance\b", r"\be\.g\.\b",
            r"\bsuch as\b.*,.*,",  # "such as X, Y, Z" (listing examples)
            r"\bwas discovered\b", r"\bwas first\b", r"\bin \d{4}\b",
            r"\bhistorically\b", r"\baccording to\b",
            r"\bit is important\b", r"\bit should be noted\b",
        ]
        self.encyclopedic_indicators_el = [
            r"\bγια παράδειγμα\b", r"\bπ\.χ\.\b", r"\bόπως\b.*,.*,",
            r"\bανακαλύφθηκε\b", r"\bιστορικά\b", r"\bσύμφωνα με\b",
            r"\bείναι σημαντικό\b",
        ]

    def validate_structure(self, definition: str, term: str, lang: str = "en") -> dict:
        """
        Validates if a definition follows ISO-compliant genus + differentia structure.

        Returns dict with:
            score (int): overall quality score (0-7 scale)
            max_score (int): maximum possible score
            valid (bool): whether the definition passes (score >= threshold)
            checks (list[dict]): individual check results with name, passed, reason
        """
        checks = []
        definition_lower = definition.lower().strip()
        term_lower = term.lower().strip()

        # ── 1. Circularity check ──
        # The term should not appear at the start of its own definition
        def_words = definition_lower.split()
        term_words = term_lower.split()
        starts_with_term = def_words[:len(term_words)] == term_words
        # Also check if term appears anywhere (partial circularity)
        term_in_def = term_lower in definition_lower

        if starts_with_term:
            checks.append({
                "name": "circularity",
                "passed": False,
                "weight": 1,
                "reason": f"Circular: definition begins with the term '{term}'"
            })
        elif term_in_def:
            checks.append({
                "name": "circularity",
                "passed": False,
                "weight": 1,
                "reason": f"Partially circular: term '{term}' appears within its own definition"
            })
        else:
            checks.append({
                "name": "circularity",
                "passed": True,
                "weight": 1,
                "reason": "No circularity detected"
            })

        # ── 2. Genus check ──
        indicators = self.genus_indicators_el if lang == "el" else self.genus_indicators_en
        genus_match = None
        for pattern in indicators:
            m = re.search(pattern, definition_lower)
            if m:
                genus_match = m.group()
                break

        if genus_match:
            checks.append({
                "name": "genus",
                "passed": True,
                "weight": 2,
                "reason": f"Genus indicator found: '{genus_match}'"
            })
        else:
            checks.append({
                "name": "genus",
                "passed": False,
                "weight": 2,
                "reason": "Missing genus indicator — definition should state what category the concept belongs to (e.g. 'is a [type]', 'refers to a [category]')"
            })

        # ── 3. Differentia check ──
        diff_indicators = self.differentia_indicators_el if lang == "el" else self.differentia_indicators_en
        diff_match = None
        for pattern in diff_indicators:
            m = re.search(pattern, definition_lower)
            if m:
                diff_match = m.group()
                break

        if diff_match:
            checks.append({
                "name": "differentia",
                "passed": True,
                "weight": 1,
                "reason": f"Differentia indicator found: '{diff_match}'"
            })
        else:
            checks.append({
                "name": "differentia",
                "passed": False,
                "weight": 1,
                "reason": "Missing differentia — definition should include distinguishing characteristics (e.g. 'that causes...', 'characterized by...')"
            })

        # ── 4. Negation check ──
        neg_patterns = self.negation_patterns_el if lang == "el" else self.negation_patterns_en
        neg_match = None
        for pattern in neg_patterns:
            m = re.search(pattern, definition_lower)
            if m:
                neg_match = m.group()
                break

        if neg_match:
            checks.append({
                "name": "negation",
                "passed": False,
                "weight": 1,
                "reason": f"Definition uses negative phrasing: '{neg_match}' — definitions should state what a concept IS, not what it is not"
            })
        else:
            checks.append({
                "name": "negation",
                "passed": True,
                "weight": 1,
                "reason": "No negative phrasing detected"
            })

        # ── 5. Encyclopedic content check ──
        enc_indicators = self.encyclopedic_indicators_el if lang == "el" else self.encyclopedic_indicators_en
        enc_match = None
        for pattern in enc_indicators:
            m = re.search(pattern, definition_lower)
            if m:
                enc_match = m.group()
                break

        if enc_match:
            checks.append({
                "name": "encyclopedic",
                "passed": False,
                "weight": 1,
                "reason": f"Contains encyclopedic content: '{enc_match}' — definitions should not include examples, history, or commentary"
            })
        else:
            checks.append({
                "name": "encyclopedic",
                "passed": True,
                "weight": 1,
                "reason": "No encyclopedic content detected"
            })

        # ── 6. Conciseness check ──
        word_count = len(definition.split())
        if word_count < 5:
            checks.append({
                "name": "conciseness",
                "passed": False,
                "weight": 1,
                "reason": f"Too short ({word_count} words) — definition may be incomplete"
            })
        elif word_count > 50:
            checks.append({
                "name": "conciseness",
                "passed": False,
                "weight": 1,
                "reason": f"Too long ({word_count} words) — definitions should be concise (under 50 words)"
            })
        else:
            checks.append({
                "name": "conciseness",
                "passed": True,
                "weight": 1,
                "reason": f"Good length ({word_count} words)"
            })

        # ── 7. Genus-in-termbase check ──
        if self.known_terms and genus_match:
            # Extract the word(s) right after the genus indicator to find the superordinate concept
            genus_pattern = None
            for pattern in indicators:
                m = re.search(pattern + r"\s+(?:a\s+|an\s+)?(\w+(?:\s+\w+)?)", definition_lower)
                if m:
                    genus_pattern = m.group(1).strip()
                    break

            if genus_pattern and any(genus_pattern in t for t in self.known_terms):
                checks.append({
                    "name": "genus_in_termbase",
                    "passed": True,
                    "weight": 1,
                    "reason": f"Superordinate concept '{genus_pattern}' exists in the project termbase"
                })
            elif genus_pattern:
                checks.append({
                    "name": "genus_in_termbase",
                    "passed": False,
                    "weight": 1,
                    "reason": f"Superordinate concept '{genus_pattern}' is not in the project termbase — consider adding it as a term"
                })
            else:
                checks.append({
                    "name": "genus_in_termbase",
                    "passed": True,
                    "weight": 0,
                    "reason": "Could not extract superordinate concept to verify"
                })
        # If no known_terms provided, skip this check silently

        # ── Calculate score ──
        score = 0
        max_score = 0
        for check in checks:
            max_score += check["weight"]
            if check["passed"]:
                score += check["weight"]

        # Failed reasons for backward compatibility and for the feedback loop
        failed_reasons = [c["reason"] for c in checks if not c["passed"]]

        return {
            "score": score,
            "max_score": max_score,
            "valid": score >= (max_score * 0.7),  # Pass at 70%+
            "checks": checks,
            "reasons": failed_reasons,
        }

    def get_feedback_prompt(self, definition: str, term: str, validation_result: dict, lang: str = "en") -> str:
        """
        Generate a targeted feedback prompt for the LLM based on symbolic validation failures.
        Used in the neuro-symbolic feedback loop.
        """
        failed_checks = [c for c in validation_result["checks"] if not c["passed"]]
        if not failed_checks:
            return ""

        lang_label = "Greek" if lang == "el" else "English"

        feedback_parts = [
            f"Your previous definition for '{term}' had the following structural issues:\n"
        ]
        for i, check in enumerate(failed_checks, 1):
            feedback_parts.append(f"{i}. [{check['name'].upper()}] {check['reason']}")

        feedback_parts.append(f"\nRewrite the definition for '{term}' in {lang_label}, fixing ALL of the above issues.")
        feedback_parts.append("A valid terminological definition must:")
        feedback_parts.append("- Begin with a superordinate concept (genus): what category does this concept belong to?")
        feedback_parts.append("- Include distinguishing characteristics (differentia): what makes it different from related concepts?")
        feedback_parts.append("- Be concise (under 50 words), positive (not 'is not'), and factual (no examples or history).")
        feedback_parts.append("- Not include the term itself in the definition.")
        feedback_parts.append("\nOutput ONLY the corrected definition text, nothing else.")

        return "\n".join(feedback_parts)


# Example usage
if __name__ == "__main__":
    parser = SymbolicDefinitionParser(known_terms=["disorder", "immune system", "gluten"])
    test_def = "Celiac disease is a chronic immune-mediated disorder triggered by gluten ingestion in genetically predisposed individuals, causing inflammation of the small intestine."
    result = parser.validate_structure(test_def, "Celiac disease")
    print(f"Score: {result['score']}/{result['max_score']} | Valid: {result['valid']}")
    for check in result["checks"]:
        status = "✓" if check["passed"] else "✗"
        print(f"  {status} [{check['name']}] {check['reason']}")

    # Test with a bad definition
    bad_def = "Celiac disease is not a common condition. It was first described in 1888 by Samuel Gee."
    result2 = parser.validate_structure(bad_def, "Celiac disease")
    print(f"\nBad def - Score: {result2['score']}/{result2['max_score']} | Valid: {result2['valid']}")
    for check in result2["checks"]:
        status = "✓" if check["passed"] else "✗"
        print(f"  {status} [{check['name']}] {check['reason']}")

    # Test feedback generation
    feedback = parser.get_feedback_prompt(bad_def, "Celiac disease", result2)
    print(f"\nFeedback prompt:\n{feedback}")
