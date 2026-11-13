"""Morning brief: reads Google News for each topic in news-topics.txt,
asks Gemini (free tier, no search grounding needed) to pick the 3 items
that matter most, and writes news.json for the app to show."""
import json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not KEY:
    sys.exit("GEMINI_API_KEY secret is missing")
UA = {"User-Agent": "Mozilla/5.0 (daily-manager morning brief)"}

def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

topics = [l.strip() for l in open("news-topics.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
items, seen = [], set()
for t in topics:
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
json.dump(result, open("news.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False)[:600])
