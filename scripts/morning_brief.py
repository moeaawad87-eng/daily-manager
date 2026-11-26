"""Morning brief: reads Google News for each topic in news-topics.txt,
asks Gemini (free tier, no search grounding needed) to pick the 3 items
that matter most, and writes news.json for the app to show."""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

KEY = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'").strip()
if not KEY:
    sys.exit("GEMINI_API_KEY secret is missing")
UA = {"User-Agent": "Mozilla/5.0 (daily-manager morning brief)"}

def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:  # show Google's reason (never the key) in the log
        body = e.read().decode("utf-8", "ignore")[:400]
        print("HTTP", e.code, "from", url.split("?")[0], "-", body.replace(KEY, "***") if KEY else body)
        raise

topics = [l.strip() for l in open("news-topics.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
items, seen = [], set()
for t in topics:
    time.sleep(2)  # Google News answers 429 if asked too fast
    q = urllib.parse.quote(t + " when:3d")
    try:
        root = ET.fromstring(get(f"https://news.google.com/rss/search?q={q}&hl=en-AE&gl=AE&ceid=AE:en"))
    except Exception as e:
        print("skip topic", t, e); continue
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        key = re.sub(r"\W+", "", title.lower())[:60]
        if not title or key in seen: continue
        seen.add(key)
        items.append({"n": len(items), "topic": t, "title": title,
                      "source": (it.findtext("source") or "").strip(),
                      "date": (it.findtext("pubDate") or "")[:16],
                      "link": it.findtext("link") or ""})
        if sum(1 for x in items if x["topic"] == t) >= 12: break
print(len(items), "headlines from", len(topics), "topics")
if not items:
    sys.exit("no headlines found")

# pick a free model the same way the app does
models = json.loads(get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key=" + KEY))["models"]
names = [m["name"].split("/")[-1] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
ok = [n for n in names if n.startswith("gemini-") and "flash" in n and not re.search(r"image|tts|live|audio|thinking|exp|vision|embedding", n)]
model = ("gemini-flash-lite-latest" if "gemini-flash-lite-latest" in ok else
         (sorted([n for n in ok if "lite" in n and "preview" not in n]) or sorted(ok))[-1])
print("model", model)

prompt = f"""Mohamad is Business Development Manager at The Gardenian For Garden Services, a landscaping company in Abu Dhabi
(softscape, hardscape, irrigation, swimming pools, indoor plants, maintenance contracts). He wants to win more projects and
later start his own business.
Here are today's news headlines (JSON): {json.dumps([{k: x[k] for k in ('n','title','source','date')} for x in items], ensure_ascii=False)}

Pick the 3 headlines that matter most for his work and sales (new projects to bid on, market changes, useful tools).
Prefer UAE news. Return ONLY JSON:
{{"picks":[{{"n":number,
  "en":{{"title":"short clear title","summary":"2 short sentences of what happened, based only on the headline","why":"1 sentence: why it matters for Mohamad / The Gardenian"}},
  "ar":{{"title":"...","summary":"...","why":"..."}} }}]}}
The "ar" texts are the same content in clear Modern Standard Arabic. Do not invent facts that are not in the headline."""
body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}).encode()
for attempt in range(3):
    try:
        out = json.loads(get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                             data=body, headers={"Content-Type": "application/json"}))
        break
    except Exception as e:
        print("gemini error", e); time.sleep(20)
else:
    sys.exit("Gemini failed")
text = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
picks = json.loads(re.search(r"\{[\s\S]*\}", text).group(0))["picks"][:3]

result = {"date": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d"),
          "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
          "topics": topics, "items": []}
for p in picks:
    src = items[int(p["n"])] if 0 <= int(p["n"]) < len(items) else {}
    result["items"].append({"en": p.get("en", {}), "ar": p.get("ar", {}),
                            "source": src.get("source", ""), "link": src.get("link", ""), "date": src.get("date", "")})
# ---------- Claude news channel: new Claude / Anthropic features, explained for Mohamad ----------
def claude_news():
    qs = ["Anthropic Claude new feature", "Anthropic announces Claude", "Claude AI update"]
    heads, seen2 = [], set()
    for t in qs:
        time.sleep(2)
        try:
            root = ET.fromstring(get("https://news.google.com/rss/search?q=" + urllib.parse.quote(t + " when:7d") + "&hl=en-US&gl=US&ceid=US:en"))
        except Exception as e:
            print("skip claude query", t, e); continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            key = re.sub(r"\W+", "", title.lower())[:60]
            if not title or key in seen2: continue
            seen2.add(key)
            heads.append({"n": len(heads), "title": title, "source": (it.findtext("source") or "").strip(),
                          "date": (it.findtext("pubDate") or "")[:16], "link": it.findtext("link") or ""})
            if len(heads) >= 40: break
    print(len(heads), "Claude headlines")
    if not heads: return []
    p2 = f"""Mohamad uses Claude (the AI assistant by Anthropic) every day for his landscaping sales work in Abu Dhabi
(quotations, BOQs, reports, emails, small apps). He wants to hear about NEW Claude features and changes as soon as they come out.
Headlines from the last 7 days (JSON): {json.dumps([{k: x[k] for k in ('n','title','source','date')} for x in heads], ensure_ascii=False)}

Pick up to 3 headlines that announce a real NEW Claude feature, model, product or important change from Anthropic.
Skip opinion pieces, stock/funding news, lawsuits and old features. If nothing is truly new, return an empty list.
Return ONLY JSON:
{{"picks":[{{"n":number,
  "en":{{"title":"short clear title","summary":"1-2 short sentences on what is new, based only on the headline","why":"1 sentence: how Mohamad could use it in his work"}},
  "ar":{{"title":"...","summary":"...","why":"..."}} }}]}}
The "ar" texts are the same content in clear, simple Modern Standard Arabic. Do not invent facts that are not in the headline."""
    b2 = json.dumps({"contents": [{"parts": [{"text": p2}]}],
                     "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}).encode()
    o2 = json.loads(get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                        data=b2, headers={"Content-Type": "application/json"}))
    t2 = "".join(x.get("text", "") for x in o2["candidates"][0]["content"]["parts"])
    out2 = []
    for pk in json.loads(re.search(r"\{[\s\S]*\}", t2).group(0)).get("picks", [])[:3]:
        n = int(pk.get("n", -1))
        if not 0 <= n < len(heads): continue
        h = heads[n]
        out2.append({"en": pk.get("en", {}), "ar": pk.get("ar", {}), "source": h["source"], "link": h["link"], "date": h["date"]})
    return out2

# ---------- Anthropic official updates: every post on anthropic.com / claude.com in the last 14 days ----------
def anthropic_official():
    q = urllib.parse.quote("(site:anthropic.com OR site:claude.com) when:14d")
    root = ET.fromstring(get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"))
    rows, seen3 = [], set()
    for it in root.iter("item"):
        title = re.sub(r"\s+[-|\u2013]\s+(Anthropic|Claude|claude\.com|anthropic\.com)$", "", (it.findtext("title") or "").strip())
        key = re.sub(r"\W+", "", title.lower())[:60]
        if not title or key in seen3: continue
        seen3.add(key)
        rows.append({"en": title, "ar": "", "date": (it.findtext("pubDate") or "")[:16], "link": it.findtext("link") or ""})
        if len(rows) >= 10: break
    print(len(rows), "official Anthropic posts")
    if rows:  # Arabic titles; if this fails we keep English only
        try:
            pr = ("Translate each English title to short, clear Modern Standard Arabic. Keep product names (Claude, Anthropic, Opus, Sonnet, Haiku) in English. "
                  'Return ONLY JSON {"ar":["...", ...]} in the same order: ' + json.dumps([r["en"] for r in rows], ensure_ascii=False))
            bb = json.dumps({"contents": [{"parts": [{"text": pr}]}],
                             "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}).encode()
            oo = json.loads(get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                                data=bb, headers={"Content-Type": "application/json"}))
            tt = "".join(x.get("text", "") for x in oo["candidates"][0]["content"]["parts"])
            for r, a in zip(rows, json.loads(re.search(r"\{[\s\S]*\}", tt).group(0)).get("ar", [])):
                r["ar"] = str(a)
        except Exception as e:
            print("translate failed:", e)
    return rows

try:
    result["anthropic"] = anthropic_official()
except Exception as e:
    print("Anthropic official failed:", e)
    result["anthropic"] = []

try:
    result["claude"] = claude_news()
except Exception as e:  # never let this break the main brief
    print("Claude news failed:", e)
    result["claude"] = []

json.dump(result, open("news.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False)[:600])
