# Codex Meter

ChatGPT **Codex 주간 사용량**과 사용량 한도 재설정권을 시스템 트레이(메뉴 바)에서 보여주는 크로스 플랫폼(macOS / Windows) 앱입니다. Codex CLI 파일을 읽지 않으며, Codex CLI나 ChatGPT 데스크톱 앱을 설치하지 않아도 동작합니다.

## 설치

Python 3.10+ 필요. 저장소 폴더에서:

- **macOS**: `setup.command` 더블클릭 (터미널에서는 `./setup.sh`)
- **Windows**: `setup.bat` 더블클릭 (python.org에서 Python 설치 시 "Add to PATH" 체크)
- **Linux**: `./setup.sh`

설치 스크립트는 프로젝트 안에 `.venv` 가상 환경을 만들고 필요한 패키지를 설치합니다. 기존에 실행 중인 Codex Meter가 있으면 먼저 중지하므로 업데이트할 때도 같은 스크립트를 실행하면 됩니다.

## 실행

설치가 끝나면 앱이 자동으로 시작됩니다. 이후 다시 실행할 때는:

- **macOS**: `run.command` 더블클릭 (터미널에서는 `./run.sh`)
- **Windows**: `run.bat` 더블클릭
- **Linux**: `./run.sh`

실행 스크립트는 앱을 터미널에서 **분리(detach)** 해서 띄우므로 터미널 창을 닫아도 앱은 계속 동작합니다. 로그는 `~/.codex-meter/app.log` (Windows: `%USERPROFILE%\.codex-meter\app.log`). 터미널에 붙여서 디버그하려면 `.venv/bin/python -m codex_meter` 로 직접 실행하세요. Windows에서는 `.venv\Scripts\python.exe -m codex_meter` 를 사용합니다.

실행하면 트레이(메뉴 바)에 아이콘이 생기고, 메뉴에서 주간 사용량과 초기화까지 남은 시간을 확인할 수 있습니다.

```text
주간: 5% 사용 · 6일 12시간 3분 후 초기화
사용량 한도 재설정: 1개
  Full reset · 사용 가능 · 2026. 8. 13. 오전 9:00 만료 (21일 4시간 12분 후)
```

사용량은 API의 `used_percent` 기준입니다. 초기화 시각과 재설정권 만료까지 남은 시간은 API를 다시 호출하지 않고 로컬에서 1분마다 카운트다운됩니다. 실제 API 조회 주기는 메뉴의 **새로고침 주기** 설정을 따릅니다.

주간 사용량이나 재설정권 항목을 클릭하면 ChatGPT 사용량 페이지가 기본 브라우저로 열립니다.

```text
https://chatgpt.com/#settings/Usage
```

재설정권은 **조회만** 합니다. Codex Meter는 재설정권을 직접 적용하거나 소모하지 않습니다.
하단의 **Codex 애널리틱스 페이지 열기** 항목을 클릭한 경우에만 Codex Analytics 페이지(`https://chatgpt.com/codex/cloud/settings/analytics`)로 이동합니다.

## 트레이 메뉴

로그인 상태에서 다음 기능을 제공합니다.

- 주간 사용량과 초기화 카운트다운
- 사용량 한도 재설정권 개수·종류·상태·만료 시각
- 지금 새로고침
- Codex 애널리틱스 페이지 열기
- 새로고침 주기(5분 / 10분 / 30분 / 60분)
- 로그인 시 자동 시작
- 로그아웃
- 종료

Windows에서는 좌클릭과 우클릭 모두 메뉴를 엽니다. 트레이 아이콘은 작업 표시줄 테마에 따라 검정 또는 흰색으로 바뀌며, macOS에서는 시스템 template image로 처리되어 메뉴 바 색상에 자동으로 맞춰집니다.

## 로그인

메뉴에서 **OpenAI로 로그인...** 을 선택하면 OpenAI device-code 로그인을 시작합니다.

1. Codex Meter가 일회용 장치 코드를 요청합니다.
2. 장치 코드를 클립보드에 복사하고 OpenAI 확인 페이지를 기본 브라우저로 엽니다.
3. 브라우저에서 OpenAI 계정으로 로그인한 뒤 표시된 코드를 입력합니다.
4. 승인이 완료되면 Codex Meter가 OAuth 토큰을 교환하고 OS credential 저장소에 보관합니다.
5. 로그인 직후 사용량을 조회하고 이후 설정한 주기에 따라 갱신합니다.

로그인은 15분 안에 완료해야 합니다. 메뉴에 장치 코드와 진행 상태가 표시되며, 실패 원인은 `~/.codex-meter/app.log` 에 기록됩니다.

Codex Meter는 Codex CLI와 동일한 공개 OAuth client ID와 device-code 흐름을 사용하지만, Codex CLI의 `auth.json` 또는 다른 로그인 파일은 읽거나 수정하지 않습니다.

## 자격 증명 보안

OAuth access token, refresh token, ID token과 계정 메타데이터는 다음 OS 보안 저장소에 보관합니다.

- **Windows**: Windows Credential Manager
- **macOS**: macOS Keychain
- **Linux**: `keyring`이 선택한 시스템 credential backend

토큰은 `config.json`이나 프로젝트 파일에 기록하지 않습니다. Windows Credential Manager의 항목 크기 제한을 넘는 자격 증명은 압축한 뒤 여러 보안 항목으로 나누어 저장하고, 마지막 manifest 교체를 commit 지점으로 사용합니다. 따라서 갱신 중에도 이전 전체 자격 증명 또는 새 전체 자격 증명만 읽습니다.

OpenAI가 refresh token을 회전하면 access token, refresh token, ID token과 메타데이터 전체를 함께 교체합니다. Windows keyring backend가 남길 수 있는 이전 credential과 이전 세대 조각도 성공적인 교체 뒤 제거합니다.

API 호출에서 HTTP 401 또는 403이 발생하면 refresh token으로 자격 증명을 강제 갱신하고 해당 작업을 **한 번만** 재시도합니다. 네트워크 오류는 저장된 로그인을 삭제하지 않으며 다음 주기에 다시 시도합니다.

## 삭제

삭제 스크립트는 실행 전에 확인을 묻고, 앱을 중지한 뒤 자동 시작 등록·OS credential 저장소의 OAuth 로그인·데이터 폴더(`~/.codex-meter`)·`.venv`를 제거합니다.

- **macOS**: `uninstall.command` 더블클릭 (터미널에서는 `./uninstall.sh`)
- **Windows**: `uninstall.bat` 더블클릭
- **Linux**: `./uninstall.sh`

스크립트가 지우는 것은 앱이 시스템에 만든 항목뿐입니다. 프로젝트 폴더 자체는 남으니 완전히 지우려면 삭제 후 폴더를 직접 삭제하세요.

### 부팅 시 자동 시작

메뉴의 **로그인 시 자동 시작**을 체크하면 OS 로그인 시 앱이 자동으로 실행됩니다.

- macOS: `~/Library/LaunchAgents/local.codex-meter.plist` (LaunchAgent)
- Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 레지스트리 (pythonw로 콘솔 창 없이 실행)
- 등록 정보에는 절대 경로가 들어가므로 프로젝트 폴더를 옮기면 다음 실행 때 경로를 갱신합니다.
- 중복 실행은 잠금 파일로 차단됩니다. 자동 시작된 상태에서 실행 스크립트를 다시 실행해도 기존 앱을 교체하므로 트레이 아이콘이 두 개 생기지 않습니다.

## 설정

비밀 정보가 아닌 설정은 `~/.codex-meter/config.json` (Windows: `%USERPROFILE%\.codex-meter\config.json`)에 저장됩니다.

```json
{
  "refresh_interval": 10
}
```

- `refresh_interval`: API 갱신 주기(분). `5`, `10`, `30`, `60` 중 하나이며 메뉴에서도 변경할 수 있습니다.
- 초기화·만료 카운트다운의 1분 UI 갱신은 이 값과 무관하며 네트워크 요청을 만들지 않습니다.
- 로그 파일과 단일 인스턴스 잠금 파일도 `~/.codex-meter` 아래에 저장됩니다.

## 문제 해결

- **로그**: `~/.codex-meter/app.log`
- **로그인이 완료되지 않음**: 브라우저 승인을 15분 안에 마쳤는지 확인하고 로그에서 `Device login approved`와 `OAuth credentials saved` 메시지를 확인하세요.
- **로그인이 만료됨**: 메뉴에서 로그아웃한 뒤 device-code 로그인을 다시 진행하세요. 취소·만료·폐기·재사용된 refresh token은 복구할 수 없습니다.
- **네트워크 오류**: 로그인은 유지되며 다음 주기에 자동 재시도합니다.
- **사용량 응답을 읽지 못함**: ChatGPT 내부 API 또는 응답 구조가 변경됐을 수 있습니다. 로그를 확인하고 최신 코드로 업데이트하세요.
- **아이콘 색상이 배경과 맞지 않음**: Windows는 작업 표시줄의 `SystemUsesLightTheme`를 5초마다 확인합니다. 잠시 기다리거나 앱을 다시 실행하세요.
- **앱이 보이지 않음**: 숨겨진 트레이 아이콘 영역을 확인하고 `run.bat` 또는 `run.command`로 기존 인스턴스를 교체 실행하세요.

## 내부 API 주의사항

Codex Meter는 다음과 같은 문서화되지 않은 ChatGPT 내부 API를 사용합니다.

```text
GET https://chatgpt.com/backend-api/wham/usage
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
```

OpenAI는 이 endpoint, 응답 필드, 필요한 header, OAuth 동작 또는 접근 정책을 예고 없이 변경하거나 제거할 수 있습니다. 로컬 설치가 바뀌지 않아도 Codex Meter가 동작하지 않을 수 있으며, 이는 이 프로젝트가 가진 본질적인 유지보수·호환성 위험입니다.

## 테스트

전체 단위 테스트:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Windows:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

테스트는 OAuth 요청 형식, credential 압축·세대별 저장, refresh token 회전, 401/403 단일 재시도, API 파싱, 시간 표시, 테마별 아이콘 렌더링을 검사합니다. 외부 OpenAI 계정이나 실제 API 호출은 사용하지 않습니다.

## 상표 및 비공식 앱 고지

Codex Meter는 독립적으로 제작된 유틸리티입니다. OpenAI의 공식 앱이 아니며 OpenAI가 보증·후원하거나 제휴한 프로젝트가 아닙니다.

ChatGPT, Codex, OpenAI, Blossom 로고와 관련 표장은 OpenAI의 상표 또는 자산입니다. 저장소의 `favicon.ico`는 모니터링 대상 서비스를 트레이에서 식별하기 위한 목적으로만 사용합니다. 공식 Blossom 형상을 단색 시스템 트레이 glyph로 추출하고 비율을 유지해 크기만 조정하며, Codex Meter 자체의 브랜드처럼 표시하지 않습니다.
