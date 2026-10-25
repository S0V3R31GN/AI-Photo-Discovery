import re

PERSON = ["woman", "man", "lady", "gentleman", "guy", "girl", "boy", "kid", "child",
          "adult", "teen", "teenager", "toddler", "baby", "infant"]
PEOPLE = ["women", "men", "ladies", "gentlemen", "guys", "girls", "boys", "kids", "children",
          "adults", "teens", "teenagers", "toddlers", "babies", "infants"]

_person = "|".join(PERSON)
_people = "|".join(PEOPLE)

_her_as_them = r"(?=\s*(?:[.,!?;:]|$)|\s+(?:and|or|to|with|in|on|at|for|from|by|while|as)\b)"

RULES = [
    (rf"\ban ({_person})\b", "a person"),
    (rf"\b({_people})\b", "people"),
    (rf"\b({_person})\b", "person"),
    (r"\b(he|she) is\b", "they are"),
    (r"\b(he|she) was\b", "they were"),
    (r"\b(he|she) has\b", "they have"),
    (r"\b(he|she) does\b", "they do"),
    (r"\b(he|she)'s\b", "they're"),
    (r"\b(he|she)\b", "they"),
    (r"\b(himself|herself)\b", "themselves"),
    (r"\bhers\b", "theirs"),
    (r"\bhis\b", "their"),
    (r"\bhim\b", "them"),
    (rf"\bher\b{_her_as_them}", "them"),
    (r"\bher\b", "their"),
]


def _keep_case(repl):
    def sub(m):
        return repl[0].upper() + repl[1:] if m.group(0)[0].isupper() else repl
    return sub


def normalize(text):
    text = str(text)
    for pattern, repl in RULES:
        text = re.sub(pattern, _keep_case(repl), text, flags=re.I)
    return text