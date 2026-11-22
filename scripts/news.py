import json, os, re, time, html, urllib.request, datetime
MODEL = "openai/gpt-4o-mini"
MAX_NEW = 8
THEMES = ["bank", "pay", "multi", "inst", "rwa", "rlusd", "ai", "xrp", "other"]
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
UA = {"User-Agent": "Mozilla/5.0 (compatible; personal-reader; few requests per day)"}
def load(p, d):
 try:
  return json.load(open(p, encoding="utf-8"))
 except Exception:
  return d
xml = open("data/press-release.xml", encoding="utf-8").read()
items = []
for m in re.finditer(r"<url>(.*?)</url>", xml, re.S):
 loc = re.search(r"<loc>https://ripple\.com/ripple-press/([^/<]+)/?</loc>", m.group(1))
 mod = re.search(r"<lastmod>([^<]+)</lastmod>", m.group(1))
 if loc:
  s = re.sub(r"[^A-Za-z0-9_-]", "", loc.group(1))
  if s and not re.search(r"-(ja|ko|kr|pt)$", s):
   items.append((mod.group(1) if mod else "", s))
items.sort(key=lambda x: x[0], reverse=True)
slugs = [s for _, s in items][:40]
raw = load("data/news.json", [])
news = raw.get("items", []) if isinstance(raw, dict) else raw
done = {n["s"] for n in news if n.get("ai")}
todo = [s for s in slugs if s not in done][:MAX_NEW]
print("slugs", len(slugs), "done", len(done), "todo", len(todo))
def page(s):
 r = urllib.request.Request("https://ripple.com/ripple-press/%s/" % s, headers=UA)
 t = urllib.request.urlopen(r, timeout=40).read().decode("utf-8", "ignore")
 t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
 t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
 i = t.find("Press Releases")
 t = t[i + 14:] if i >= 0 else t
 m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), (20\d\d)", t[:600])
 d = "%s-%02d-%02d" % (m.group(3), MON[m.group(1)], int(m.group(2))) if m else ""
 return d, t[:5500]
SYS = ("You analyze official Ripple press releases for a Japanese individual who holds XRP long term. "
 "Answer ONLY with a JSON object, no markdown. Write all text values in plain, short Japanese sentences (desu/masu). "
 "No metaphors. No price predictions. Do not add facts that are not in the text. Mark inferences as likely, not certain. "
 "Keys: title_ja (Japanese title, max 45 chars), what (what happened, 2 sentences), "
 "impact (how this may affect Ripple's business and the size of its market over the next few years, 2-3 sentences), "
 "xrp (relation to demand for XRP itself: say whether the text mentions XRP or the XRP Ledger and whether XRP is actually used, 1-2 sentences), "
 "theme (one of: bank=licenses/regulation, pay=payments/treasury, multi=multichain/bridges, inst=institutional custody/prime/collateral, rwa=tokenization, rlusd=RLUSD stablecoin, ai=AI agents, xrp=XRP and XRPL features, other), "
 "stage (integer: 1 plan, 2 partnership or application, 3 approval or signed deal or acquisition, 4 live launch, 5 published numbers), "
 "xrp_mentioned (true or false).")
def ask(text):
 body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 700, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": text}]}).encode()
 r = urllib.request.Request("https://models.github.ai/inference/chat/completions", data=body, headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Content-Type": "application/json"})
 c = urllib.request.urlopen(r, timeout=90).read().decode("utf-8", "ignore").strip()
 try:
  j = json.loads(c)
  if isinstance(j, dict) and "choices" in j:
   c = j["choices"][0]["message"]["content"]
 except Exception:
  pass
 return json.loads(c[c.find("{"):c.rfind("}") + 1])
def clip(v, n):
 return re.sub(r"\s+", " ", str(v or "")).strip()[:n]
added = 0
for s in todo:
 rec = {"s": s, "d": "", "ai": False}
 try:
  rec["d"], text = page(s)
 except Exception as e:
  print("page failed", s, type(e).__name__)
  continue
 try:
  a = ask(text)
  st = int(a.get("stage") or 0)
  rec.update({"ai": True, "ja": clip(a.get("title_ja"), 60), "what": clip(a.get("what"), 260), "impact": clip(a.get("impact"), 380), "xrp": clip(a.get("xrp"), 260), "th": a.get("theme") if a.get("theme") in THEMES else "other", "st": st if 1 <= st <= 5 else 0, "xm": bool(a.get("xrp_mentioned"))})
  added += 1
 except Exception as e:
  print("model failed", s, type(e).__name__, str(e)[:160])
  if "429" in str(e):
   break
 news = [n for n in news if n["s"] != s] + [rec]
 time.sleep(5)
order = {s: i for i, s in enumerate(slugs)}
news = [n for n in news if n["s"] in order]
news.sort(key=lambda n: (n.get("d") or "", -order[n["s"]]), reverse=True)
json.dump({"updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "model": MODEL, "items": news[:60]}, open("data/news.json", "w", encoding="utf-8"), ensure_ascii=False)
print("analyzed", added, "total", len(news))
