BASE_FILE_NAME = "russian_nouns_5_letters.txt"

WORDS = None


def get_words() -> list:
    global WORDS
    if not WORDS:
        with open(BASE_FILE_NAME, "r") as f_base:
            WORDS = [line.strip() for line in f_base]
    return WORDS


def check_mask(mask: str, word: str) -> bool:
    assert len(mask) == len(word)
    for ind, mask_letter in enumerate(mask):
        if mask_letter == "*":
            continue
        elif mask_letter != word[ind]:
            return False
    return True


def guess(yes_letters: str = "", no_letters: str = "", word_mask: str = "*****") -> str:
    yes_letters = set(yes_letters.lower())
    no_letters = set(no_letters.lower())
    word_mask = word_mask.lower()

    # Fix intersection
    no_letters = no_letters - yes_letters

    word_counter = 0

    result = ""
    for word in get_words():
        if any([letter in word for letter in no_letters]):
            continue
        if all([letter in word for letter in yes_letters]):
            if check_mask(word_mask, word):
                word_counter += 1
                result += f"{word_counter:0>2}) {word}\n"
    return result.strip()
