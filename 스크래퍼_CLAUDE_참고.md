# 혁신의숲 기업 등록 자동화 — 스크래퍼

## 이 프로젝트가 하는 일

혁신의숲에 신규 기업을 등록할 때 필요한 11개 항목을 자동 수집한다.
수집 결과는 **검수 작업대(HTML)** 에 붙여넣는 JSON으로 출력하고, 사람이 검수 후 어드민에 입력한다.
완전 자동화가 목표가 아니라 **"기계가 후보를 찾고 사람이 승인"** 하는 구조다.

## 절대 원칙 (위반 시 작업 무효)

1. **실제 확인된 정보만 출력한다.** 추측·생성·조합 금지.
2. **URL은 실제로 본 것만.** 홈페이지 주소에 제품명을 붙여 만드는 식의 조합은 절대 금지.
   - 과거 실제 사고: `stradvision.com/svnet/`, 로고 경로를 임의 생성 → 둘 다 존재하지 않는 주소였음
3. **확인 못 한 항목은 비운다.** 억지로 채우지 않는다. 비어 있으면 사람이 채우지만, 가짜가 들어가면 그대로 등록되어 더 위험하다.
4. **유사 사명 주의.** 반드시 대표자명·사업자번호로 교차 확인.
   - 실제 사례: "씨쓰리브이"(대표 강연주) vs "씨브이쓰리"(대표 양진호) — 완전히 다른 회사
   - 실제 사례: "(주)알록"이 뷰티디바이스/폐업 전자상거래/의료기기 3곳 존재

## 현재 상태

### 동작 확인된 것 (로컬 픽스처)
- 규칙 엔진: 이메일 8/8, 전화 8/8, 사업자번호 3/3 통과 (`test_rules.py`)
- SPA 렌더링: 일반 fetch 287바이트 → Playwright 렌더링 후 전체 추출
- 멀티페이지 크롤링: `/contact`의 전화·이메일 수집 확인
- 로고 실측: 512/400/57px 각각 정확 판정 (57px는 화질미달 경고)

### 미검증 — **여기부터 작업 필요**
- [ ] **실제 기업 사이트 E2E 테스트** (작성 환경이 외부망 차단이라 못 함)
  - 테스트 대상: `https://stradvision.com` (JS 렌더링, 푸터에 사업자번호 506-81-90203, contact@stradvision.com 있음)
  - 테스트 대상: `https://physiorobo.co.kr` (WordPress, 로고가 57x57 저화질, 이메일 okpt@hanmail.net → 차단되어야 정상)
  - 테스트 대상: `https://www.playtown.biz/` (Wix, 이메일이 `/business` 하위 페이지에 있음, 사업자번호는 **이미지**라 못 읽음)
- [ ] 쿠키 배너·lazy-load 푸터 대응 (대기 로직 조정 필요할 수 있음)
- [ ] 이미지로 된 사업자등록번호 → OCR 검토 (플레이타운 사례)

## 알려진 제약

| 코드 | 제약 | 상태 |
|---|---|---|
| A-1 | JS 렌더링 사이트 푸터 못 읽음 | **해결** — Playwright |
| A-2 | 로고 크기·화질 사전 확인 불가 | **해결** — PIL 실측 |
| A-3 | URL 생존 확인 불가 | **해결** — `check_url_alive()` |
| A-4 | 검색 요약엔 푸터 정보 없음 | 홈페이지 직접 방문으로 해결 |
| A-6 | 대표자 SNS 동명이인 | **미해결, 해결 어려움** — 사람 확인 항목으로 두는 게 맞음 |
| A-7 | 공식 기업정보 DB 없음 | 미해결 — 국세청/NICE API 연동 검토 |

## 업무 규칙 (코드에 구현됨, 변경 시 지시문도 같이 고칠 것)

### 전화
유선만. 지역번호형(02·031·055·070) + 대표번호형(1588·1600).
**010 휴대폰은 등록 불가** → `phone_rejected`로 분리해서 사유 표시.

### 이메일
- 우선순위 상: `support info hi hello contact cs help ask connect` + 기업명@
- 우선순위 중: `ceo sales marketing ir`
- **차단**: `tax bill finance fn account` (세금·회계)
- **개인 도메인 예외 규칙**: gmail·naver·hanmail 등이라도 아이디가 회사 도메인/사명과 통하면
  `검수필요`로 통과시키고 사유를 표시한다.
  - 통과 예: `playtown.biz` + `playtown808@gmail.com`
  - 차단 예: `physiorobo.co.kr` + `okpt@hanmail.net`
- 개인정보 판매 이슈가 있어 **개인 이메일 등록은 법적 리스크**. 엄격히 지킬 것.

### 로고
후보 순서: `og:image` → `apple-touch-icon` → `header img` → `favicon`.
가장 큰 것 선택. 짧은 변 200px 미만이면 `low_res=True` (256 확대 시 깨짐).

### 서비스
(2026-09-04 한벤투 서비스 수집 로직 이식 — 전문은 `.claude/skills/company-research/SKILL.md` "서비스 수집 규칙")
실제 **구동되는** 일반 사용자용 웹·앱·자사몰만 (기업 홈페이지·소개용 랜딩·B2B 소개 페이지 ✗). B2B는 "구동되는 별도 URL이 없어서" 제외하는 것이지 B2B라서 제외하는 게 아님 — 반드시 1회는 검색 확인.
앱은 `play.google.com`에서 **퍼블리셔(개발사)명 확인** → `publisher`에 기록, 개발사 페이지에서 파생 앱 전수 나열. 웹+앱이 같은 서비스면 한 항목(`type:"웹·앱"`). 패키지명은 작업대가 `playUrl`의 `id=`에서 추출.
  - 실제 사례: MCN "플레이타운" 검색 시 메타버스 게임 "플레이타운"(개발사 1zlabs)이 나옴. 다른 회사.
오프라인 시설·매장, iOS 앱스토어 URL은 수집 안 함. 서비스 없으면 `services` 생략 + `servicesNote`에 확인 경로.

## 출력 형식

검수 작업대가 먹는 JSON. **빈 값은 키 자체를 생략**한다.

```json
[{"name":"기업명","bizno":"000-00-00000","ceo":"대표자","homepage":"https://...",
  "logo":"https://...","phone":"02-000-0000","email":"contact@...",
  "sns":["https://linkedin.com/..."],
  "services":[{"name":"서비스명","nameEn":"영문명","type":"웹·앱","webUrl":"https://...",
    "playUrl":"https://play.google.com/store/apps/details?id=...",
    "publisher":"스토어 개발사명","note":"비고"}],
  "servicesNote":"서비스 없을 때만 — 업종·확인 경로"}]
```

## 구조

```
company_scraper.py    스크래퍼 본체 (Playwright)
test_rules.py         규칙 엔진 단위테스트
fixtures/             로컬 테스트용 픽스처 (SPA 재현)
  basic/              기본 케이스 (푸터에 전부 있음)
  edge/               예외 (010 전화, 회사 gmail, 57px 로고)
  multipage/          /contact 에 연락처가 있는 구조
```

## 실행

```bash
pip install -r requirements.txt && python -m playwright install chromium

python test_rules.py                                    # 규칙 테스트
cd fixtures/multipage && python -m http.server 8897 &   # 로컬 픽스처
python company_scraper.py http://127.0.0.1:8897/ --name realcompany

python company_scraper.py https://stradvision.com --name stradvision --ceo 김준환 --workbench
```

## 다음에 붙일 것 (우선순위)

1. **실제 사이트 E2E 검증** — 위 3개 사이트로 돌려보고 셀렉터 보정
2. **검색 API** (Parallel.ai 등) — 기업 식별·뉴스 수집 보강.
   뉴스는 제목/URL/언론사/보도일 4개가 필요하니, 언론사·발행일이 구조화돼 나오는지 먼저 확인할 것
3. **Claude API** — 소개글 양식 정리, 카테고리·키워드 추천.
   키워드 284개 목록을 매번 보내야 하므로 **배치로 묶어 목록을 1회만 전송**. Batch API 쓰면 비용 절반
4. NICE/국세청 사업자정보 API (A-7)

**API 키는 환경변수로.** 코드·저장소에 하드코딩 금지.
