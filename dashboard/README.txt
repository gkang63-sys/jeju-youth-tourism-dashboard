청년층 제주 관광 현황 대시보드

[실행]
index.html을 더블클릭하면 브라우저에서 열린다.
서버, 설치, 인터넷 연결이 필요 없다.
index.html, data.js, reviews.js는 같은 폴더에 있어야 한다.

[파일]
index.html            화면과 계산 코드. 외부 라이브러리를 쓰지 않는다.
data.js               원본 엑셀에서 만든 데이터 (약 13MB).
jeju_boundary.json    지도용 읍면동 경계. data.js를 다시 만들 때만 쓴다.
build_data.py         원본 엑셀을 읽어 data.js를 만든다. 표준 라이브러리만 쓴다.
build_boundary.py     경계 원본에서 제주만 골라 jeju_boundary.json을 만든다.
verify_dashboard.py   브라우저로 필터를 조작해 화면 값을 원본과 대조한다.
reviews.js            온라인 후기 분류 결과. 대시보드가 읽는다.
naver_blog_posts.json 블로그 검색 API 수집 원본 (작성일, 제목, 요약, 링크).
collect_reviews.py    NAVER API HUB로 블로그 검색 결과를 모은다. 키는 .env에서만 읽는다.
build_reviews.py      수집 원본을 규칙으로 분류해 reviews.js를 만든다.
.env                  API 키. 다른 사람에게 넘기거나 올리지 않는다 (.gitignore에 등록됨).

[온라인 후기 다시 모을 때]
python collect_reviews.py --check   인증만 1회 확인
python collect_reviews.py           전체 수집 (호출 약 400회)
python build_reviews.py             분류해 reviews.js 생성

[원본 엑셀이 바뀌었을 때]
1. 이 폴더의 바로 위 폴더에 같은 이름의 엑셀을 둔다.
2. python build_data.py
3. 브라우저를 새로 고친다.
열 이름이 달라지면 build_data.py가 멈추고 어느 열인지 알려 준다.

[검증]
pip install playwright 후, Chrome이 설치된 PC에서
python verify_dashboard.py
실패 항목이 있으면 끝에 목록으로 나온다.

[지도 경계 출처]
통계청 SGIS 행정동 경계 (공공누리 제1유형)를 가공한
vuski/admdongkor ver20261001 (CC BY 4.0)
https://github.com/vuski/admdongkor
표시용으로 약 70m 단위로 단순화했다. 면적 계산에는 쓸 수 없다.

[자료 기준]
화면 맨 아래 "자료 기준"과 상위 폴더의 파일&데이터구조.txt를 참고한다.
