# Credit Spread 자동 갱신 대시보드 (GitHub Actions + GitHub Pages)

미국 하이일드 스프레드([FRED BAMLH0A0HYM2](https://fred.stlouisfed.org/series/bamlh0a0hym2))와 투자등급 스프레드([FRED BAMLC0A0CM](https://fred.stlouisfed.org/series/BAMLC0A0CM))를 매일 자동으로 수집해 모바일·PC에서 볼 수 있는 웹 대시보드로 배포하는 프로젝트입니다.

## 자동 갱신 스케줄
- **실행 시각**: 매주 화~토 새벽 **01:00 KST** (`16:00 UTC`, 월~금)
- FRED에 전일 미국 장 마감 데이터가 반영되는 시각(미국 중부시간 오전 9:00~9:45경) 직후에 자동으로 최신 CSV를 내려받아 `dist/index.html`을 다시 빌드·배포합니다.

## 5분 설치 및 배포 방법

1. **GitHub 새 저장소(Repository) 생성**
   - GitHub에서 **Public** 저장소를 하나 만듭니다(예: `credit-spread`).
2. **파일 업로드**
   - 이 압축 파일의 내용을 그대로 저장소 루트에 올립니다(`.github/workflows/update_spreads.yml`, `scripts/build_site.py`, `template/index.html`, `README.md`).
   - 웹 UI에서 업로드할 때 숨김 폴더(`.github`)가 빠지지 않도록 주의하거나 `git push`로 올리면 가장 확실합니다.
3. **GitHub Pages 활성화**
   - 저장소 상단 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 변경합니다.
4. **첫 실행 및 모바일 홈 화면 추가**
   - 저장소 상단 **Actions → Update Credit Spread Dashboard → Run workflow**를 클릭합니다.
   - 약 30초 뒤 배포가 완료되면 `https://<깃허브아이디>.github.io/<저장소명>/` 주소로 접속해 스마트폰 홈 화면에 추가해 두세요.
