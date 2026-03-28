import re

class SymbolicDefinitionParser:
    """
    A symbolic parser to validate definitions based on terminological rules.
    """
    
    def __init__(self):
        # Common genus indicators in EN and EL
        self.genus_indicators_en = [r"\bis a\b", r"\brefers to\b", r"\ba type of\b", r"\ba method of\b", r"\ba disorder\b"]
        self.genus_indicators_el = [r"\beίναι\b", r"\baναφέρεται\b", r"\beίδος\b", r"\bmέθοδος\b", r"\bdιαταραχή\b"]

    def validate_structure(self, definition: str, term: str, lang: str = "en") -> dict:
        """
        Validates if the definition follows Genus + Differentia structure.
        """
        score = 0
        reasons = []
        
        # 1. Check for Term inclusion (Circularity check)
        if term.lower() in definition.lower().split()[:3]:
            score -= 1
            reasons.append("Circular: Term appears at start of definition")
        else:
            score += 1

        # 2. Genus Check
        indicators = self.genus_indicators_el if lang == "el" else self.genus_indicators_en
        has_genus = any(re.search(pattern, definition.lower()) for pattern in indicators)
        if has_genus:
            score += 2
        else:
            reasons.append("Missing genus indicator (is a / είναι)")

        # 3. Length Check (Conciseness)
        word_count = len(definition.split())
        if 5 < word_count < 50:
            score += 1
        elif word_count >= 50:
            reasons.append("Too long (> 50 words)")
        
        return {
            "score": max(0, score),
            "valid": score >= 3,
            "reasons": reasons
        }

# Example usage
if __name__ == "__main__":
    parser = SymbolicDefinitionParser()
    test_def = "Celiac disease is a chronic immune-mediated disorder..."
    print(parser.validate_structure(test_def, "Celiac disease"))
