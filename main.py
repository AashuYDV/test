"""
main.py  —  Offer Predictor API
Deploy on Render:
  Build:  pip install -r requirements.txt
  Start:  uvicorn main:app --host 0.0.0.0 --port $PORT
Env var required: MONGO_URI
"""
import os, math
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# ── Absolute path so Render can find frontend/ regardless of cwd ──────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="Offer Predictor API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
_client   = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
col       = _client["offer_predictor"]["admits"]

DEGREE_MAP = {
    "Master's": "Masters", "Masters": "Masters", "master's": "Masters",
    "PhD": "PhD", "phd": "PhD",
    "MBA": "MBA", "mba": "MBA",
    "Bachelor's": "Bachelors", "Bachelors": "Bachelors", "bachelor's": "Bachelors",
}
COUNTRY_MAP = {
    "USA": "United States", "UK": "United Kingdom",
    "Germany": "Germany",   "Canada": "Canada",
    "Australia": "Australia", "Netherlands": "Netherlands",
    "Ireland": "Ireland",   "France": "France",
}
COURSE_MAP = {
    "Computer Science":   "Computer Science",
    "Data Science":       "Data Science and Data Analytics",
    "ECE":                "Electrical and Computer Engineering",
    "MBA":                "Mba",
    "Mechanical Engg":    "Mechanical Engineering",
    "Business Analytics": "Business Analytics",
    "Finance":            "Finance",
    "Civil Engineering":  "Civil Engineering",
}
KNOWN_ABBR = {
    "Massachusetts Institute of Technology": "MIT",
    "University of California, Berkeley": "UCB",
    "University of California, Los Angeles": "UCLA",
    "University of California, San Diego": "UCSD",
    "University of California, Irvine": "UCI",
    "University of California, Davis": "UCD",
    "University of California,  Riverside": "UCR",
    "University of Southern California": "USC",
    "University of Michigan, Ann Arbor": "UMich",
    "University of Maryland, College Park": "UMD",
    "University of Illinois Urbana-Champaign": "UIUC",
    "University of Illinois at Chicago": "UIC",
    "The University of Texas at Austin": "UTA",
    "The University of Texas at Dallas": "UTD",
    "The University of Texas at Arlington": "UTA",
    "University of Washington": "UW",
    "University of Wisconsin-Madison": "UW-M",
    "University of Minnesota, Twin Cities": "UMN",
    "University of Florida": "UFL",
    "University of North Carolina at Charlotte": "UNCC",
    "University of Massachusetts Amherst": "UMass",
    "University of Colorado Boulder": "CUB",
    "Carnegie Mellon University": "CMU",
    "Georgia Institute of Technology": "GT",
    "Columbia University": "CU",
    "New York University": "NYU",
    "Northeastern University, Boston": "NEU",
    "Northeastern University, Silicon Valley": "NEU-SV",
    "Boston University": "BU",
    "Purdue University West Lafayette": "Purdue",
    "Pennsylvania State University": "PSU",
    "Texas A&M University, College Station": "TAMU",
    "Arizona State University": "ASU",
    "University at Buffalo SUNY": "UB",
    "Stony Brook University": "SBU",
    "Stevens Institute of Technology": "SIT",
    "Illinois Institute of Technology": "IIT",
    "North Carolina State University, Raleigh": "NCSU",
    "Virginia Tech": "VT",
    "Duke University": "Duke",
    "Johns Hopkins University": "JHU",
    "Northwestern University": "NU",
    "Cornell University": "Cornell",
    "Stanford University": "Stanford",
    "Harvard University": "Harvard",
    "The University of Chicago": "UChicago",
    "University of Chicago": "UChicago",
    "Vanderbilt University": "Vandy",
    "Indiana University Bloomington": "IU",
    "George Mason University": "GMU",
    "The George Washington University": "GWU",
    "Rutgers University, New Brunswick": "RU",
    "San Jose State University": "SJSU",
    "New Jersey Institute of Technology": "NJIT",
    "Rochester Institute of Technology": "RIT",
    "University of Arizona": "UA",
    "University of Maryland, Baltimore County": "UMBC",
    "California State University, Long Beach": "CSULB",
    "University of Pittsburgh": "Pitt",
    "Pace University": "Pace",
    "University of Cincinnati": "UC",
    "University College London": "UCL",
    "Imperial College London": "ICL",
    "The University of Edinburgh": "UoE",
    "University of Edinburgh": "UoE",
    "King's College London": "KCL",
    "University of Manchester": "UoM",
    "University of Birmingham": "UoB",
    "University of Bristol": "UoB",
    "University of Warwick": "UoW",
    "University of Glasgow": "UoG",
    "University of Liverpool": "UoL",
    "Queen Mary University of London": "QMUL",
    "University of Nottingham": "UoN",
    "University of Leeds": "Leeds",
    "Technical University of Munich": "TUM",
    "RWTH Aachen University": "RWTH",
    "Dresden University of Technology": "TU Dresden",
    "Delft University of Technology": "TU Delft",
    "University of Toronto": "UoT",
    "The University of British Columbia, Vancouver": "UBC",
    "McGill University": "McGill",
}

def make_abbr(name: str) -> str:
    if name in KNOWN_ABBR: return KNOWN_ABBR[name]
    skip = {"of","the","at","in","and","for","&","a","an","university","college",
            "institute","school","state","national","international","new"}
    words = [w for w in name.replace(",","").replace(".","").split()
             if w.lower() not in skip]
    if not words: words = name.split()
    return "".join(w[0].upper() for w in words[:4])[:5] or name[:4].upper()


class PredictRequest(BaseModel):
    country:         str
    parent_course:   str
    degree:          str
    work_exp_months: int
    english_test:    Optional[str]   = None
    english_score:   Optional[float] = None

class OfferCard(BaseModel):
    university:      str
    course:          str
    rank_label:      Optional[str]
    rank:            Optional[int]
    admit_count:     int
    scholarship_pct: int
    sample_profiles: list[str]   # up to 3 real yocket.com/profile/ links
    abbr:            str

class NearMiss(BaseModel):
    university:     str
    course:         str
    rank_label:     Optional[str]
    gap_field:      str
    gap_label:      str
    user_value:     float
    required_value: float
    admit_count:    int

class PredictResponse(BaseModel):
    matched_profiles: int
    results:          list[OfferCard]
    near_miss:        list[NearMiss]
    fallback_used:    bool
    context_label:    str


def run_pipeline(base, we_lo, we_hi, eng_test, eng_lo, eng_hi, limit=10):
    pipeline = [
        {"$match": base},
        {"$match": {"profile.work_exp_months": {"$gte": we_lo, "$lte": we_hi}}},
    ]
    if eng_test and eng_test.upper() not in ("NONE", "") and eng_lo is not None:
        pipeline.append({"$match": {"$or": [
            {"profile.eng_test": None},
            {"profile.eng_test": {"$exists": False}},
            {"$and": [
                {"profile.eng_test":  eng_test.upper()},
                {"profile.eng_score": {"$gte": eng_lo, "$lte": eng_hi}},
            ]},
        ]}})
    count_res = list(col.aggregate(pipeline + [{"$count": "total"}]))
    total = count_res[0]["total"] if count_res else 0
    pipeline += [
        {"$group": {
            "_id":         "$university",
            "admit_count": {"$sum": 1},
            "rank":        {"$first": "$rank"},
            "rank_label":  {"$first": "$rank_label"},
            "courses":     {"$addToSet": "$course"},
            "schol_count":  {"$sum": {"$cond": [{"$eq": ["$got_scholarship", "Yes"]}, 1, 0]}},
            "profile_urls": {"$push": "$profile_url"},
        }},
        {"$addFields": {"rank_sort": {"$ifNull": ["$rank", 9999]}}},
        {"$sort": {"rank_sort": 1, "admit_count": -1}},
        {"$limit": limit},
    ]
    return total, list(col.aggregate(pipeline))


def eng_band(test, score):
    if not test or not score or test.upper() == "NONE": return None, None
    t = test.upper()
    if t == "IELTS":  return round(score - 0.5, 1), round(score + 0.5, 1)
    if t == "TOEFL": return score - 5, score + 5
    return None, None


def build_near_miss(base, we_lo, we_hi, eng_test, eng_score, seen):
    if not eng_test or not eng_score or eng_test.upper() in ("NONE", ""): return []
    t = eng_test.upper(); step = 0.5 if t == "IELTS" else 5; out = []
    for offset in [1, 2]:
        req = round(eng_score + step * offset, 1)
        if t == "IELTS" and req > 9.0: break
        if t == "TOEFL" and req > 120: break
        pipeline = [
            {"$match": base},
            {"$match": {"profile.work_exp_months": {"$gte": we_lo, "$lte": we_hi}}},
            {"$match": {"profile.eng_test": t, "profile.eng_score": {"$gte": req}}},
            {"$group": {
                "_id":         "$university",
                "admit_count": {"$sum": 1},
                "rank":        {"$first": "$rank"},
                "rank_label":  {"$first": "$rank_label"},
                "courses":     {"$addToSet": "$course"},
                "min_eng":     {"$min": "$profile.eng_score"},
            }},
            {"$match": {"admit_count": {"$gte": 3}}},
            {"$addFields": {"rank_sort": {"$ifNull": ["$rank", 9999]}}},
            {"$sort": {"rank_sort": 1, "admit_count": -1}},
            {"$limit": 3},
        ]
        for r in col.aggregate(pipeline):
            if r["_id"] in seen: continue
            actual = round(r["min_eng"], 1)
            label  = (f"IELTS {actual}+ required · you have {eng_score}"
                      if t == "IELTS"
                      else f"TOEFL {int(actual)}+ required · you have {int(eng_score)}")
            out.append(NearMiss(
                university=     r["_id"],
                course=         sorted(r["courses"])[0] if r["courses"] else "",
                rank_label=     r.get("rank_label"),
                gap_field=      "english_score",
                gap_label=      label,
                user_value=     eng_score,
                required_value= actual,
                admit_count=    r["admit_count"],
            ))
            seen.add(r["_id"])
    return out[:2]


@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    country_db = COUNTRY_MAP.get(req.country)
    course_db  = COURSE_MAP.get(req.parent_course)
    degree_db  = DEGREE_MAP.get(req.degree)

    if not country_db: raise HTTPException(400, f"Unknown country: '{req.country}'")
    if not course_db:  raise HTTPException(400, f"Unknown course: '{req.parent_course}'")
    if not degree_db:  raise HTTPException(400, f"Unknown degree: '{req.degree}'")

    we         = max(0, min(req.work_exp_months, 240))
    eng        = (req.english_test or "").strip() or None
    score      = req.english_score
    base       = {"country": country_db, "parent_course": course_db, "degree_group": degree_db}
    eng_lo, eng_hi = eng_band(eng, score)

    fallback   = False
    we_lo, we_hi = max(0, we - 18), we + 18
    total, rows  = run_pipeline(base, we_lo, we_hi, eng, eng_lo, eng_hi)

    if len(rows) < 6 and eng and eng.upper() not in ("NONE", ""):
        total, rows = run_pipeline(base, we_lo, we_hi, None, None, None); fallback = True
    if len(rows) < 6:
        we_lo, we_hi = max(0, we - 36), we + 36
        total, rows  = run_pipeline(base, we_lo, we_hi, None, None, None); fallback = True
    if len(rows) < 6:
        total, rows = run_pipeline(base, 0, 999, None, None, None); fallback = True
    if not rows:
        raise HTTPException(422, f"No data found for '{req.parent_course}' in {req.country}. "
                                  "Try a different course or country.")

    seen = set(); cards = []
    for r in rows:
        pct = math.floor(r["schol_count"] / r["admit_count"] * 100) if r["admit_count"] else 0
        # Deduplicate and take up to 3 real profile URLs
        seen_urls = set()
        sample = []
        for url in (r.get("profile_urls") or []):
            if url and url not in seen_urls:
                seen_urls.add(url)
                sample.append(url)
            if len(sample) == 3:
                break
        cards.append(OfferCard(
            university=      r["_id"],
            course=          sorted(r["courses"])[0] if r["courses"] else course_db,
            rank_label=      r.get("rank_label"),
            rank=            r.get("rank"),
            admit_count=     r["admit_count"],
            scholarship_pct= pct,
            sample_profiles= sample,
            abbr=            make_abbr(r["_id"]),
        ))
        seen.add(r["_id"])

    nm    = build_near_miss(base, we_lo, we_hi, eng, score, set(seen))
    parts = [req.degree, req.parent_course, req.country]
    if eng and eng.upper() not in ("NONE", "") and score: parts.append(f"{eng} {score}")
    if we > 0: parts.append(f"{we} mo exp")

    return PredictResponse(
        matched_profiles= total,
        results=          cards,
        near_miss=        nm,
        fallback_used=    fallback,
        context_label=    " · ".join(parts),
    )


@app.get("/health")
def health():
    try:
        _client.admin.command("ping")
        return {"status": "ok", "documents": col.count_documents({})}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Serve frontend — MUST be last, uses absolute path ─────────────────────────
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
