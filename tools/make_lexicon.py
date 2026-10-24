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
LEXICON_VERSION = "2026.10.24-3"
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
           "phrases": {p: e for p, e in sorted(entries.items(), key=lambda kv: (-len(kv[0]), kv[0]))}}
    return out


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
    a = ap.parse_args()
    lex = build()
    p = os.path.join(REPO, "question-lexicon.json")
    json.dump(lex, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(p, "a").write("\n")
    print(f"wrote question-lexicon.json: {len(lex['phrases'])} phrases ({sum(1 for e in lex['phrases'].values() if e['source'] == 'alias')} aliases), version {LEXICON_VERSION}")
    if a.unmatched: unmatched(a.unmatched, lex, a.since, a.top)


if __name__ == "__main__":
    main()
