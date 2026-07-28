# 근무표 도구 자동 동기화 버전

이 버전은 브라우저에서 파일을 선택하지 않습니다. GitHub Actions가 Meditong 근무표 페이지를 주기적으로 받아 `data/YYYY-MM.html`과 `data/manifest.json`을 갱신하고, `index.html`은 그 데이터를 읽어 년월 선택 목록을 표시합니다.

## 저장소 구조

```text
index.html
data/
  manifest.json
  2026-07.html              # GitHub Actions가 자동 생성/갱신
scripts/
  sync_schedule.py
.github/
  workflows/
    sync-schedule.yml
```

## GitHub에 올리는 방법

1. 새 GitHub repository를 만듭니다.
2. 이 폴더 안의 파일을 그대로 업로드합니다.
3. repository의 `Settings > Pages`에서 배포 소스를 `Deploy from a branch`, 브랜치는 `main`, 폴더는 `/root`로 설정합니다.
4. repository의 `Actions` 탭에서 `Sync Meditong Schedule` 워크플로를 열고 `Run workflow`를 눌러 한 번 실행합니다.
5. 실행 후 `data/2026-03.html` 같은 파일과 `data/manifest.json`이 갱신되면 GitHub Pages 주소로 접속합니다.

## 로그인이 필요한 경우

원본 근무표 페이지가 로그인 없이 열리지 않으면 GitHub Actions가 로그인 화면만 받을 수 있습니다. 이 경우 브라우저에서 로그인 후 쿠키 문자열을 복사해 repository의 `Settings > Secrets and variables > Actions > New repository secret`에 아래 이름으로 저장합니다.

```text
MEDITONG_COOKIE
```

쿠키는 비밀번호처럼 취급해야 하며, `index.html`, `sync_schedule.py`, README, 공개 이슈 등에 절대 붙여 넣지 마세요.

## 월 범위 바꾸기

`.github/workflows/sync-schedule.yml`에서 아래 값을 수정합니다.

```yaml
SYNC_START_MONTH: "2026-03"
SYNC_FUTURE_MONTHS: "1"
```

예를 들어 현재 월 기준 다음 2개월까지 미리 확인하려면 `SYNC_FUTURE_MONTHS`를 `2`로 바꾸면 됩니다.
