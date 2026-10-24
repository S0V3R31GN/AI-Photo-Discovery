import re

PERSON = ["woman", "man", "lady", "gentleman", "guy", "girl", "boy", "kid", "child",
          "adult", "teen", "teenager", "toddler", "baby", "infant"]
PEOPLE = ["women", "men", "ladies", "gentlemen", "guys", "girls", "boys", "kids", "children",
          "adults", "teens", "teenagers", "toddlers", "babies", "infants"]

_person = "|".join(PERSON)
_people = "|".join(PEOPLE)

RULES = [
    (rf"\ban ({_person})\b", "a person"),
    (rf"\b({_people})\b", "people"),
    (rf"\b({_person})\b", "person"),
]


def normalize(text):
    text = str(text)
    for pattern, repl in RULES:
        text = re.sub(pattern, repl, text, flags=re.I)
    return text