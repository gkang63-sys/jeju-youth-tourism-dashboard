# 청년층 제주 관광 현황 대시보드

청년층은 제주에서 어떤 여행을 하고 있을까? 20대 방문 추이, 지역별 방문, 인기 장소, 검색어, 블로그 후기를 한 화면에서 봅니다. 기간과 지역 필터를 바꾸면 지표와 차트가 함께 바뀝니다.

서버와 API 키 없이 동작하는 정적 페이지입니다. 모든 집계는 브라우저에서 합니다.

## 실행

`dashboard/index.html`을 브라우저로 엽니다. `index.html`, `data.js`, `reviews.js`가 같은 폴더에 있어야 합니다.

## 배포 상태

2026-11-04에 저장소를 공개로 바꿨습니다. 저장소에 올라간 `dashboard/data.js`(관광 데이터)와 `dashboard/reviews.js`(블로그 후기 분류 결과)는 누구나 볼 수 있습니다.

GitHub Pages로는 아직 배포하지 않습니다. 배포 설정 파일 `.github/workflows/deploy-pages.yml`은 로컬에만 있고 저장소에는 올리지 않았습니다. 배포할 때는 이 파일을 올리고, 저장소 Settings → Pages의 Source를 GitHub Actions로 정한 뒤, Actions 탭에서 Run workflow로 직접 실행합니다.

## 데이터 다시 만들기

| 작업 | 필요한 것 | 명령 |
|---|---|---|
| 관광 데이터 갱신 | 저장소 최상위에 원본 엑셀 7개 (저장소에 없음) | `python dashboard/build_data.py` |
| 블로그 후기 수집 | `dashboard/.env` (`.env.example` 복사 후 키 입력) | `python dashboard/collect_reviews.py` |
| 블로그 후기 분류 | 수집 결과 `naver_blog_posts.json` | `python dashboard/build_reviews.py` |
| 화면 값 검증 | 위 자료 전부, `pip install playwright`, Chrome | `python dashboard/verify_dashboard.py` |

## 주의

- API 키를 파일에 직접 쓰거나 올리지 마세요. 키는 `dashboard/.env`에만 두고, 이 파일은 `.gitignore`로 제외되어 있습니다.
- 블로그 후기는 제목과 요약을 낱말 규칙으로 분류한 것입니다. 작성자 연령을 확인한 것이 아니며, 건수는 대략의 크기로만 봐야 합니다.

## 출처

- 관광 데이터 (엑셀 7개 모두): 제주 관광 빅데이터 플랫폼(비짓제주)
- 온라인 후기: 네이버 블로그 검색 API (제목·요약과 원문 링크)
- 지도 경계: 통계청 SGIS 행정동 경계 (공공누리 제1유형)를 가공한 [vuski/admdongkor](https://github.com/vuski/admdongkor) (CC BY 4.0)
