#!/usr/bin/env python3
"""Build question-lexicon.json: the scheme names a question can be matched on, from the site's page list (brief §66).

Every English information page on citizensinformation.ie has a slug that names its subject ("fuel-allowance",
"housing-assistance-payment"). The lexicon is those slugs as phrases, plus ALIASES (what people call things: the dole,
HAP, GP card) and minus a STOP list of generic slugs that name nothing on their own. redact_feed.py loads it and tags
each question with the longest phrase it contains, as the page address and its category. The lexicon is public data
(the site's own page addresses) and is committed; it carries a version and the expected outcome per intent.

Usage:
    python3 tools/make_lexicon.py                              # write question-lexicon.json from site-pages.csv
    python3 tools/make_lexicon.py --unmatched exports/qa-feed_*.csv --since 2026-09-15
        # local: the most frequent words and word pairs in questions the lexicon does not match (counts only), to
        # grow ALIASES and STOP by looking at what people actually say. Iterate until the frequent ones are covered.
"""
import argparse, csv, json, os, re, sys, collections as C
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEXICON_VERSION = "2026.10.24-5"
MIN_CHARS = 6            # a phrase shorter than this never matches on its own ("tax" would match everything)
CI = "https://www.citizensinformation.ie/en/"
# What people call things → the page slug (or full path) it means. Checked against the unmatched report.
ALIASES = {
    "the dole": "social-welfare/unemployed-people/jobseekers-allowance", "dole": "social-welfare/unemployed-people/jobseekers-allowance",
    "jobseekers": "social-welfare/unemployed-people/jobseekers-allowance", "jobseeker": "social-welfare/unemployed-people/jobseekers-allowance",
    "hap": "housing/renting-a-home/help-with-renting/housing-assistance-payment", "hap limits": "housing/renting-a-home/help-with-renting/housing-assistance-payment",
    "gp card": "health/medical-cards-and-gp-visit-cards/gp-visit-cards", "gp visit card": "health/medical-cards-and-gp-visit-cards/gp-visit-cards",
    "medical card": "health/medical-cards-and-gp-visit-cards/medical-card", "pps number": "social-welfare/irish-social-welfare-system/personal-public-service-number",
    "pps": "social-welfare/irish-social-welfare-system/personal-public-service-number", "pension": "social-welfare/older-and-retired-people/state-pension-contributory",
    "state pension": "social-welfare/older-and-retired-people/state-pension-contributory", "contributory pension": "social-welfare/older-and-retired-people/state-pension-contributory",
    "non contributory pension": "social-welfare/older-and-retired-people/state-pension-non-contributory", "child benefit": "social-welfare/families-and-children/child-benefit",
    "children's allowance": "social-welfare/families-and-children/child-benefit", "childrens allowance": "social-welfare/families-and-children/child-benefit",
    "back to school": "social-welfare/families-and-children/back-to-school-clothing-and-footwear-allowance", "btsa": "social-welfare/families-and-children/back-to-school-clothing-and-footwear-allowance",
    "fuel allowance": "social-welfare/extra-social-welfare-benefits/fuel-allowance", "carers allowance": "social-welfare/carers/carers-allowance", "carer's allowance": "social-welfare/carers/carers-allowance",
    "carers benefit": "social-welfare/carers/carers-benefit", "disability allowance": "social-welfare/disability-and-illness/disability-allowance",
    "illness benefit": "social-welfare/disability-and-illness/illness-benefit", "invalidity pension": "social-welfare/disability-and-illness/invalidity-pension",
    "maternity benefit": "social-welfare/families-and-children/maternity-benefit", "paternity benefit": "social-welfare/families-and-children/paternity-benefit",
    "parents benefit": "social-welfare/families-and-children/parents-benefit", "parent's benefit": "social-welfare/families-and-children/parents-benefit",
    "working family payment": "social-welfare/families-and-children/working-family-payment", "wfp": "social-welfare/families-and-children/working-family-payment",
    "one parent family payment": "social-welfare/families-and-children/one-parent-family-payment", "household benefits": "social-welfare/extra-social-welfare-benefits/household-benefits-package",
    "free travel": "social-welfare/extra-social-welfare-benefits/free-travel", "living alone allowance": "social-welfare/extra-social-welfare-benefits/living-alone-allowance", "living alone": "social-welfare/extra-social-welfare-benefits/living-alone-allowance",
    "christmas bonus": "social-welfare/irish-social-welfare-system/christmas-bonus", "additional needs payment": "social-welfare/supplementary-welfare-schemes/additional-needs-payment",
    "rent supplement": "social-welfare/supplementary-welfare-schemes/rent-supplement", "supplementary welfare allowance": "social-welfare/supplementary-welfare-schemes/supplementary-welfare-allowance-scheme",
    "passport": "travel-and-recreation/passports/applying-for-or-renewing-an-irish-passport", "passport renewal": "travel-and-recreation/passports/applying-for-or-renewing-an-irish-passport",
    "driving licence": "travel-and-recreation/motoring/driver-licensing/full-driving-licence", "driving license": "travel-and-recreation/motoring/driver-licensing/full-driving-licence",
    "learner permit": "travel-and-recreation/motoring/driving-tests/learner-driving-permits-for-cars-and-work-vehicles", "theory test": "travel-and-recreation/motoring/driving-tests/driver-theory-test",
    "nct": "travel-and-recreation/motoring/motor-tax-and-insurance/national-car-test", "motor tax": "travel-and-recreation/motoring/motor-tax-and-insurance/motor-tax-rates",
    "lpt": "money-and-tax/tax/housing-taxes-and-reliefs/local-property-tax", "local property tax": "money-and-tax/tax/housing-taxes-and-reliefs/local-property-tax",
    "usc": "money-and-tax/tax/income-tax/universal-social-charge", "prsi": "social-welfare/irish-social-welfare-system/social-insurance-prsi/social-insurance",
    "tax credits": "money-and-tax/tax/income-tax-credits-and-reliefs/introduction-to-income-tax-credits-and-reliefs", "rent tax credit": "money-and-tax/tax/housing-taxes-and-reliefs/rent-tax-credit",
    "help to buy": "housing/owning-a-home/help-with-buying-a-home/help-to-buy-scheme", "first home scheme": "housing/owning-a-home/help-with-buying-a-home/first-home-scheme",
    "rtb": "housing/renting-a-home/resolving-disputes/residential-tenancies-board", "eviction": "housing/renting-a-home/tenants-rights-and-responsibilities/if-your-landlord-wants-you-to-leave",
    "notice to quit": "housing/renting-a-home/tenants-rights-and-responsibilities/if-your-landlord-wants-you-to-leave", "minimum wage": "employment/employment-rights-and-conditions/pay-and-employment/minimum-wage",
    "redundancy": "employment/unemployment-and-redundancy/redundancy/redundancy-payments", "annual leave": "employment/employment-rights-and-conditions/leave-and-holidays/annual-leave", "holiday entitlement": "employment/employment-rights-and-conditions/leave-and-holidays/annual-leave",
    "public holidays": "employment/employment-rights-and-conditions/leave-and-holidays/public-holidays", "bank holiday": "employment/employment-rights-and-conditions/leave-and-holidays/public-holidays", "sick pay": "employment/employment-rights-and-conditions/leave-and-holidays/sick-leave-and-sick-pay",
    "sick leave": "employment/employment-rights-and-conditions/leave-and-holidays/sick-leave-and-sick-pay", "maternity leave": "employment/employment-rights-and-conditions/leave-and-holidays/maternity-leave",
    "stamp 4": "moving-country/irish-citizenship/becoming-an-irish-citizen-through-naturalisation", "naturalisation": "moving-country/irish-citizenship/becoming-an-irish-citizen-through-naturalisation",
    "citizenship": "moving-country/irish-citizenship/becoming-an-irish-citizen-through-naturalisation", "irp card": "moving-country/moving-to-ireland/rights-of-residence-in-ireland/registration-of-non-eea-nationals-in-ireland",
    "work permit": "moving-country/working-in-ireland/employment-permits/overview-employment-permits", "employment permit": "moving-country/working-in-ireland/employment-permits/overview-employment-permits",
    "susi": "education/third-level-education/fees-and-supports-for-third-level-education/student-grant-scheme", "student grant": "education/third-level-education/fees-and-supports-for-third-level-education/student-grant-scheme",
    "ncs": "education/pre-school-education-and-childcare/national-childcare-scheme", "national childcare scheme": "education/pre-school-education-and-childcare/national-childcare-scheme",
    "fair deal": "health/health-services/health-services-for-older-people/fair-deal-scheme", "nursing home support scheme": "health/health-services/health-services-for-older-people/fair-deal-scheme",
    "drugs payment scheme": "health/drugs-and-medicines/drugs-payment-scheme", "treatment benefit": "social-welfare/disability-and-illness/treatment-benefit-scheme",
    "budget 2027": "money-and-tax/budgets/budget-2027", "budget 2026": "money-and-tax/budgets/budget-2026", "budget 2025": "money-and-tax/budgets/budget-2025",
    "seai grant": "housing/housing-grants-and-schemes/grants-for-home-renovations-and-improvements/grants-for-a-energy-upgrade", "solar panels": "housing/housing-grants-and-schemes/grants-for-home-renovations-and-improvements/grants-for-solar-panels", "solar grant": "housing/housing-grants-and-schemes/grants-for-home-renovations-and-improvements/grants-for-solar-panels", "energy upgrade grant": "housing/housing-grants-and-schemes/grants-for-home-renovations-and-improvements/grants-for-a-energy-upgrade",
    "divorce": "birth-family-relationships/separation-and-divorce/divorce-decrees", "separation": "birth-family-relationships/separation-and-divorce/judicial-separation", "separated": "birth-family-relationships/separation-and-divorce/judicial-separation",
    "probate": "death/", "will": None, "social welfare": "social-welfare/", "welfare payment": "social-welfare/", "welfare payments": "social-welfare/", "social welfare payment": "social-welfare/", "job seekers": "social-welfare/unemployed-people/jobseekers-allowance", "jobseekers allowance": "social-welfare/unemployed-people/jobseekers-allowance", "jobseekers benefit": "social-welfare/unemployed-people/jobseekers-benefit", "disability payment": "social-welfare/disability-and-illness/disability-allowance", "social housing": "housing/local-authority-and-social-housing/applying-for-local-authority-housing", "council house": "housing/local-authority-and-social-housing/applying-for-local-authority-housing", "council housing": "housing/local-authority-and-social-housing/applying-for-local-authority-housing", "housing list": "housing/local-authority-and-social-housing/social-housing-waiting-lists", "self employed": "employment/types-of-employment/self-employment", "self employment": "employment/types-of-employment/self-employment", "one parent": "social-welfare/families-and-children/one-parent-family-payment", "lone parent": "social-welfare/families-and-children/one-parent-family-payment", "single parent": "social-welfare/families-and-children/one-parent-family-payment", "household benefit": "social-welfare/extra-social-welfare-benefits/household-benefits-package", "rent a room": "money-and-tax/", "rent room": "money-and-tax/", "means test": "social-welfare/irish-social-welfare-system/means-test-for-social-welfare-payments", "means tested": "social-welfare/irish-social-welfare-system/means-test-for-social-welfare-payments", "tax relief": "money-and-tax/", "tax credit": "money-and-tax/tax/income-tax-credits-and-reliefs", "irish citizen": "moving-country/irish-citizenship/becoming-an-irish-citizen-through-naturalisation", "citizens information": "about/", "income tax": "money-and-tax/tax/income-tax", "landlord": "housing/renting-a-home/", "tenant": "housing/renting-a-home/", "renting": "housing/renting-a-home/", "mortgage": "housing/owning-a-home/", "visa": "moving-country/visas-for-ireland/", "asylum": "moving-country/asylum-seekers-and-refugees/", "refugee": "moving-country/asylum-seekers-and-refugees/", "ukrain": "moving-country/ukrainian-refugees-in-ireland/", "carer": "social-welfare/carers/", "disability": "social-welfare/disability-and-illness/", "unemployed": "social-welfare/unemployed-people/", "lose my job": "social-welfare/unemployed-people/", "lost my job": "social-welfare/unemployed-people/", "retire": "employment/retirement/", "retirement": "employment/retirement/", "pensioner": "social-welfare/older-and-retired-people/", "inheritance": "money-and-tax/tax/capital-taxes/capital-acquisitions-tax", "inheritance tax": "money-and-tax/tax/capital-taxes/capital-acquisitions-tax", "capital gains": "money-and-tax/tax/capital-taxes/capital-gains-tax", "vat": "money-and-tax/tax/duties-and-vat/value-added-tax", "revenue": "money-and-tax/tax/", "garda": "justice/", "court": "justice/courtroom/", "solicitor": "justice/", "legal aid": "justice/legal-aid-and-advice/", "school": "education/primary-and-post-primary-education/", "college": "education/third-level-education/", "university": "education/third-level-education/", "creche": "education/pre-school-education-and-childcare/", "childcare": "education/pre-school-education-and-childcare/", "hospital": "health/health-services/", "dentist": "health/health-services/dental-aural-and-optical-services/", "gp": "health/health-services/gp-and-hospital-services/", "prescription": "health/drugs-and-medicines/", "electricity": "consumer/utilities/", "esb": "consumer/utilities/", "energy credit": "consumer/utilities/", "electric car": "environment/", "ev grant": "environment/", "dog licence": "environment/pets-and-wildlife/", "voting": "government-in-ireland/elections-and-referenda/", "vote": "government-in-ireland/elections-and-referenda/", "death certificate": "death/", "funeral": "death/", "bereavement": "death/", "birth certificate": "birth-family-relationships/", "marriage": "birth-family-relationships/getting-married/", "wedding": "birth-family-relationships/getting-married/", "adoption": "birth-family-relationships/adoption-and-fostering/", "domestic violence": "justice/", "northern ireland": "returning-to-ireland/", "social protection": "social-welfare/", "intreo": "social-welfare/", "qualified adult": "social-welfare/irish-social-welfare-system/", "adult dependant": "social-welfare/irish-social-welfare-system/", "foreign birth": "moving-country/irish-citizenship/irish-citizenship-through-birth-or-descent", "foreign births register": "moving-country/irish-citizenship/irish-citizenship-through-birth-or-descent", "leaving cert": "education/state-examinations/", "junior cert": "education/state-examinations/", "public holiday": "employment/employment-rights-and-conditions/leave-and-holidays/public-holidays", "bank account": "money-and-tax/personal-finance/banking/", "opt out": "money-and-tax/personal-finance/pensions/auto-enrolment", "auto enrolment": "money-and-tax/personal-finance/pensions/auto-enrolment", "auto enrollment": "money-and-tax/personal-finance/pensions/auto-enrolment", "employer": "employment/", "working hours": "employment/employment-rights-and-conditions/hours-of-work/", "work hours": "employment/employment-rights-and-conditions/hours-of-work/", "hours a week": "employment/employment-rights-and-conditions/hours-of-work/", "pay tax": "money-and-tax/tax/income-tax", "tax return": "money-and-tax/tax/income-tax", "tax refund": "money-and-tax/tax/income-tax", "medical": "health/", "doctor": "health/health-services/", "benefit": "social-welfare/", "allowance": "social-welfare/", "grant": None,   # None: too generic on its own, kept out even if a slug matches
}
# Generic slugs that name nothing on their own; these never become phrases
STOP = {"overview", "introduction", "rights", "housing", "employment", "health", "education", "consumer", "justice", "death", "environment",
        "money", "tax", "benefits", "payments", "services", "support", "supports", "schemes", "grants", "forms", "contact", "about", "help",
        "general", "other", "information", "resources", "rules", "rates", "apply", "applying", "how to apply", "eligibility", "appeals",
        "your rights", "getting help", "useful contacts", "organisations", "categories", "home", "news", "glossary", "faq", "search",
        # titles that are also ordinary phrases (brief §71): a question using the words is not naming the page
        "cost of living", "insurance", "dismissal", "signing on", "accommodation", "legislation", "mental health", "complaints", "appeals",
        "retirement", "redundancy", "divorce", "separation", "wills", "probate", "citizenship"}
# Intents and the outcome the design expects (brief §66): status → redirect (a not-found or out-of-scope is correct), the rest → cited
# status → cited: AskCI explaining how to check a claim is the right outcome (brief §71, reversing §66). Clarification is
# the expected outcome for a "what is" question that names no scheme; the dashboard applies that second dimension.
INTENTS = {"status": "cited", "contact": "cited", "documents": "cited", "apply": "cited", "rate": "cited", "eligibility": "cited",
           "timing": "cited", "definition": "cited", "statement": "cited", "other": None}
TS = "%b %d, %Y %H:%M"


def norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s.replace("-", " ").replace("'", ""))
    return re.sub(r"\s+", " ", s).strip()


def build():
    pages = {}
    with open(os.path.join(REPO, "site-pages.csv"), encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("Kind") != "information" or r.get("Language") != "en": continue
            u = r["URL"].rstrip("/"); path = u.split("/en/", 1)[1] if "/en/" in u else ""
            if not path: continue
            cat = path.split("/")[0]; slug = path.split("/")[-1]; phrase = norm(slug)
            pages[path] = (u, cat, phrase)
    entries = {}
    hubs = {path for path in pages if any(o != path and o.startswith(path + "/") for o in pages)}   # pages with pages beneath them
    for path, (u, cat, phrase) in pages.items():
        if len(phrase) < MIN_CHARS or phrase in STOP or phrase.split()[-1] in ("overview", "introduction"): continue
        if phrase not in entries or len(path) < len(entries[phrase]["path"]): entries[phrase] = {"path": path, "url": u, "category": cat, "source": "slug", "hub": path in hubs}
    for alias, path in ALIASES.items():
        a = norm(alias)
        if path is None:
            entries.pop(a, None); continue
        cat = path.split("/")[0]
        if path.endswith("/"):   # a category (or section) only: no page, the category still counts as a topic
            entries[a] = {"path": path.rstrip("/"), "url": None, "category": cat, "source": "alias"}; continue
        u = CI + path
        if path not in pages: print(f"note: alias '{alias}' points at a path not on the page list ({path}); kept, category {cat}", file=sys.stderr)
        entries[a] = {"path": path, "url": u, "category": cat, "source": "alias", "hub": path in hubs}
    out = {"_comment": "Scheme names a question can be matched on (brief §66): the site's English information page slugs as phrases, plus aliases, minus "
                       "generic slugs and ordinary-phrase titles. redact_feed.py tags each question with the longest phrase it contains, as the page address and category. "
                       "hub = other pages sit beneath it, so a citation of any of them counts as a hit (brief §71). Public data: the site's own addresses. INTENTS carries the outcome the design expects per intent.",
           "version": LEXICON_VERSION, "min_chars": MIN_CHARS, "intents": INTENTS,
           "derivation_version": DERIVATION_VERSION, "topics": topics_out(),
           "phrases": {p: e for p, e in sorted(entries.items(), key=lambda kv: (-len(kv[0]), kv[0]))}}
    return out


# Topic layer (brief §75): generic keyword buckets per category. A topic's keywords are ordinary words and short phrases,
# never a phrase lifted from a distinctive question; `--topic-counts FEEDS` prints how many questions each keyword
# matches (counts only) and the build refuses a keyword under TOPIC_MIN_MATCHES, so nothing rare and identifying can
# enter this public file. A question's topic is the matching keyword that is longest; a topic marked general applies
# only when no other does. DERIVATION_VERSION bundles this key with redact_feed.py's response rules and template list.
DERIVATION_VERSION = "2026.10.24-6"   # bumped with redact_feed.py's: -2 templates, -3 organisations, -4 figures, -5 five more topic tables, -6 layer 2 (situation, asks)
TOPIC_MIN_MATCHES = 20
TOPICS = {
    "housing": {
        "Renting: landlord and tenant": ["landlord", "landlords", "tenant", "tenants", "tenancy", "evict", "evicted", "eviction", "notice of termination", "rtb", "residential tenancies", "lease", "my deposit", "deposit back"],
        "Rent increases and rent pressure zones": ["rent increase"],
        "HAP, Rent Supplement and RAS": ["hap", "housing assistance payment", "rent supplement"],
        "Rent tax credit": ["rent tax credit"],
        "Social and council housing": ["social housing", "council house", "council housing", "housing list", "housing waiting list", "local authority housing", "housing application", "cost rental", "affordable housing", "differential rent", "approved housing body", "housing body"],
        "Homelessness and emergency accommodation": ["homeless", "homelessness", "emergency accommodation", "hostel"],
        "Buying a home": ["help to buy", "first home scheme", "first time buyer", "first time buyers", "mortgage", "local authority home loan", "buying a house", "buy a house", "new build"],
        "Mortgage arrears and repossession": ["mortgage interest"],
        "Home grants and energy upgrades": ["housing adaptation grant", "adaptation grant", "mobility aids grant", "housing aid for older people", "vacant property grant", "vacant property refurbishment", "vacant property", "derelict", "seai", "insulation", "solar panels", "solar panel", "warmer homes", "heat pump", "better energy", "energy upgrade", "energy upgrades", "home improvement"],
        "Planning permission and building": ["planning permission", "extension", "modular home", "septic tank", "ber rating", "mobile home"],
        "Property taxes": ["local property tax", "lpt", "property tax", "stamp duty"],
        "Rent-a-room and lodgers": ["rent a room", "rent a room scheme", "licensee", "renting a room", "rent out a room"],
        "Accommodation for refugees and protection applicants": ["arp", "ipas"],
        "Inheriting, selling or transferring a home": ["sell the house"],
        "Separation and the family home": ["family home"],
        "Neighbours, boundaries and nuisance": ["neighbour", "neighbours", "boundary", "hedge", "right of way"],
        "Renting: repairs, standards and overcrowding": ["repairs", "repair"],
        "Student and short-term accommodation": ["student accommodation", "airbnb", "holiday home"],
        "Apartment management companies": ["management company"],
        "Housing, general": {"general": True, "keywords": ["housing", "accommodation", "apartment", "apartments", "renting", "rented", "rent", "rents", "property", "properties", "home owner", "my house", "our house", "a house", "the house", "my home", "our home", "new home", "new house", "house i", "house we"]},
    },
    "social-welfare": {
        "Jobseekers": ["jobseekers", "jobseeker", "jobseekers allowance", "jobseekers benefit", "the dole", "dole", "unemployment benefit", "signing on", "sign on", "unemployed"],
        "State pension": ["state pension", "contributory pension", "non contributory pension", "pension age", "old age pension", "widows pension", "pension rate", "my pension", "the pension", "pension entitlement", "pension when i"],
        "Illness and disability payments": ["disability allowance", "illness benefit", "invalidity pension", "partial capacity", "injury benefit", "blind pension", "domiciliary care", "disability payment", "disability benefit", "sick from work", "out sick", "on sick leave"],
        "Carers": ["carers allowance", "carers benefit", "carers support grant", "carer", "carers", "caring for my", "half rate carers"],
        "Families and children": ["child benefit", "childrens allowance", "maternity benefit", "paternity benefit", "parents benefit", "one parent family", "working family payment", "back to school", "lone parent", "single parent", "single mother", "child support", "child maintenance", "maintenance payments", "newborn", "new baby", "my baby", "my children", "my child", "my son", "my daughter", "my kids"],
        "Extra benefits": ["fuel allowance", "household benefits", "free travel", "living alone", "christmas bonus", "telephone support", "electricity allowance", "tv licence", "winter fuel", "double payment", "lump sum payment"],
        "Supplementary welfare": ["additional needs payment", "exceptional needs", "supplementary welfare", "community welfare", "community welfare officer", "financial help", "financial assistance", "hardship"],
        "Means tests and income limits": ["means test", "means tested", "means testing", "income limit", "income limits", "income threshold", "how much can i earn", "assessable income", "means assessment", "household income", "my savings", "savings affect", "disregard"],
        "PRSI and contributions": ["prsi", "pps number", "pps", "social insurance", "contributions", "stamps", "credited contributions", "credits", "class a", "class s", "voluntary contributions", "insurance record", "contribution record", "paid contributions", "homemakers"],
        "Appeals, overpayments and decisions": ["appeal", "appeals", "appealed", "overpayment", "overpaid", "was refused", "been refused", "cut off", "suspended", "review my", "reviewed"],
        "Working while claiming": ["back to work enterprise", "btwea", "work while on", "casual work", "community employment", "tus scheme", "back to education allowance"],
        "Social welfare, general": {"general": True, "keywords": ["social welfare", "welfare payment", "welfare", "my payment", "payment", "payments", "benefit", "benefits", "allowance", "allowances", "entitled to", "entitlements", "entitlement", "intreo", "department of social protection", "social protection", "dsp", "weekly payment", "claim", "claiming", "my claim"]},
    },
    "employment": {
        "Pay and the minimum wage": ["minimum wage", "wages", "payslip", "payslips", "overtime", "not been paid", "hourly rate", "my pay", "my wages", "my salary", "back pay", "rate of pay"],
        "Leave and holidays": ["annual leave", "holiday pay", "holidays", "holiday entitlement", "public holiday", "public holidays", "bank holiday", "bank holidays", "sick leave", "sick pay", "statutory sick", "maternity leave", "paternity leave", "parental leave", "parents leave", "carers leave", "force majeure", "unpaid leave", "leave entitlement", "days off", "day off", "time off", "accrue", "accrued"],
        "Redundancy and losing a job": ["redundancy", "redundant", "laid off", "lay off", "layoff", "dismissal", "dismissed", "fired", "let go", "unfair dismissal", "notice period", "short time", "insolvency", "lose my job", "lost my job", "terminated"],
        "Contracts and conditions": ["contract of employment", "my contract", "employment contract", "contract", "probation", "fixed term", "fixed term contract", "zero hours", "working hours", "my hours", "reduce my hours", "part time", "part time worker", "remote working", "work from home", "working from home", "flexible working", "roster", "shift", "shifts"],
        "Rights, disputes and the WRC": ["wrc", "workplace relations", "grievance", "bullying", "bullied", "harassment", "discrimination", "equality", "employer refuses", "employment rights", "disciplinary"],
        "Self-employment and starting a business": ["self employed", "self employment", "sole trader", "contractor", "freelance", "register as self employed", "limited company", "my business", "small business", "own business"],
        "Retirement from work": ["retire", "retiring", "retirement", "retirement age", "occupational pension", "company pension", "work pension", "auto enrolment", "my future fund", "prsa", "pension scheme", "pension contributions"],
        "Agency, young and migrant workers": ["under 18", "16 year old", "17 year old", "internship", "apprentice", "apprenticeship"],
        "Employment, general": {"general": True, "keywords": ["employer", "employers", "employee", "employees", "employment", "my job", "new job", "my boss", "my manager", "workplace", "at work", "my work", "staff", "job offer", "full time", "started work", "start work", "working for"]},
    },
    "money-and-tax": {
        "Income tax, PAYE and credits": ["income tax", "tax credits", "tax credit", "paye", "emergency tax", "tax refund", "tax back", "tax return", "form 12", "form 11", "myaccount", "statement of liability", "usc", "tax free", "tax relief", "single person child carer", "jointly assessed", "joint assessment", "tax on my", "pay tax on", "do i pay tax", "taxable", "taxed", "net pay", "take home pay", "gross pay", "tax year"],
        "Reliefs on expenses": ["medical expenses", "tuition fees", "cycle to work", "bike to work", "tax relief on", "claim back", "claim tax back", "rent a room relief", "relief for"],
        "Capital taxes: inheritance, gifts, gains": ["inheritance tax", "capital acquisitions", "capital gains", "cgt", "inherit", "inherited", "inheritance"],
        "Budget": ["budget 2026", "budget 2027", "the budget", "in the budget"],
        "Banking, debt and personal finance": ["mabs", "debt", "debts", "credit union", "bank account", "open a bank account", "loan", "loans", "credit card", "savings account", "repayments", "repay"],
        "VAT, duties and other taxes": ["vat", "vat rate", "vrt", "customs", "duty on", "carbon tax", "local property tax", "lpt"],
        "Cost of living supports": ["cost of living", "electricity bill", "cant afford", "cannot afford", "cost of", "price of"],
        "Money and tax, general": {"general": True, "keywords": ["tax", "taxes", "revenue", "taxation", "income", "my income", "earnings", "salary", "money", "finances", "financial"]},
    },
    "moving-country": {
        "Citizenship and naturalisation": ["citizenship", "naturalisation", "naturalization", "irish citizen", "citizen by", "foreign birth", "foreign births register", "citizenship application", "reckonable residence"],
        "Residence permissions and stamps": ["stamp 1", "stamp 1g", "stamp 2", "stamp 3", "stamp 4", "stamp 0", "irp card", "irp", "gnib", "residence permission", "permission to remain", "immigration permission", "eu treaty rights", "renew my irp", "my permission"],
        "Visas and entry": ["visa", "visas", "visa application", "short stay visa", "short stay", "do i need a visa", "need a visa", "entry visa", "preclearance", "tourist visa", "schengen", "d visa"],
        "Employment permits": ["employment permit", "work permit", "critical skills", "general employment permit", "permit holder", "permit application", "allowed to work", "right to work", "sponsorship"],
        "Family reunification": ["family reunification", "spouse visa", "de facto partner", "de facto", "family member of", "married to an irish"],
        "International protection and Ukraine": ["asylum", "asylum seeker", "international protection", "ipas", "temporary protection", "ukrainian", "ukrainians", "ukraine", "refugee", "refugees", "refugee status", "leave to remain", "subsidiary protection", "ipo"],
        "Students and graduates": ["student visa", "international student", "1g", "20 hours"],
        "Returning to and leaving Ireland": ["returning to ireland", "return to ireland", "moving back", "move back to ireland", "moving back to ireland", "move abroad", "leaving ireland", "leave ireland", "habitual residence", "living abroad", "uk pension"],
        "Moving country, general": {"general": True, "keywords": ["immigration", "immigrant", "non eea", "non eu", "eu citizen", "uk citizen", "british citizen", "british passport", "common travel area", "residency", "resident in ireland", "moving to ireland", "move to ireland", "living in ireland", "nationality", "from india", "from brazil", "from the us", "from canada", "from australia", "from the uk", "from england", "from ukraine"]},
    },
    "health": {
        "Medical card and GP visit card": ["medical card", "medical cards", "gp visit card", "gp card", "medical card application", "renew my medical card", "medical card means", "over 70s medical card", "discretionary medical card", "medical card cover", "with a medical card", "full medical card"],
        "GP, hospital and waiting lists": ["gp", "my gp", "doctor", "my doctor", "hospital", "a&e", "waiting list", "consultant", "referral", "referred", "cross border", "ambulance"],
        "Prescriptions and medicines": ["drugs payment scheme", "dps", "prescription", "prescriptions", "long term illness", "long term illness scheme", "medicines", "medication", "pharmacy", "hrt"],
        "Dental, eyes and ears": ["dentist", "dental", "dental treatment", "teeth", "tooth", "dentures", "eye test", "glasses", "hearing aid", "hearing aids", "treatment benefit", "filling", "extraction"],
        "Older people's care: home support and nursing homes": ["fair deal", "nursing home", "home support", "home help", "home care", "respite", "respite care", "my mother is", "my father is", "dementia", "care of my", "residential care"],
        "Disability, mental health and services": ["mental health", "counselling", "therapy", "therapist", "autism", "autistic", "asd", "adhd", "physiotherapy", "wheelchair", "mobility aids", "primary care", "special needs", "my disability", "disabled", "disability", "addiction", "alcohol", "rehab", "depression", "anxiety"],
        "Pregnancy, birth and children": ["pregnant", "pregnancy", "maternity and infant", "antenatal", "public health nurse", "vaccine", "vaccination"],
        "Health insurance and costs": ["health insurance", "private health insurance", "private health", "medical expenses"],
        "Health, general": {"general": True, "keywords": ["hse", "health services", "health", "medical", "treatment", "clinic", "public health", "healthcare", "health care", "sick", "illness", "diagnosed", "diagnosis", "condition", "surgery", "operation", "scan", "blood test", "diabetic", "diabetes", "cancer", "stroke", "heart"]},
    },
}


def topics_out():
    """TOPICS as written to the lexicon: {category: {topic: {"keywords": [...], "general": bool}}}, keywords normalised."""
    out = {}
    for cat, tops in TOPICS.items():
        out[cat] = {}
        for name, spec in tops.items():
            kws = spec["keywords"] if isinstance(spec, dict) else spec
            out[cat][name] = {"keywords": sorted({norm(k) for k in kws}, key=lambda k: (-len(k), k)), "general": bool(isinstance(spec, dict) and spec.get("general"))}
    return out


def topic_counts(feeds, since, fail_under):
    """local: how many questions each topic keyword matches (counts only; no text is printed). Returns the keywords
    under fail_under, which is the check the build runs before the lexicon is written."""
    kws = {(c, t, k) for c, tops in topics_out().items() for t, spec in tops.items() for k in spec["keywords"]}
    rx = {key: re.compile(r"\b" + re.escape(key[2]) + r"\b") for key in kws}
    seen = set(); n = 0; counts = C.Counter(); topic_q = C.Counter()
    for f in feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID"), row.get("Turn #"))
                if k in seen: continue
                seen.add(k)
                if since:
                    try: d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date().isoformat()
                    except ValueError: continue
                    if d < since: continue
                q = norm(row.get("User Query") or "")
                if len(q) < 4: continue
                n += 1; hit = set()
                for key, r in rx.items():
                    if r.search(q): counts[key] += 1; hit.add(key[:2])
                for t in hit: topic_q[t] += 1
    for (c, t), tq in sorted(topic_q.items()): print(f"{c} / {t}: {tq:,} questions")
    print(f"\nkeywords by matches ({n:,} questions read):")
    low = []
    for key in sorted(kws, key=lambda k: (counts[k], k)):
        v = counts[key]; flag = "  LOW" if v < fail_under else ""
        print(f"   {v:6}  {key[0]} / {key[1]} / {key[2]}{flag}")
        if v < fail_under: low.append(key)
    return low


def unmatched(feeds, lex, since, top):
    """local: words and word pairs most frequent in questions the lexicon does not match, with how those turns ended"""
    phrases = list(lex["phrases"]); rx = re.compile(r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b")
    seen = set(); n = m = 0; words = C.Counter(); pairs = C.Counter(); nf_words = C.Counter()
    stop = set("the a an to of for in on and or is are my i me we it do can how what when where who which if was be get am have has with about from at this that you your will would should could there their they them need want know".split())
    for f in feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID"), row.get("Turn #"))
                if k in seen: continue
                seen.add(k)
                try: d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date().isoformat()
                except ValueError: continue
                if since and d < since: continue
                q = norm(row.get("User Query") or "")
                if len(q) < 4: continue
                n += 1
                if rx.search(q): m += 1; continue
                toks = [w for w in q.split() if w not in stop and len(w) > 2]
                words.update(set(toks)); pairs.update(set(zip(toks, toks[1:])))
    print(f"{n:,} questions since {since or 'the start'}: {m:,} matched a phrase ({m / n:.0%}), {n - m:,} did not")
    print("most frequent words in unmatched questions:"); [print(f"   {v:6}  {w}") for w, v in words.most_common(top)]
    print("most frequent word pairs in unmatched questions:"); [print(f"   {v:6}  {' '.join(w)}") for w, v in pairs.most_common(top)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unmatched", nargs="*", metavar="FEED"); ap.add_argument("--since"); ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--topic-counts", nargs="*", metavar="FEED", help="local: questions matched per topic keyword (counts only); the build refuses keywords under TOPIC_MIN_MATCHES")
    a = ap.parse_args()
    if a.topic_counts:
        low = topic_counts(a.topic_counts, a.since, TOPIC_MIN_MATCHES)
        if low: sys.exit(f"{len(low)} topic keyword(s) match fewer than {TOPIC_MIN_MATCHES} questions; remove them before writing the lexicon")
        print(f"every topic keyword matches {TOPIC_MIN_MATCHES}+ questions")
    lex = build()
    p = os.path.join(REPO, "question-lexicon.json")
    json.dump(lex, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(p, "a").write("\n")
    print(f"wrote question-lexicon.json: {len(lex['phrases'])} phrases ({sum(1 for e in lex['phrases'].values() if e['source'] == 'alias')} aliases), version {LEXICON_VERSION}; "
          f"{sum(len(t) for t in lex['topics'].values())} topics in {len(lex['topics'])} categories, derivation {DERIVATION_VERSION}")
    if a.unmatched: unmatched(a.unmatched, lex, a.since, a.top)


if __name__ == "__main__":
    main()
