"""Detecting botanical mentions in regulatory free text, and classifying
what kind of adulteration event a record describes.

Two deliberately conservative design choices:

**Detection is dictionary-based, not inferred.** A curated vocabulary of
botanical names — binomials, genera and the common names that appear on
supplement labels — is matched against record text with word boundaries.
This under-detects: a botanical absent from the vocabulary is missed. The
alternative, treating any capitalised binomial-shaped token as a plant,
over-detects badly on firm names and product brands ("Nature's Bounty",
"Garden of Life"), and the resulting false positives are invisible in
aggregate. Under-detection is measurable and can be stated; over-detection
contaminates the record silently.

**Adulteration type is assigned from explicit language only.** A record whose
text does not state the nature of the problem is classified `unspecified`
rather than guessed from context. In this domain the difference between
substitution and contamination is the finding, not a detail.

The vocabulary here is a seed list covering botanicals recurrent in US
enforcement actions. It is intended to be extended; `docs/VOCABULARY.md`
explains how, and every count BOTREG reports names the vocabulary version
used, since the vocabulary is part of the method rather than an input to it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VOCABULARY_VERSION = "0.1.0"

# Seed vocabulary. Keys are the canonical scientific name where one exists;
# values are surface forms seen in labels and enforcement text.
BOTANICAL_TERMS: dict[str, list[str]] = {
    # --- stimulants and weight-loss botanicals -----------------------------
    "Ephedra sinica": ["ephedra", "ma huang", "ma-huang", "ephedra sinica"],
    "Citrus aurantium": ["bitter orange", "citrus aurantium", "synephrine",
                         "advantra"],
    "Acacia rigidula": ["acacia rigidula", "blackbrush acacia"],
    "Garcinia gummi-gutta": ["garcinia", "garcinia cambogia", "garcinia gummi-gutta",
                             "hydroxycitric acid", "malabar tamarind"],
    "Hoodia gordonii": ["hoodia", "hoodia gordonii"],
    "Opuntia": ["opuntia", "prickly pear", "nopal"],
    "Paullinia cupana": ["guarana", "paullinia cupana"],
    "Ilex paraguariensis": ["yerba mate", "yerba-mate", "ilex paraguariensis"],
    "Ilex": ["ilex"],
    "Camellia sinensis": ["green tea", "camellia sinensis", "green tea extract",
                          "egcg", "black tea", "oolong"],
    "Coffea": ["green coffee bean", "coffea", "chlorogenic acid"],

    # --- cognition, mood, sleep -------------------------------------------
    "Ginkgo biloba": ["ginkgo", "ginko", "ginkgo biloba", "gingko"],
    "Styphnolobium japonicum": ["sophora japonica", "styphnolobium japonicum",
                                "japanese pagoda tree", "pagoda tree"],
    "Hypericum perforatum": ["st john's wort", "st. john's wort", "st johns wort",
                             "hypericum perforatum"],
    "Hypericum": ["hypericum"],
    "Bacopa monnieri": ["bacopa", "bacopa monnieri", "brahmi", "water hyssop"],
    "Bacopa": ["bacopa species"],
    "Centella asiatica": ["gotu kola", "centella asiatica"],
    "Centella": ["centella"],
    "Valeriana officinalis": ["valerian", "valeriana officinalis"],
    "Valeriana": ["valeriana"],
    "Passiflora incarnata": ["passionflower", "passion flower", "passiflora incarnata",
                             "maypop"],
    "Passiflora": ["passiflora"],
    "Piper methysticum": ["kava", "kava kava", "kava-kava", "piper methysticum"],
    "Piper": ["piper species"],
    "Matricaria chamomilla": ["chamomile", "german chamomile", "matricaria",
                              "matricaria chamomilla", "matricaria recutita"],
    "Anthemis": ["anthemis", "roman chamomile", "chamaemelum nobile"],
    "Griffonia simplicifolia": ["griffonia", "griffonia simplicifolia", "5-htp"],
    "Rhodiola rosea": ["rhodiola", "rhodiola rosea", "golden root", "roseroot",
                       "arctic root"],
    "Rhodiola crenulata": ["rhodiola crenulata"],
    "Withania somnifera": ["ashwagandha", "withania somnifera", "withanolide",
                           "indian ginseng", "winter cherry"],
    "Withania coagulans": ["withania coagulans"],
    "Sceletium tortuosum": ["kanna", "sceletium tortuosum"],
    "Mitragyna speciosa": ["kratom", "mitragyna speciosa", "mitragynine",
                           "7-hydroxymitragynine"],
    "Cannabis sativa": ["cannabis", "cannabis sativa", "hemp", "cbd",
                        "cannabidiol", "delta-8", "delta 8"],

    # --- adaptogens and ginsengs ------------------------------------------
    "Panax ginseng": ["panax ginseng", "asian ginseng", "korean ginseng",
                      "red ginseng"],
    "Panax quinquefolius": ["american ginseng", "panax quinquefolius"],
    "Eleutherococcus senticosus": ["eleuthero", "siberian ginseng",
                                   "eleutherococcus", "eleutherococcus senticosus",
                                   "acanthopanax"],
    "Periploca sepium": ["periploca", "periploca sepium", "silk vine"],
    "Codonopsis pilosula": ["codonopsis", "codonopsis pilosula", "dang shen"],
    "Astragalus membranaceus": ["astragalus membranaceus", "huang qi", "huangqi"],
    "Astragalus": ["astragalus"],
    "Eurycoma longifolia": ["tongkat ali", "eurycoma longifolia", "longjack"],
    "Eurycoma": ["eurycoma"],
    "Schisandra chinensis": ["schisandra", "schizandra", "schisandra chinensis",
                             "wu wei zi"],
    "Schisandra sphenanthera": ["schisandra sphenanthera"],
    "Lycium barbarum": ["goji", "goji berry", "wolfberry", "lycium barbarum"],
    "Lycium chinense": ["lycium chinense"],

    # --- women's health ----------------------------------------------------
    "Actaea racemosa": ["black cohosh", "actaea racemosa", "cimicifuga racemosa",
                        "cimicifuga"],
    "Actaea dahurica": ["actaea dahurica", "cimicifuga dahurica"],
    "Actaea cimicifuga": ["actaea cimicifuga", "cimicifuga foetida"],
    "Vitex agnus-castus": ["chaste tree", "chasteberry", "vitex agnus-castus",
                           "vitex"],
    "Vitex": ["vitex species"],
    "Dioscorea villosa": ["wild yam", "dioscorea villosa"],
    "Dioscorea": ["dioscorea"],
    "Caulophyllum thalictroides": ["blue cohosh", "caulophyllum thalictroides"],
    "Caulophyllum": ["caulophyllum"],
    "Angelica sinensis": ["dong quai", "dang gui", "angelica sinensis"],
    "Angelica": ["angelica"],
    "Trigonella foenum-graecum": ["fenugreek", "trigonella foenum-graecum"],
    "Trigonella": ["trigonella"],

    # --- men's health ------------------------------------------------------
    "Serenoa repens": ["saw palmetto", "serenoa repens", "serenoa"],
    "Elaeis guineensis": ["palm oil", "elaeis guineensis", "oil palm"],
    "Cocos nucifera": ["coconut oil", "cocos nucifera"],
    "Prunus africana": ["pygeum", "prunus africana", "african cherry"],
    "Prunus": ["prunus"],
    "Pausinystalia johimbe": ["yohimbe", "yohimbine", "pausinystalia",
                              "pausinystalia johimbe", "corynanthe"],
    "Tribulus terrestris": ["tribulus", "tribulus terrestris", "puncture vine"],
    "Tribulus": ["tribulus species"],
    "Epimedium": ["epimedium", "horny goat weed", "icariin", "yin yang huo"],
    "Turnera diffusa": ["damiana", "turnera diffusa"],
    "Turnera": ["turnera"],

    # --- immune, antimicrobial --------------------------------------------
    "Echinacea purpurea": ["echinacea", "echinacea purpurea", "purple coneflower",
                           "coneflower"],
    "Parthenium integrifolium": ["parthenium integrifolium", "missouri snakeroot",
                                 "prairie dock"],
    "Sambucus nigra": ["elderberry", "elder berry", "sambucus nigra", "sambucus",
                       "black elder"],
    "Sambucus canadensis": ["sambucus canadensis", "american elder"],
    "Hydrastis canadensis": ["goldenseal", "golden seal", "hydrastis",
                             "hydrastis canadensis", "hydrastine"],
    "Coptis chinensis": ["coptis", "coptis chinensis", "huang lian", "goldthread"],
    "Berberis aristata": ["berberis aristata", "indian barberry", "tree turmeric"],
    "Berberis": ["berberis", "berberine", "barberry"],
    "Allium sativum": ["garlic", "allium sativum", "allicin"],
    "Sutherlandia frutescens": ["sutherlandia", "cancer bush"],
    "Uncaria tomentosa": ["cat's claw", "cats claw", "uncaria tomentosa",
                          "una de gato"],
    "Uncaria guianensis": ["uncaria guianensis"],

    # --- anti-inflammatory, joint -----------------------------------------
    "Curcuma longa": ["turmeric", "curcuma longa", "curcumin", "curcuminoid"],
    "Curcuma zedoaria": ["curcuma zedoaria", "zedoary", "white turmeric"],
    "Boswellia serrata": ["boswellia serrata", "indian frankincense",
                          "boswellic acid"],
    "Boswellia": ["boswellia", "frankincense", "olibanum"],
    "Zingiber officinale": ["ginger", "zingiber officinale", "gingerol"],
    "Harpagophytum procumbens": ["devil's claw", "devils claw",
                                 "harpagophytum procumbens", "harpagoside"],
    "Harpagophytum zeyheri": ["harpagophytum zeyheri"],
    "Commiphora wightii": ["guggul", "commiphora wightii", "commiphora mukul",
                           "guggulsterone"],
    "Commiphora": ["commiphora", "myrrh"],
    "Salix": ["white willow", "willow bark", "salix", "salicin"],
    "Arnica montana": ["arnica", "arnica montana"],
    "Heterotheca inuloides": ["heterotheca inuloides", "mexican arnica"],
    "Tanacetum parthenium": ["feverfew", "tanacetum parthenium", "parthenolide"],
    "Tanacetum": ["tanacetum"],
    "Petasites hybridus": ["butterbur", "petasites hybridus", "petadolex"],
    "Petasites": ["petasites"],

    # --- liver, kidney, detox ---------------------------------------------
    "Silybum marianum": ["milk thistle", "silybum marianum", "silymarin",
                         "silibinin"],
    "Silybum": ["silybum"],
    "Cynara scolymus": ["artichoke", "cynara scolymus", "artichoke leaf"],
    "Taraxacum officinale": ["dandelion", "taraxacum officinale"],
    "Peumus boldus": ["boldo", "peumus boldus", "boldine"],
    "Peumus": ["peumus"],
    "Stephania tetrandra": ["stephania tetrandra", "han fang ji", "fangji",
                            "fang ji"],
    "Aristolochia fangchi": ["aristolochia fangchi", "guang fang ji"],
    "Aristolochia manshuriensis": ["aristolochia manshuriensis", "guan mu tong"],
    "Aristolochia": ["aristolochia", "aristolochic acid", "birthwort"],
    "Clematis armandii": ["clematis armandii", "chuan mu tong", "mu tong"],
    "Polygonum multiflorum": ["he shou wu", "fo-ti", "polygonum multiflorum",
                              "reynoutria multiflora"],
    "Polygonum": ["polygonum"],

    # --- urinary, prostate -------------------------------------------------
    "Vaccinium macrocarpon": ["cranberry", "vaccinium macrocarpon"],
    "Arctostaphylos uva-ursi": ["uva ursi", "uva-ursi", "bearberry",
                                "arctostaphylos uva-ursi", "arbutin"],
    "Vaccinium vitis-idaea": ["lingonberry", "vaccinium vitis-idaea", "cowberry"],
    "Urtica dioica": ["nettle", "stinging nettle", "urtica dioica"],
    "Urtica urens": ["urtica urens", "dwarf nettle"],
    "Equisetum arvense": ["horsetail", "equisetum arvense", "shavegrass"],
    "Equisetum palustre": ["equisetum palustre", "marsh horsetail"],

    # --- antioxidant fruits and extracts ----------------------------------
    "Vaccinium myrtillus": ["bilberry", "vaccinium myrtillus", "european blueberry"],
    "Vaccinium corymbosum": ["blueberry", "vaccinium corymbosum"],
    "Vitis vinifera": ["grape seed", "grape seed extract", "vitis vinifera",
                       "resveratrol", "opc"],
    "Arachis hypogaea": ["peanut skin", "peanut skin extract", "arachis hypogaea"],
    "Punica granatum": ["pomegranate", "punica granatum", "punicalagin",
                        "ellagic acid"],
    "Euterpe oleracea": ["acai", "acai berry", "euterpe oleracea"],
    "Myrciaria dubia": ["camu camu", "camu-camu", "myrciaria dubia"],
    "Hippophae rhamnoides": ["sea buckthorn", "seabuckthorn", "hippophae rhamnoides"],
    "Hippophae": ["hippophae"],
    "Adansonia digitata": ["baobab", "adansonia digitata"],
    "Adansonia": ["adansonia"],
    "Morinda citrifolia": ["noni", "morinda citrifolia"],
    "Morinda": ["morinda"],
    "Aronia melanocarpa": ["aronia", "chokeberry", "aronia melanocarpa"],
    "Amaranthus": ["amaranth", "amaranthus", "amaranth dye"],
    "Garcinia mangostana": ["mangosteen", "garcinia mangostana", "xanthone"],
    "Garcinia": ["garcinia species"],
    "Annona muricata": ["graviola", "soursop", "annona muricata"],

    # --- culinary and spice ------------------------------------------------
    "Cinnamomum verum": ["ceylon cinnamon", "cinnamomum verum", "true cinnamon",
                         "cinnamomum zeylanicum"],
    "Cinnamomum cassia": ["cassia", "cassia cinnamon", "cinnamomum cassia",
                          "chinese cinnamon"],
    "Cinnamomum": ["cinnamon", "cinnamomum"],
    "Crocus sativus": ["saffron", "crocus sativus", "crocin", "safranal"],
    "Carthamus tinctorius": ["safflower", "carthamus tinctorius"],
    "Origanum vulgare": ["oregano", "origanum vulgare", "oregano leaf"],
    "Olea europaea": ["olive leaf", "olea europaea", "oleuropein"],
    "Cistus": ["cistus", "rock rose", "rockrose"],
    "Rhus": ["sumac", "rhus"],
    "Myrtus communis": ["myrtle", "myrtus communis"],
    "Capsicum annuum": ["cayenne", "capsicum", "capsaicin", "capsicum annuum"],
    "Piper nigrum": ["black pepper", "piper nigrum", "piperine", "bioperine"],
    "Rosmarinus officinalis": ["rosemary", "rosmarinus officinalis",
                               "salvia rosmarinus"],
    "Mentha piperita": ["peppermint", "mentha piperita", "menthol"],
    "Salvia officinalis": ["sage", "salvia officinalis"],
    "Thymus vulgaris": ["thyme", "thymus vulgaris", "thymol"],
    "Syzygium aromaticum": ["clove", "syzygium aromaticum", "eugenol"],
    "Elettaria cardamomum": ["cardamom", "elettaria cardamomum"],
    "Foeniculum vulgare": ["fennel", "foeniculum vulgare"],

    # --- laxatives and GI --------------------------------------------------
    "Senna alexandrina": ["senna", "cassia senna", "senna alexandrina",
                          "sennoside"],
    "Rheum palmatum": ["chinese rhubarb", "rheum palmatum", "da huang"],
    "Rheum rhaponticum": ["rhapontic rhubarb", "rheum rhaponticum", "rhaponticin"],
    "Aloe vera": ["aloe vera", "aloe barbadensis", "acemannan"],
    "Aloe": ["aloe"],
    "Plantago ovata": ["psyllium", "plantago ovata", "ispaghula"],
    "Ulmus rubra": ["slippery elm", "ulmus rubra"],
    "Glycyrrhiza glabra": ["licorice", "liquorice", "glycyrrhiza glabra",
                           "glycyrrhizin", "dgl"],
    "Zingiber": ["zingiber"],

    # --- pyrrolizidine-alkaloid risk ---------------------------------------
    "Symphytum officinale": ["comfrey", "symphytum officinale", "knitbone"],
    "Symphytum": ["symphytum"],
    "Tussilago farfara": ["coltsfoot", "tussilago farfara"],
    "Senecio": ["senecio", "ragwort", "groundsel"],
    "Borago officinalis": ["borage", "borago officinalis", "starflower"],

    # --- hepatotoxicity-relevant substitutes -------------------------------
    "Scutellaria lateriflora": ["skullcap", "scullcap", "scutellaria lateriflora",
                                "american skullcap"],
    "Scutellaria baicalensis": ["scutellaria baicalensis", "baical skullcap",
                                "huang qin", "baicalin"],
    "Teucrium canadense": ["teucrium canadense", "american germander",
                           "wood sage"],
    "Teucrium chamaedrys": ["teucrium chamaedrys", "wall germander"],
    "Teucrium": ["teucrium", "germander"],

    # --- fungi (traded as botanicals) --------------------------------------
    "Cordyceps sinensis": ["cordyceps sinensis", "ophiocordyceps sinensis",
                           "dong chong xia cao"],
    "Cordyceps militaris": ["cordyceps militaris", "cordycepin"],
    "Cordyceps": ["cordyceps"],
    "Ganoderma lucidum": ["reishi", "ganoderma lucidum", "lingzhi", "ling zhi"],
    "Ganoderma": ["ganoderma"],
    "Lentinula edodes": ["shiitake", "lentinula edodes", "lentinan"],
    "Hericium erinaceus": ["lion's mane", "lions mane", "hericium erinaceus"],
    "Trametes versicolor": ["turkey tail", "trametes versicolor", "coriolus"],
    "Inonotus obliquus": ["chaga", "inonotus obliquus"],

    # --- algae and cyanobacteria -------------------------------------------
    "Arthrospira platensis": ["spirulina", "arthrospira platensis"],
    "Chlorella": ["chlorella"],
    "Ascophyllum nodosum": ["kelp", "bladderwrack", "ascophyllum nodosum",
                            "fucus vesiculosus"],

    # --- other commonly traded ---------------------------------------------
    "Lepidium meyenii": ["maca", "lepidium meyenii"],
    "Lepidium": ["lepidium"],
    "Moringa oleifera": ["moringa", "moringa oleifera"],
    "Salvia miltiorrhiza": ["danshen", "dan shen", "salvia miltiorrhiza"],
    "Salvia": ["salvia species"],
    "Camellia oleifera": ["camellia oleifera", "tea seed oil"],
    "Serenoa": ["serenoa species"],
    "Tabebuia": ["pau d'arco", "pau darco", "tabebuia", "lapacho"],
    "Ptychopetalum olacoides": ["muira puama", "ptychopetalum olacoides"],
    "Erythroxylum catuaba": ["catuaba"],
    "Butea superba": ["butea superba", "red kwao krua"],
    "Pueraria mirifica": ["pueraria mirifica", "white kwao krua", "kudzu"],
    "Gymnema sylvestre": ["gymnema", "gymnema sylvestre"],
    "Momordica charantia": ["bitter melon", "momordica charantia", "karela"],
    "Cissus quadrangularis": ["cissus", "cissus quadrangularis"],
    "Coleus forskohlii": ["forskolin", "coleus forskohlii", "plectranthus barbatus"],
    "Nigella sativa": ["black seed", "black cumin", "nigella sativa",
                       "thymoquinone"],
    "Melaleuca alternifolia": ["tea tree", "tea tree oil", "melaleuca alternifolia"],
    "Calendula officinalis": ["calendula", "calendula officinalis", "marigold"],
    "Tagetes": ["tagetes", "marigold flower"],
    "Ginkgoaceae": ["ginkgolide"],

    # --- species central to documented US substitution cases ---------------
    # Added after the first production run returned zero substitution events:
    # the FDA tejocote/yellow oleander advisory uses explicit "substituted
    # with" language, but neither species was in the vocabulary, so those
    # records were undetectable rather than misclassified.
    "Crataegus mexicana": ["tejocote", "raiz de tejocote", "crataegus mexicana",
                           "mexican hawthorn"],
    "Crataegus": ["hawthorn", "crataegus"],
    "Cascabela thevetia": ["yellow oleander", "cascabela thevetia",
                           "thevetia peruviana", "thevetin"],
    "Nerium oleander": ["oleander", "nerium oleander"],
    "Pausinystalia": ["pausinystalia species"],
    "Digitalis": ["digitalis", "foxglove"],
    "Atropa belladonna": ["belladonna", "atropa belladonna", "deadly nightshade"],
    "Datura": ["datura", "jimsonweed", "jimson weed"],
    "Colchicum autumnale": ["colchicum", "autumn crocus", "colchicine"],
    "Gelsemium": ["gelsemium", "yellow jessamine"],
    "Illicium anisatum": ["japanese star anise", "illicium anisatum"],
    "Illicium verum": ["star anise", "illicium verum", "chinese star anise"],
    "Stephania": ["stephania", "fang ji species"],
    "Akebia": ["akebia", "mu tong species"],
    "Asarum": ["asarum", "wild ginger", "xi xin"],
    "Sida cordifolia": ["sida cordifolia", "bala"],
    "Convallaria majalis": ["lily of the valley", "convallaria majalis"],
    "Aconitum": ["aconite", "aconitum", "monkshood", "fu zi", "chuan wu"],
    "Strychnos nux-vomica": ["nux vomica", "strychnos", "strychnine"],
    "Brazil seed": ["brazil seed", "semilla de brasil"],
}

# Language that identifies the kind of adulteration. Order matters: the
# first category whose pattern matches wins, so more specific findings are
# tested before more general ones.
ADULTERATION_PATTERNS: list[tuple[str, list[str]]] = [
    ("substitution", [
        # NOTE: the bare word "adulterated" is deliberately NOT here. In FDA
        # usage it is a legal term of art under FD&C Act 402 meaning broadly
        # non-compliant -- it covers contamination, undeclared ingredients and
        # much else. Treating it as evidence of species substitution inflates
        # the substitution count, which is precisely the headline figure of a
        # botanical adulteration dataset. Substitution must be stated.
        r"\bsubstitut", r"\bnot the (?:declared|labeled|labelled)",
        # FDA's other standard construction, from the live tejocote
        # advisory: "contain yellow oleander (Thevetia peruviana) instead of
        # the labeled ingredient". Requiring "the labeled/declared" after
        # keeps this distinct from plant-part language ("leaf instead of
        # root"), which is classified separately.
        r"\b(?:instead of|in place of|rather than) the "
        r"(?:labeled|labelled|declared|stated|intended)\b",
        r"\b(?:instead of|in place of) the (?:labeled|labelled|declared) "
        r"(?:ingredient|botanical|species|plant)",
        r"\bdifferent species\b", r"\bspecies substitution\b",
        r"\bmisidentif", r"\bwrong (?:species|plant|botanical)\b",
        r"\bplant material .{0,30}\bnot\b", r"\bDNA (?:test|barcod)",
    ]),
    ("undeclared_ingredient", [
        r"\bundeclared\b", r"\bnot declared\b", r"\bfailure to declare\b",
        r"\bhidden (?:drug|ingredient)", r"\bunlabeled\b", r"\bunlabelled\b",
        r"\bcontains? (?:the )?undeclared\b", r"\bspiked with\b",
    ]),
    ("contamination", [
        r"\bcontaminat", r"\blead\b", r"\bcadmium\b", r"\bmercury\b",
        r"\barsenic\b", r"\bheavy metal", r"\bsalmonella\b", r"\bE\. ?coli\b",
        r"\bmicrobial\b", r"\bpesticide", r"\bmold\b", r"\bmould\b",
        r"\baflatoxin", r"\bforeign material\b",
    ]),
    ("unapproved_ingredient", [
        r"\bunapproved\b", r"\bnew dietary ingredient\b", r"\bNDI\b",
        r"\bnot (?:a )?(?:generally recognized|GRAS)", r"\bprohibited\b",
        r"\bbanned\b",
    ]),
    ("plant_part_substitution", [
        # 21 CFR 101.36(b)(3) requires the part of the plant to be declared,
        # and 21 USC 343(s)(2)(C) makes a supplement misbranded if the
        # labelling fails to identify it. Plant-part identity is therefore a
        # distinct regulatory failure from species identity: the species may
        # be correct while the represented part is not -- root versus leaf in
        # ashwagandha, root versus aerial in nettle, root versus stem
        # peelings in kava.
        r"\bplant part\b", r"\bpart of the plant\b",
        # allow a short qualifier between the part and the contrast phrase:
        # "stem peelings rather than root", "leaf powder instead of root"
        r"\b(?:root|leaf|leaves|aerial|stem|bark|rhizome|flower|seed|fruit)"
        r"\s+(?:\w+\s+){0,2}?(?:instead of|in place of|rather than|substituted)",
        r"\bsubstitut\w*\s+(?:the\s+)?"
        r"(?:root|leaf|leaves|aerial|stem|bark|rhizome)\b",
        r"\bfail(?:ure|s|ed)? to (?:declare|identify) the (?:plant )?part",
        r"\bpart not (?:declared|identified|specified)\b",
        r"\baerial parts? (?:instead|rather)",
    ]),
    ("mislabeling", [
        r"\bmisbrand", r"\bmislabel", r"\bfalse (?:or misleading )?(?:label|claim)",
        r"\bincorrect label", r"\blabeling (?:error|violation)",
    ]),
]

_COMPILED_ADULTERATION = [
    (label, [re.compile(p, re.IGNORECASE) for p in patterns])
    for label, patterns in ADULTERATION_PATTERNS
]


def _term_pattern(surface: str) -> re.Pattern:
    """Word-boundary pattern for a surface form.

    Boundaries matter: without them 'aloe' matches inside 'aloeswood' and
    'cbd' matches inside arbitrary product codes.
    """
    escaped = re.escape(surface).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)


_COMPILED_TERMS: list[tuple[str, str, re.Pattern]] = [
    (canonical, surface, _term_pattern(surface))
    for canonical, surfaces in BOTANICAL_TERMS.items()
    for surface in surfaces
]
# Longer surface forms first, so 'siberian ginseng' wins over 'ginseng'.
_COMPILED_TERMS.sort(key=lambda t: len(t[1]), reverse=True)


@dataclass(frozen=True)
class TermHit:
    canonical: str          # canonical scientific name from the vocabulary
    surface: str            # the form actually found in the text
    context: str            # surrounding characters, for hand verification
    start: int


def find_botanicals(text: str, context_chars: int = 70) -> list[TermHit]:
    """Find botanical mentions, one hit per canonical name.

    Returns at most one hit per canonical botanical even if several surface
    forms appear, so that a record naming "ginkgo" and "Ginkgo biloba" counts
    once rather than twice.
    """
    if not text:
        return []
    hits: dict[str, TermHit] = {}
    claimed: list[tuple[int, int]] = []
    for canonical, surface, pattern in _COMPILED_TERMS:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            # skip a match already covered by a longer term
            if any(s <= span[0] and span[1] <= e for s, e in claimed):
                continue
            claimed.append(span)
            if canonical in hits:
                continue
            lo = max(0, m.start() - context_chars)
            hi = min(len(text), m.end() + context_chars)
            hits[canonical] = TermHit(
                canonical=canonical, surface=m.group(0),
                context=text[lo:hi].replace("\n", " ").strip(), start=m.start())
    return sorted(hits.values(), key=lambda h: h.start)


def classify_adulteration(text: str) -> str:
    """Classify the adulteration type from explicit language only.

    Returns 'unspecified' when the text does not state the nature of the
    problem, rather than inferring one.
    """
    if not text:
        return "unspecified"
    for label, patterns in _COMPILED_ADULTERATION:
        if any(p.search(text) for p in patterns):
            return label
    return "unspecified"


def vocabulary_size() -> tuple[int, int]:
    """(distinct canonical botanicals, distinct surface forms)."""
    return len(BOTANICAL_TERMS), sum(len(v) for v in BOTANICAL_TERMS.values())
