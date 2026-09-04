# 혁신의숲 등록 데이터로 라벨별 판별 n-gram 사전(LEX)과 유사사례 인덱스를 굽는다.
# 핵심 변경: '소개글끼리 비교'가 아니라 '라벨을 예측하는 조각'을 배운다.
#           → 붙여넣는 원문이 길고 거칠어도 판별 조각만 걸리면 맞춘다.
import openpyxl, io, re, math, json, collections, sys

SRC = r'C:/Users/user/Downloads/corporation_20260831145255.xlsx'
wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
rows = list(wb['기업정보'].iter_rows(values_only=True))
hdr, data = rows[0], rows[1:]
ix = {h: i for i, h in enumerate(hdr)}
def g(r, k):
    if k not in ix or r[ix[k]] is None: return ''
    return str(r[ix[k]]).replace('_x000D_', ' ').strip()

html = io.open('소개글_카테고리_키워드_도우미.html', encoding='utf-8').read()
official = set(m.group(1) for m in re.finditer(r'\["(.*?)","', html.split('const KW = [')[1].split('\n];')[0]))

kwfreq = collections.Counter()
for r in data:
    for x in g(r, '키워드').split(','):
        if x.strip(): kwfreq[x.strip()] += 1
# 기업명이 키워드 칸에 잘못 들어간 값 제거 (공식 목록 밖 + 희소)
valid_kw = {k for k, c in kwfreq.items() if k in official or c >= 5}

CATS = ['광고/마케팅','교육','금융/보험/핀테크','게임','모빌리티/교통','물류','부동산/건설','뷰티/화장품',
'AI/딥테크/블록체인','소셜미디어/커뮤니티','여행/레저','유아/출산','인사/비즈니스/법률','제조/하드웨어','커머스',
'콘텐츠/예술','통신/보안/데이터','패션','푸드/농업','환경/에너지','홈리빙/펫','헬스케어/바이오','피트니스/스포츠','기타']
KWS = sorted(valid_kw)
ci = {c: i for i, c in enumerate(CATS)}
ki = {k: i for i, k in enumerate(KWS)}

def norm(s): return re.sub(r'\s+', '', s.lower())
def grams(s, ns=(2, 3, 4)):
    s = norm(s); out = set()
    for n in ns:
        for i in range(len(s) - n + 1):
            t = s[i:i+n]
            if re.search(r'[가-힣a-z0-9]', t): out.add(t)
    return out

ACTS = []
docs = []          # [기업명, 소개글, [카테고리], [키워드], 액션idx]
for r in data:
    d = g(r, '기업설명')
    if not d or len(d) < 8: continue
    # 기업설명 칸에 내부 메모가 들어간 행 제외 (학습 잡음)
    if not d.endswith('기업') and not d.endswith('기업.'): continue
    if re.search(r'비노출|필요 ?없|확인 ?필요|데이터 ?없|테스트|미확인|삭제|중복', d): continue
    cl = [ci[x.strip()] for x in g(r, '카테고리').split(',') if x.strip() in ci]
    kl = [ki[x.strip()] for x in g(r, '키워드').split(',') if x.strip() in ki]
    if not cl and not kl: continue
    m = re.search(r'([가-힣]+(?:\s*및\s*[가-힣]+)*)하는 기업$', d)
    a = -1
    if m:
        v = m.group(1).strip()
        if v not in ACTS: ACTS.append(v)
        a = ACTS.index(v)
    docs.append([g(r, '기업명'), d, cl, kl, a])

N = len(docs)
print('학습 문서 %d건 / 카테고리 %d / 키워드 %d / 액션 %d' % (N, len(CATS), len(KWS), len(ACTS)))

# ── 1) 라벨별 판별 n-gram 학습 (log-lift) ──────────────────────────────
dfa = collections.Counter()                       # n-gram 문서빈도
pair_c = collections.defaultdict(collections.Counter)   # 카테고리별
pair_k = collections.defaultdict(collections.Counter)   # 키워드별
docg = []
for i, (nm, d, cl, kl, a) in enumerate(docs):
    gs = grams(d)
    docg.append(gs)
    for t in gs:
        dfa[t] += 1
        for c in cl: pair_c[c][t] += 1
        for k in kl: pair_k[k][t] += 1

cat_n = collections.Counter()
kw_n = collections.Counter()
for nm, d, cl, kl, a in docs:
    for c in cl: cat_n[c] += 1
    for k in kl: kw_n[k] += 1

def learn(pairs, label_n, min_a, min_lift, top):
    """라벨을 실제로 가리키는 조각만 남긴다 (lift = 그 조각이 있을 때 라벨 확률 / 기본 확률)"""
    out = {}
    for L, cnt in pairs.items():
        p = label_n[L] / N
        scored = []
        for t, a in cnt.items():
            if a < min_a: continue
            b = dfa[t]
            lift = (a / b) / p
            if lift < min_lift: continue
            scored.append((t, round(math.log(lift) * math.log(1 + a), 3)))
        scored.sort(key=lambda x: -x[1])
        if scored: out[L] = scored[:top]
    return out

# '기타서비스'처럼 무엇이든 걸리는 잡동사니 라벨은 판별에서 뺀다
JUNK = {'기타서비스', '기타'}
for _j in JUNK:
    if _j in ci: pair_c.pop(ci[_j], None)
    if _j in ki: pair_k.pop(ki[_j], None)
LEX_C = learn(pair_c, cat_n, 4, 2.0, 120)
LEX_K = learn(pair_k, kw_n, 3, 3.0, 60)
print('카테고리 사전 %d개 라벨 / 키워드 사전 %d개 라벨' % (len(LEX_C), len(LEX_K)))

# 런타임이 빠르도록 뒤집어 저장: ngram -> [[labelIdx, weight], ...]
def invert(lex):
    inv = collections.defaultdict(list)
    for L, lst in lex.items():
        for t, w in lst: inv[t].append([L, w])
    return {t: v for t, v in inv.items()}
INV_C, INV_K = invert(LEX_C), invert(LEX_K)
print('판별 조각: 카테고리 %d개, 키워드 %d개' % (len(INV_C), len(INV_K)))

# ── 2) 유사사례 인덱스 ────────────────────────────────────────────────
# 라벨 예측은 위 사전이 하고, 여기는 '실제 사례 보여주기'와 액션 투표만 담당한다.
# 전부 실을 필요가 없으므로 카테고리별로 고르게 뽑아 용량을 줄인다.
import random as _r
_r.seed(11)
by_cat = collections.defaultdict(list)
for i, (nm, d, cl, kl, a) in enumerate(docs):
    by_cat[cl[0] if cl else -1].append(i)
PER = 420
keep = []
for c, lst in by_cat.items():
    keep.extend(lst if len(lst) <= PER else _r.sample(lst, PER))
keep.sort()
sub_docs = [docs[i] for i in keep]
CAP = int(len(sub_docs) * 0.01)
post = collections.defaultdict(list)
for j, i in enumerate(keep):
    for t in docg[i]:
        if len(t) >= 3 and 4 <= dfa[t] <= int(N * 0.01): post[t].append(j)
IDX = {t: v for t, v in post.items() if len(v) >= 2}
print('유사사례 %d건 / 인덱스 %d조각 / %d포스팅' % (len(sub_docs), len(IDX), sum(len(v) for v in IDX.values())))

# ── 3) 카테고리별 최빈 액션 ────────────────────────────────────────────
catact = collections.defaultdict(collections.Counter)
for nm, d, cl, kl, a in docs:
    if a >= 0 and cl: catact[CATS[cl[0]]][ACTS[a]] += 1
ACT = {c: cc.most_common(1)[0][0] for c, cc in catact.items() if cc}

# ── 실제 등록 소개글의 '목적어 구절' 사전 ────────────────────────────
# "~을 운영하는 기업"의 ~~ 자리에 진짜로 쓰이는 말만 모은다.
# 원문에서 "주요 서비스" 같은 껍데기를 잡던 문제를 이걸로 막는다.
PTYPES = ['플랫폼','서비스','솔루션','브랜드','앱','시스템','제품','콘텐츠','기기','장비','소프트웨어',
          '스토어','마켓','설비','부품','소재','키트','모듈','로봇','센서','기술','상품','도구','엔진']
SHELL = {'등의','및','그','이','저','다양한','여러','각종','모든','주요','핵심','대표','대표적인','전체',
         '기존','최근','새로운','해당','관련','이번','위의','다음'}
phr = collections.Counter()
for r in data:
    d = g(r, '기업설명')
    if not d.endswith('기업'): continue
    m = re.match(r'^(.*?)(?:을|를)\s*[가-힣, 및]+하는 기업$', d)
    if not m: continue
    obj = re.sub(r"['‘’\"“”][^'‘’\"“”]{1,20}['‘’\"“”]", ' ', m.group(1))   # 서비스명 제거
    toks = re.sub(r'[·,/]', ' ', obj).split()
    for i, t in enumerate(toks):
        if not any(t.endswith(T) for T in PTYPES): continue
        for back in (1, 2, 3):
            if i - back < 0: break
            seg = toks[i-back:i+1]
            if seg[0] in SHELL: continue
            cand = ' '.join(seg)
            if 3 <= len(cand) <= 24: phr[cand] += 1
PHR = {k: v for k, v in phr.items() if v >= 2}
print('제품 구절 사전 %d개 (예: %s)' % (len(PHR), ', '.join(list(PHR)[:5])))

TYPES = ['플랫폼','서비스','솔루션','브랜드','앱','시스템','제품','콘텐츠','기기','장비','소프트웨어','스토어','마켓','설비','부품','소재']
typef = collections.Counter()
for nm, d, cl, kl, a in docs:
    for t in TYPES:
        if t in d: typef[t] += 1

kwcat = collections.defaultdict(collections.Counter)
for nm, d, cl, kl, a in docs:
    for k in kl:
        for c in cl: kwcat[k][c] += 1
KWCAT = [ (kwcat[i].most_common(1)[0][0] if kwcat.get(i) else 23) for i in range(len(KWS)) ]

model = {'docs': sub_docs, 'kwcat': KWCAT, 'idx': {t: ','.join(map(str, v)) for t, v in IDX.items()},
         'cats': CATS, 'kws': KWS, 'act': ACT, 'acts': ACTS,
         'types': {t: round(c / N, 4) for t, c in typef.most_common()},
         'lexC': INV_C, 'lexK': INV_K, 'phr': PHR}
for key in ['docs', 'idx', 'lexC', 'lexK']:
    b = len(json.dumps(model[key], ensure_ascii=False, separators=(',', ':')).encode())
    print('  %-5s %.2f MB' % (key, b / 1048576))
js = 'const MODEL=' + json.dumps(model, ensure_ascii=False, separators=(',', ':')) + ';\n'
io.open('학습모델.js', 'w', encoding='utf-8').write(js)
print('모델 %.2f MB' % (len(js.encode()) / 1048576))

# ── 홀드아웃 평가: 90%로 사전을 다시 학습해 나머지 10%(미학습)로 측정 ──
import random
random.seed(7)
test = set(random.sample(range(N), N // 10))
tr_dfa = collections.Counter(); tr_c = collections.defaultdict(collections.Counter)
tr_k = collections.defaultdict(collections.Counter); tr_cn = collections.Counter(); tr_kn = collections.Counter()
NT = 0
for i, (nm, d, cl, kl, a) in enumerate(docs):
    if i in test: continue
    NT += 1
    for t in docg[i]:
        tr_dfa[t] += 1
        for c in cl: tr_c[c][t] += 1
        for k in kl: tr_k[k][t] += 1
    for c in cl: tr_cn[c] += 1
    for k in kl: tr_kn[k] += 1
def learn2(pairs, ln, mina, minlift, top):
    out = {}
    for L, cnt in pairs.items():
        p = ln[L] / NT
        sc = []
        for t, a in cnt.items():
            if a < mina: continue
            lift = (a / tr_dfa[t]) / p
            if lift < minlift: continue
            sc.append((t, math.log(lift) * math.log(1 + a)))
        sc.sort(key=lambda x: -x[1])
        if sc: out[L] = sc[:top]
    return out
INV_C = invert(learn2(tr_c, tr_cn, 4, 2.0, 120))
INV_K = invert(learn2(tr_k, tr_kn, 3, 3.0, 60))
test = list(test)
def predict(text, inv, topn):
    hits = collections.defaultdict(dict)
    for t in grams(text):
        for L, w in inv.get(t, []): hits[L][t] = w
    sc = collections.Counter()
    for L, hm in hits.items():          # 겹치는 조각은 한 번만 (런타임과 동일)
        kept = []
        for gm in sorted(hm, key=len, reverse=True):
            if any(gm in k for k in kept): continue
            kept.append(gm); sc[L] += hm[gm]
    return [L for L, _ in sc.most_common(topn)]
c1 = c3 = 0; nc = 0; kcov = 0; ktot = 0
for i in test:
    nm, d, cl, kl, a = docs[i]
    if cl:
        nc += 1
        p = predict(d, INV_C, 3)
        if p and p[0] in cl: c1 += 1
        if any(x in cl for x in p): c3 += 1
    if kl:
        p = predict(d, INV_K, 5)
        kcov += len(set(p) & set(kl)); ktot += len(kl)
print('\n[평가 %d건] 카테고리 1순위 적중 %.1f%% / 상위3 안 %.1f%%' % (nc, 100*c1/nc, 100*c3/nc))
print('[평가] 키워드 상위5가 실제 키워드를 덮은 비율 %.1f%%' % (100*kcov/ktot))
