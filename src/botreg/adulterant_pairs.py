"""Documented adulterant-authentic species pairs in the botanical supplement trade.

Each entry records a botanical that is substituted for, adulterated with, or
confused with another, together with how the substitution presents and what
distinguishes the two analytically.

Why this table exists
---------------------

Detecting that a regulatory record mentions "skullcap" is weak evidence of
anything. Detecting that it mentions skullcap *and* germander, or that a
skullcap product was recalled for hepatotoxicity, is a substitution signal —
germander substitution for *Scutellaria lateriflora* is a documented cause of
hepatotoxicity. Encoding the pairs turns BAER from an index of botanical
mentions into an index of botanical adulteration signals.

Evidence classes
----------------

Pairs differ enormously in how well established they are, and collapsing that
distinction would be the same error as treating a GBIF fuzzy match as an
identification. Every pair carries one of:

  ``documented``  Repeatedly reported in peer-reviewed analytical literature,
                  pharmacopoeial monographs, or regulatory action. The
                  substitution is established.
  ``reported``    Reported in the literature or by testing programmes, but
                  less frequently or with less analytical confirmation.
  ``plausible``   Taxonomically or commercially plausible and named as a
                  concern in review literature, without a strong body of
                  confirmed market cases.

Nothing here is an assertion about any particular product or company. These
are documented *patterns* in the trade, drawn from the published analytical
literature; the `note` field names the mechanism or the reason it matters.

**Verify before citing.** Entries were compiled from domain literature and
each carries an evidence class, but citations have not been machine-verified
against live records. `docs/VOCABULARY.md` describes how to check and extend
them. Treat `plausible` entries in particular as leads rather than findings.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PAIRS_VERSION = "0.1.0"

SUBSTITUTION_MODES = {
    "substitution",        # adulterant sold as the authentic species
    "admixture",           # adulterant blended with the authentic species
    "misidentification",   # confusion in the supply chain, not necessarily intentional
    "undeclared_addition", # material added and not declared
    "chemical_spiking",    # non-botanical compound added to meet a marker assay
}

EVIDENCE_CLASSES = {"documented", "reported", "plausible"}


@dataclass(frozen=True)
class AdulterantPair:
    """One authentic -> adulterant relationship."""

    authentic: str                  # accepted scientific name
    adulterant: str                 # accepted scientific name, or a compound
    mode: str
    evidence: str
    plant_part: str = ""            # root, leaf, aerial, fruit, bark, whole
    concern: str = ""               # why it matters: toxicity, efficacy, economics
    detection: str = ""             # methods that distinguish them
    note: str = ""
    adulterant_is_botanical: bool = True

    def __post_init__(self):
        if self.mode not in SUBSTITUTION_MODES:
            raise ValueError(f"unknown mode {self.mode!r}")
        if self.evidence not in EVIDENCE_CLASSES:
            raise ValueError(f"unknown evidence class {self.evidence!r}")


P = AdulterantPair

ADULTERANT_PAIRS: list[AdulterantPair] = [
    # ---------------------------------------------------- toxicity-relevant
    P("Scutellaria lateriflora", "Teucrium canadense", "substitution", "documented",
      "aerial", "hepatotoxicity",
      "HPTLC; LC-MS marker profile; DNA barcoding",
      "Germander substitution for American skullcap is a documented cause of "
      "hepatotoxicity; germander contains hepatotoxic neo-clerodane diterpenes."),
    P("Scutellaria lateriflora", "Teucrium chamaedrys", "substitution", "documented",
      "aerial", "hepatotoxicity", "HPTLC; LC-MS; DNA barcoding",
      "Wall germander; withdrawn from several markets after hepatitis cases."),
    P("Stephania tetrandra", "Aristolochia fangchi", "misidentification", "documented",
      "root", "nephrotoxicity and urothelial carcinoma",
      "LC-MS for aristolochic acids; DNA barcoding",
      "The Belgian slimming-clinic cases: shared Chinese pinyin names "
      "(fangji) led to substitution; aristolochic acid is a Group 1 carcinogen."),
    P("Clematis armandii", "Aristolochia manshuriensis", "misidentification", "documented",
      "stem", "nephrotoxicity", "LC-MS for aristolochic acids",
      "Guan mu tong substituted for mu tong; same aristolochic acid mechanism."),
    P("Equisetum arvense", "Equisetum palustre", "admixture", "documented",
      "aerial", "toxicity: palustrine alkaloids",
      "Microscopy; alkaloid profiling; DNA barcoding",
      "Marsh horsetail is toxic to livestock and a recognised contaminant of "
      "field horsetail harvests."),
    P("Cinnamomum verum", "Cinnamomum cassia", "substitution", "documented",
      "bark", "coumarin hepatotoxicity at high intake",
      "Coumarin quantification by HPLC; microscopy",
      "Cassia is far cheaper and much higher in coumarin; commonly sold "
      "simply as 'cinnamon' in the US, where labelling does not require the "
      "distinction."),

    # ---------------------------------------------- economically motivated
    P("Eleutherococcus senticosus", "Periploca sepium", "substitution", "documented",
      "root bark", "efficacy; cardiac glycoside exposure",
      "HPTLC; LC-MS; DNA barcoding",
      "Silk vine root bark substituted for eleuthero; contains cardiac "
      "glycosides absent from the authentic material."),
    P("Vaccinium myrtillus", "Vaccinium corymbosum", "substitution", "documented",
      "fruit", "efficacy: anthocyanin profile",
      "Anthocyanin profiling by HPLC-DAD",
      "Cultivated blueberry substituted for wild bilberry; distinguishable by "
      "anthocyanin fingerprint."),
    P("Vaccinium myrtillus", "Amaranthus", "chemical_spiking", "documented",
      "fruit", "efficacy; dye adulteration",
      "HPLC-DAD anthocyanin profile; dye screening",
      "Bilberry extract adulterated with cheaper anthocyanin sources and "
      "synthetic dyes to meet colour or total-anthocyanin specifications.",
      ),
    P("Vitis vinifera", "Arachis hypogaea", "substitution", "documented",
      "seed / skin", "allergen risk; efficacy",
      "HPLC procyanidin profile; peanut allergen ELISA",
      "Peanut skin extract substituted for grape seed extract; introduces an "
      "undeclared major allergen."),
    P("Vaccinium macrocarpon", "Arachis hypogaea", "admixture", "reported",
      "fruit", "allergen risk; efficacy",
      "Proanthocyanidin (PAC) profiling; DMAC assay",
      "Peanut skin and grape material used to raise apparent PAC content."),
    P("Ginkgo biloba", "Styphnolobium japonicum", "chemical_spiking", "documented",
      "leaf", "efficacy; marker gaming",
      "Flavonol aglycone ratio; genistein/rutin markers by HPLC",
      "Rutin from Japanese pagoda tree, or free quercetin/kaempferol, added "
      "to meet the 24% flavonol glycoside specification without the "
      "authentic extract."),
    P("Serenoa repens", "Elaeis guineensis", "substitution", "documented",
      "fruit", "efficacy: fatty acid profile",
      "Fatty acid profile by GC; sterol profile",
      "Cheaper palm and coconut oils substituted for saw palmetto extract; "
      "distinguishable by fatty acid ratios."),
    P("Serenoa repens", "Cocos nucifera", "substitution", "reported",
      "fruit", "efficacy", "GC fatty acid profile", ""),
    P("Crocus sativus", "Carthamus tinctorius", "substitution", "documented",
      "stigma", "economics; efficacy",
      "HPLC crocin/picrocrocin/safranal; microscopy",
      "Safflower is the classic saffron adulterant; saffron's price makes it "
      "one of the most adulterated botanicals in trade."),
    P("Crocus sativus", "Curcuma longa", "admixture", "reported",
      "stigma", "economics", "HPLC; UV-Vis; microscopy",
      "Turmeric used as a colouring adulterant in powdered saffron."),
    P("Origanum vulgare", "Olea europaea", "admixture", "documented",
      "leaf", "economics; efficacy",
      "DNA metabarcoding; microscopy; volatile profile by GC-MS",
      "Olive leaf, myrtle, sumac and cistus reported as oregano bulking "
      "agents at substantial rates in market surveys."),
    P("Origanum vulgare", "Cistus", "admixture", "reported",
      "leaf", "economics", "DNA metabarcoding; GC-MS", ""),
    P("Rhodiola rosea", "Rhodiola crenulata", "substitution", "documented",
      "root", "efficacy: rosavin absence",
      "HPLC for rosavins vs salidroside; DNA barcoding",
      "R. crenulata lacks rosavins, the markers characteristic of R. rosea, "
      "and is far more available commercially."),
    P("Actaea racemosa", "Actaea dahurica", "substitution", "documented",
      "root/rhizome", "efficacy; safety profile differs",
      "HPTLC; LC-MS triterpene glycosides; DNA barcoding",
      "Asian Actaea species substituted for American black cohosh; a "
      "recurring finding in market surveys."),
    P("Actaea racemosa", "Actaea cimicifuga", "substitution", "documented",
      "root/rhizome", "efficacy", "LC-MS; DNA barcoding", ""),
    P("Hydrastis canadensis", "Coptis chinensis", "substitution", "documented",
      "root", "efficacy; economics",
      "HPLC alkaloid profile: hydrastine absent in Coptis; DNA barcoding",
      "Goldenseal is slow-growing and expensive; Coptis and Berberis species "
      "share berberine but lack hydrastine."),
    P("Hydrastis canadensis", "Berberis aristata", "substitution", "documented",
      "root", "efficacy; economics", "HPLC: hydrastine vs berberine only", ""),
    P("Echinacea purpurea", "Parthenium integrifolium", "substitution", "documented",
      "root", "efficacy",
      "HPTLC; microscopy; DNA barcoding",
      "A long-standing and well-characterised Echinacea root adulterant."),
    P("Panax ginseng", "Panax quinquefolius", "substitution", "documented",
      "root", "efficacy: different ginsenoside profile",
      "HPLC ginsenoside ratio (Rf vs F11); DNA barcoding",
      "Bidirectional substitution driven by price differentials; Rf is "
      "characteristic of P. ginseng and F11 of P. quinquefolius."),
    P("Panax ginseng", "Codonopsis pilosula", "substitution", "reported",
      "root", "efficacy", "HPTLC; DNA barcoding",
      "Codonopsis is a traditional lower-cost 'poor man's ginseng'."),
    P("Harpagophytum procumbens", "Harpagophytum zeyheri", "substitution", "documented",
      "root", "efficacy: lower harpagoside",
      "HPLC harpagoside quantification",
      "Morphologically similar congener with lower marker content."),
    P("Uncaria tomentosa", "Uncaria guianensis", "substitution", "reported",
      "bark", "efficacy: alkaloid profile differs",
      "HPLC oxindole alkaloid profile", ""),
    P("Schisandra chinensis", "Schisandra sphenanthera", "substitution", "documented",
      "fruit", "efficacy; different pharmacopoeial monographs",
      "HPLC lignan profile",
      "Distinct species in the Chinese Pharmacopoeia with different "
      "monographs; frequently conflated in trade."),
    P("Lycium barbarum", "Lycium chinense", "substitution", "reported",
      "fruit", "efficacy", "DNA barcoding; polysaccharide profile", ""),
    P("Withania somnifera", "Withania coagulans", "substitution", "plausible",
      "root", "efficacy: withanolide profile",
      "HPLC withanolide profile; DNA barcoding", ""),
    P("Curcuma longa", "Curcuma zedoaria", "admixture", "reported",
      "rhizome", "efficacy; economics",
      "HPLC curcuminoid profile; DNA barcoding", ""),
    P("Curcuma longa", "Metanil yellow", "chemical_spiking", "documented",
      "rhizome", "toxicity; illegal dye",
      "Colour test; LC-MS",
      "Non-permitted azo dye used to enhance turmeric colour; a recurring "
      "finding in imported turmeric.", False),
    P("Curcuma longa", "Lead chromate", "chemical_spiking", "documented",
      "rhizome", "lead poisoning",
      "ICP-MS for lead; XRF screening",
      "Lead chromate added as a colourant is a documented source of "
      "population-level lead exposure from turmeric.", False),
    P("Arctostaphylos uva-ursi", "Vaccinium vitis-idaea", "substitution", "reported",
      "leaf", "efficacy: arbutin content",
      "HPLC arbutin; microscopy", ""),
    P("Matricaria chamomilla", "Anthemis", "admixture", "reported",
      "flower", "efficacy; allergenicity",
      "Microscopy; volatile oil profile by GC-MS", ""),
    P("Sambucus nigra", "Sambucus canadensis", "substitution", "plausible",
      "fruit", "efficacy", "Anthocyanin profiling; DNA barcoding", ""),
    P("Hypericum perforatum", "Hypericum", "admixture", "reported",
      "aerial", "efficacy: hypericin content",
      "HPLC hypericin/hyperforin; DNA barcoding",
      "Other Hypericum species with lower marker content."),
    P("Silybum marianum", "Silybum", "chemical_spiking", "reported",
      "seed", "efficacy: marker gaming",
      "HPLC silymarin isomer profile",
      "Isomer ratio manipulation to meet a total-silymarin specification."),
    P("Eurycoma longifolia", "Eurycoma", "substitution", "plausible",
      "root", "efficacy", "HPLC eurycomanone; DNA barcoding", ""),
    P("Pausinystalia johimbe", "Yohimbine", "chemical_spiking", "documented",
      "bark", "cardiovascular adverse effects",
      "HPLC yohimbine quantification vs alkaloid profile",
      "Synthetic yohimbine added, or content wildly inconsistent with the "
      "declared botanical; a recurring finding in US market analyses.", False),
    P("Ephedra sinica", "Ephedrine", "chemical_spiking", "documented",
      "aerial", "cardiovascular adverse events",
      "HPLC alkaloid profile",
      "Synthetic ephedrine added to botanical products; ephedra alkaloids in "
      "supplements were banned in the US in 2004.", False),
    P("Citrus aurantium", "Synephrine", "chemical_spiking", "documented",
      "fruit", "cardiovascular adverse effects",
      "HPLC synephrine vs full amine profile",
      "Synthetic synephrine well above the level attainable from the "
      "botanical.", False),
    P("Acacia rigidula", "Beta-methylphenethylamine", "chemical_spiking", "documented",
      "aerial", "undeclared stimulant",
      "LC-MS amine screening",
      "Amphetamine-like compounds not found in the plant reported in "
      "products labelled as Acacia rigidula.", False),
    P("Cordyceps sinensis", "Cordyceps militaris", "substitution", "documented",
      "fruiting body", "efficacy; economics",
      "HPLC cordycepin/adenosine; DNA barcoding",
      "Wild O. sinensis is among the most expensive natural products in "
      "trade; cultivated C. militaris is the common substitute."),
    P("Ganoderma lucidum", "Ganoderma", "substitution", "reported",
      "fruiting body", "efficacy",
      "Triterpene profile; DNA barcoding",
      "The name G. lucidum has been applied to several distinct taxa."),
    P("Aloe vera", "Maltodextrin", "chemical_spiking", "documented",
      "leaf gel", "efficacy; economics",
      "NMR; HPLC for acemannan; isotope ratio",
      "Maltodextrin added to inflate apparent polysaccharide content.", False),
    P("Euterpe oleracea", "Vitis vinifera", "admixture", "plausible",
      "fruit", "economics", "Anthocyanin profiling", ""),
    P("Punica granatum", "Vitis vinifera", "admixture", "reported",
      "fruit", "economics; efficacy",
      "HPLC punicalagin/ellagic acid profile",
      "Pomegranate extract bulked with cheaper polyphenol sources."),
    P("Camellia sinensis", "Caffeine", "chemical_spiking", "reported",
      "leaf", "undeclared stimulant load",
      "HPLC caffeine vs catechin ratio",
      "Added caffeine inconsistent with the declared extract ratio.", False),
    P("Boswellia serrata", "Boswellia", "substitution", "reported",
      "resin", "efficacy: boswellic acid profile",
      "HPLC boswellic acids", ""),
    P("Commiphora wightii", "Commiphora", "substitution", "plausible",
      "resin", "efficacy", "HPLC guggulsterones", ""),
    P("Passiflora incarnata", "Passiflora", "substitution", "reported",
      "aerial", "efficacy", "HPTLC flavonoid profile; DNA barcoding", ""),
    P("Valeriana officinalis", "Valeriana", "substitution", "reported",
      "root", "efficacy: valerenic acid",
      "HPLC valerenic acid; DNA barcoding", ""),
    P("Piper methysticum", "Piper", "admixture", "reported",
      "root", "hepatotoxicity concern from aerial parts",
      "HPLC kavalactone profile; pipermethystine screening",
      "Use of stem peelings and leaves rather than root, and non-noble kava "
      "cultivars, implicated in hepatotoxicity concerns."),
    P("Dioscorea villosa", "Dioscorea", "substitution", "plausible",
      "root", "efficacy: diosgenin", "HPLC diosgenin; DNA barcoding", ""),
    P("Tribulus terrestris", "Tribulus", "substitution", "plausible",
      "aerial/fruit", "efficacy: saponin profile",
      "HPLC protodioscin", ""),
    P("Lepidium meyenii", "Lepidium", "substitution", "reported",
      "root", "efficacy: macamide profile",
      "HPLC macamides; DNA barcoding", ""),
    P("Arnica montana", "Heterotheca inuloides", "substitution", "reported",
      "flower", "efficacy; different constituent profile",
      "HPTLC sesquiterpene lactones; microscopy",
      "Mexican arnica is a distinct genus sold under the same common name."),
    P("Rheum palmatum", "Rheum rhaponticum", "substitution", "documented",
      "root", "efficacy; rhaponticin presence",
      "HPLC rhaponticin as a marker of the adulterant",
      "Rhapontic rhubarb is excluded by pharmacopoeial monographs; "
      "rhaponticin is the diagnostic marker."),
    P("Angelica sinensis", "Angelica", "substitution", "plausible",
      "root", "efficacy", "HPLC ligustilide; DNA barcoding", ""),
    P("Mitragyna speciosa", "7-hydroxymitragynine", "chemical_spiking", "reported",
      "leaf", "potency; opioid receptor activity",
      "LC-MS alkaloid quantification",
      "Enriched or added alkaloid well above natural leaf levels.", False),
    P("Cannabis sativa", "Synthetic cannabinoids", "chemical_spiking", "documented",
      "aerial", "severe adverse events",
      "LC-MS/MS synthetic cannabinoid panel",
      "Synthetic cannabinoid receptor agonists in products marketed as "
      "hemp or CBD.", False),
    P("Garcinia gummi-gutta", "Garcinia", "substitution", "plausible",
      "fruit rind", "efficacy: hydroxycitric acid",
      "HPLC hydroxycitric acid", ""),
    P("Griffonia simplicifolia", "5-Hydroxytryptophan", "chemical_spiking", "plausible",
      "seed", "efficacy; synthetic origin undeclared",
      "Isotope ratio mass spectrometry", "", False),
    P("Trigonella foenum-graecum", "Trigonella", "substitution", "plausible",
      "seed", "efficacy", "HPLC 4-hydroxyisoleucine", ""),
    P("Astragalus membranaceus", "Astragalus", "substitution", "reported",
      "root", "efficacy: astragaloside content",
      "HPLC astragaloside IV; DNA barcoding", ""),
    P("Salvia miltiorrhiza", "Salvia", "substitution", "plausible",
      "root", "efficacy", "HPLC tanshinone/salvianolic acid", ""),
    P("Epimedium", "Epimedium", "substitution", "reported",
      "aerial", "efficacy: icariin content varies widely by species",
      "HPLC icariin; DNA barcoding",
      "The genus contains many species with very different icariin levels."),
    P("Prunus africana", "Prunus", "substitution", "plausible",
      "bark", "efficacy; CITES-listed species",
      "GC sterol profile", ""),
    P("Urtica dioica", "Urtica urens", "admixture", "plausible",
      "root/leaf", "efficacy", "Microscopy; DNA barcoding", ""),
    P("Morinda citrifolia", "Morinda", "substitution", "plausible",
      "fruit", "efficacy", "DNA barcoding", ""),
    P("Bacopa monnieri", "Bacopa", "substitution", "reported",
      "aerial", "efficacy: bacoside content",
      "HPLC bacoside A; DNA barcoding", ""),
    P("Centella asiatica", "Centella", "substitution", "plausible",
      "aerial", "efficacy: triterpene profile",
      "HPLC asiaticoside", ""),
    P("Turnera diffusa", "Turnera", "substitution", "plausible",
      "leaf", "efficacy", "HPTLC; DNA barcoding", ""),
    P("Vitex agnus-castus", "Vitex", "substitution", "plausible",
      "fruit", "efficacy: agnuside content",
      "HPLC agnuside", ""),
    P("Tanacetum parthenium", "Tanacetum", "substitution", "reported",
      "leaf", "efficacy: parthenolide content",
      "HPLC parthenolide",
      "Parthenolide content varies enormously; low-content material is a "
      "recurrent quality problem."),
    P("Petasites hybridus", "Petasites", "admixture", "documented",
      "root", "pyrrolizidine alkaloid hepatotoxicity",
      "LC-MS pyrrolizidine alkaloid screening",
      "PA-containing material must be removed; PA content is the critical "
      "safety parameter for butterbur products."),
    P("Symphytum officinale", "Symphytum", "admixture", "documented",
      "root/leaf", "pyrrolizidine alkaloid hepatotoxicity",
      "LC-MS PA screening",
      "Comfrey PA content underlies restrictions on internal use."),
    P("Ilex paraguariensis", "Ilex", "substitution", "plausible",
      "leaf", "efficacy", "DNA barcoding; methylxanthine profile", ""),
    P("Paullinia cupana", "Caffeine", "chemical_spiking", "plausible",
      "seed", "undeclared stimulant load", "HPLC caffeine", "", False),
    P("Hoodia gordonii", "Opuntia", "substitution", "documented",
      "stem", "efficacy: P57 absent",
      "HPLC for P57; DNA barcoding",
      "Market surveys have repeatedly found little or no authentic Hoodia in "
      "products sold as such."),
    P("Hippophae rhamnoides", "Hippophae", "substitution", "plausible",
      "fruit", "efficacy", "Fatty acid profile by GC", ""),
    P("Myrciaria dubia", "Ascorbic acid", "chemical_spiking", "reported",
      "fruit", "efficacy; synthetic vitamin C undeclared",
      "Isotope ratio mass spectrometry",
      "Synthetic ascorbic acid added to products marketed on natural "
      "vitamin C content.", False),
    P("Adansonia digitata", "Adansonia", "substitution", "plausible",
      "fruit", "efficacy", "DNA barcoding", ""),
    P("Peumus boldus", "Peumus", "substitution", "plausible",
      "leaf", "efficacy; boldine content", "HPLC boldine", ""),
    P("Caulophyllum thalictroides", "Caulophyllum", "substitution", "plausible",
      "root", "efficacy; teratogenicity concern",
      "HPLC alkaloid profile", ""),
    # The best-documented US regulatory substitution case: FDA tested nine
    # samples and found products labelled tejocote root to be substituted
    # with yellow oleander. CDC MMWR reported it first (DOI
    # 10.15585/mmwr.mm7237a3, 2023); FDA issued advisories in January 2024
    # using explicit "substituted with" language.
    P("Crataegus mexicana", "Cascabela thevetia", "substitution", "documented",
      "root", "cardiac glycoside poisoning; deaths reported",
      "DNA barcoding; LC-MS for thevetin B and other cardenolides",
      "Products labelled tejocote (Crataegus mexicana) root, and some labelled "
      "Brazil seed, found by FDA testing to be yellow oleander. Sold largely "
      "through online third-party platforms as weight-loss supplements. One "
      "DNA-fingerprinted product was 100% yellow oleander."),
    P("Illicium verum", "Illicium anisatum", "substitution", "documented",
      "fruit", "neurotoxicity: anisatin seizures in infants",
      "GC-MS for anisatin; morphology; DNA barcoding",
      "Japanese star anise substituted for Chinese star anise, implicated in "
      "infant seizure cases from herbal teas."),
    P("Polygonum multiflorum", "Polygonum", "substitution", "reported",
      "root", "hepatotoxicity; processing-dependent",
      "HPLC stilbene glycoside; anthraquinone profile",
      "Unprocessed vs processed root differ markedly in hepatotoxicity risk."),
]


def pairs_for(botanical: str) -> list[AdulterantPair]:
    """Pairs where `botanical` is the authentic species."""
    return [p for p in ADULTERANT_PAIRS if p.authentic == botanical]


def pairs_naming(botanical: str) -> list[AdulterantPair]:
    """Pairs where `botanical` appears on either side."""
    return [p for p in ADULTERANT_PAIRS
            if botanical in (p.authentic, p.adulterant)]


def authentic_species() -> set:
    return {p.authentic for p in ADULTERANT_PAIRS}


def adulterant_species() -> set:
    """Adulterants that are botanicals (excludes added compounds)."""
    return {p.adulterant for p in ADULTERANT_PAIRS if p.adulterant_is_botanical}


def summary() -> dict:
    from collections import Counter
    return {
        "pairs_version": PAIRS_VERSION,
        "n_pairs": len(ADULTERANT_PAIRS),
        "n_authentic_species": len(authentic_species()),
        "n_botanical_adulterants": len(adulterant_species()),
        "n_non_botanical_adulterants": len(
            {p.adulterant for p in ADULTERANT_PAIRS if not p.adulterant_is_botanical}),
        "by_mode": dict(Counter(p.mode for p in ADULTERANT_PAIRS).most_common()),
        "by_evidence": dict(Counter(p.evidence for p in ADULTERANT_PAIRS).most_common()),
        "note": ("evidence classes differ materially; 'plausible' entries are "
                 "leads named in review literature, not confirmed market cases"),
    }
