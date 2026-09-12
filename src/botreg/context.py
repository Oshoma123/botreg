"""Classifying whether a regulatory record concerns a dietary supplement.

Why this module exists
----------------------

openFDA's `food/enforcement` endpoint covers *all* food recalls, and culinary
botanicals appear as ingredients throughout ordinary food. A first live run of
BAER over 500 food recalls returned, among its most frequent botanicals,
*Cinnamomum* from cinnamon raisin bagels, *Allium sativum* from garlic
cheddar, *Cynara scolymus* from spinach artichoke dip, and *Vaccinium
macrocarpon* from oatmeal cranberry cookie dough.

Every one of those detections is *correct* — the records do mention those
botanicals — and every one is irrelevant to botanical adulteration in dietary
supplements. Left unfiltered they would dominate the record and make BAER a
list of baked goods.

The response is to classify rather than discard. A lead-contaminated turmeric
*spice* is genuinely relevant to botanical adulteration even though it is not
a supplement; a cinnamon bagel is not. Recording the context on every event
lets a user restrict to the population they mean, and makes the size of the
food population visible instead of hidden.

California's Proposition 65 register widens the problem further: it covers
all consumer products, so a first live run over 5,398 notices returned aloe
vera gel, tea tree peel-off masks, aloe sheet masks and shave foam -- all
Diethanolamine notices on **cosmetics**. Botanicals are ubiquitous in
personal care, and those records are as irrelevant to supplement adulteration
as the bagels were.

Four outcomes:

  ``supplement``  Explicit dietary-supplement language or dosage form
  ``food``        Explicit prepared-food language
  ``cosmetic``    Personal-care product language
  ``ambiguous``   None of the above -- bulk botanical powders and spices
                  frequently land here, and that is honest

The classifier is deliberately conservative: `supplement` requires a positive
marker, so the supplement population is a floor rather than an estimate.
"""
from __future__ import annotations

import re

CONTEXT_VERSION = "0.1.0"

# Explicit dietary-supplement language and dosage forms.
_SUPPLEMENT_PATTERNS = [
    r"\bdietary supplement",
    r"\bsupplement facts\b",
    r"\bnutritional supplement",
    r"\bherbal supplement",
    r"\bcapsule", r"\bcaplet", r"\bsoftgel", r"\bsoft gel\b",
    r"\bvegcap", r"\bvcap\b",
    r"\btablet",
    r"\bgel ?cap",
    r"\bstandardized extract\b",
    r"\bstandardised extract\b",
    r"\bherbal (?:tincture|extract|blend|formula)",
    r"\btincture\b",
    r"\bper serving\b.{0,40}\bmg\b",
    r"\bproprietary blend\b",
    r"\bnutraceutical",
    r"\bmultivitamin",
    r"\bVit/Min/Prot/Unconv Diet",     # CAERS industry_name for supplements
    r"\bdiet(?:ary)? conventional food/meal replacement\b",
]

# Prepared-food language. Presence alone is not decisive; a supplement marker
# outranks it, since "supplement bar" style products exist.
_FOOD_PATTERNS = [
    r"\bbagel", r"\bbread\b", r"\bmuffin", r"\bcookie", r"\bcake\b",
    r"\bbrownie", r"\bpastry", r"\bcracker", r"\bpretzel", r"\bcereal\b",
    r"\bgranola\b", r"\btortilla", r"\bpizza\b", r"\bsandwich",
    r"\bcheese\b", r"\bcheddar\b", r"\byogurt", r"\bice cream\b",
    r"\bbutter\b", r"\bmilk\b", r"\bcream\b",
    r"\bdip\b", r"\bsalsa\b", r"\bsauce\b", r"\bdressing\b", r"\bhummus\b",
    r"\bsoup\b", r"\bsalad\b", r"\bentree\b", r"\bmeal\b", r"\bburrito",
    r"\bchicken\b", r"\bbeef\b", r"\bpork\b", r"\bturkey\b", r"\bsausage",
    r"\bseafood\b", r"\bshrimp\b", r"\bsalmon\b", r"\btuna\b",
    r"\bchocolate\b", r"\bcandy\b", r"\bsnack\b", r"\bchips\b",
    r"\bfrozen (?:pucks|dough|entree)", r"\bcookie dough\b",
    r"\bbeverage\b", r"\bsoda\b", r"\bjuice\b", r"\bsmoothie\b",
    r"\bcoffee creamer\b", r"\bsyrup\b", r"\bjam\b", r"\bjelly\b",
    r"\bnoodle", r"\bpasta\b", r"\brice\b", r"\bflour\b",
    r"\bseasoning\b", r"\bspice (?:blend|mix)\b", r"\bmarinade\b",
]

# Personal-care product language. Prop 65 notices on cosmetics are numerous
# and botanicals are ubiquitous in them.
_COSMETIC_PATTERNS = [
    r"\bshampoo\b", r"\bconditioner\b", r"\bbody wash\b", r"\bshower gel\b",
    r"\bsoap\b", r"\bcleanser\b", r"\bscrub\b", r"\btoner\b",
    r"\blotion\b", r"\bmoisturi[sz]er\b", r"\bbody butter\b",
    r"\bface (?:mask|cream|oil|serum)", r"\bsheet mask", r"\bpeel-?off mask",
    r"\bmask(?:s)?\b(?!.\bingredient)", r"\bserum\b",
    r"\bshave (?:foam|gel|cream)", r"\bshaving\b", r"\baftershave\b",
    r"\bdeodorant\b", r"\bantiperspirant\b",
    r"\bsunscreen\b", r"\bspf\b", r"\bself[- ]tan",
    r"\blip (?:gloss|balm|stick)", r"\blipstick\b", r"\bmascara\b",
    r"\bfoundation\b", r"\bconcealer\b", r"\beyeliner\b", r"\bmakeup\b",
    r"\bnail (?:polish|lacquer)", r"\bhair (?:dye|color|colour|spray|gel)",
    r"\bperfume\b", r"\bcologne\b", r"\bfragrance\b", r"\bbody spray\b",
    r"\bbath bomb", r"\bbubble bath\b", r"\bhand sanitizer\b",
    # Bare 'gel' is safe here only because the supplement patterns are
    # tested first and already claim 'gel cap' / 'softgel'.
    r"\bgel\b",
    # Diethanolamine and cocamide DEA are personal-care surfactant
    # chemistry; a Prop 65 notice naming them is almost always cosmetic.
    r"\bdiethanolamine\b", r"\bcocamide\b", r"\bDEA\b",
    r"\bcosmetic", r"\bpersonal care\b", r"\btopical\b", r"\bointment\b",
    r"\bsalve\b", r"\bbalm\b", r"\bwipes?\b", r"\bdiaper cream\b",
]

_SUPPLEMENT_RE = [re.compile(p, re.IGNORECASE) for p in _SUPPLEMENT_PATTERNS]
_COSMETIC_RE = [re.compile(p, re.IGNORECASE) for p in _COSMETIC_PATTERNS]
_FOOD_RE = [re.compile(p, re.IGNORECASE) for p in _FOOD_PATTERNS]

# Sources whose entire population is supplement-relevant regardless of text.
_SUPPLEMENT_SOURCES = {"dsld_label"}


def classify_context(text: str, source: str = "") -> str:
    """Return 'supplement', 'food', 'cosmetic', or 'ambiguous'.

    A supplement marker outranks the others: supplement bars and functional
    beverages carry food language too, and the supplement framing is the one
    that matters here. Cosmetic is tested before food because personal-care
    products borrow food words freely (body butter, sugar scrub, milk
    cleanser) while the reverse is rare.
    """
    if source in _SUPPLEMENT_SOURCES:
        return "supplement"
    if not text:
        return "ambiguous"
    if any(p.search(text) for p in _SUPPLEMENT_RE):
        return "supplement"
    if any(p.search(text) for p in _COSMETIC_RE):
        return "cosmetic"
    if any(p.search(text) for p in _FOOD_RE):
        return "food"
    return "ambiguous"


def is_supplement_context(text: str, source: str = "") -> bool:
    return classify_context(text, source) == "supplement"
