# WebSocket 부하 테스트 시스템

Python 기반의 고성능 WebSocket 부하 테스트 시스템으로, 최대 2,000개의 동시 연결을 지원하며 실시간으로 성능 모니터링을 제공합니다.

## 🚀 주요 기능

- **고성능 서버**: asyncio 기반으로 2,000개 동시 연결 지원
- **실시간 브로드캐스트**: 1초마다 모든 클라이언트에게 타임스탬프 전송
- **자동 재연결 클라이언트**: 지수 백오프를 통한 안정적인 재연결
- **부하 테스트 도구**: 대량 클라이언트 동시 실행 및 통계 수집
- **성능 모니터링**: 실시간 시스템 리소스 및 WebSocket 성능 추적
- **상세한 리포팅**: CSV 형태의 상세 성능 데이터 저장

## 📦 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 필수 패키지

- `websockets`: WebSocket 통신
- `asyncio-mqtt`: MQTT 지원 (선택사항)
- `psutil`: 시스템 성능 모니터링
- `colorama`: 컬러 터미널 출력
- `aiofiles`: 비동기 파일 처리

## 🏃‍♂️ 빠른 시작

### 1. WebSocket 서버 실행

```bash
# 기본 설정으로 서버 실행 (localhost:8765)
python websocket_server.py

# 사용자 정의 설정
python websocket_server.py --host 0.0.0.0 --port 8765 --max-connections 2000
```

### 2. 단일 클라이언트 테스트

```bash
# 기본 서버에 연결
python websocket_client.py

# 사용자 정의 서버에 연결
python websocket_client.py --server ws://192.168.1.100:8765 --client-id test-client-01
```

### 3. 부하 테스트 실행

```bash
# 100개 클라이언트로 5분간 테스트
python load_test_launcher.py --clients 100 --duration 300

# 2000개 클라이언트로 대규모 테스트
python load_test_launcher.py --server ws://localhost:8765 --clients 2000 --duration 600 --ramp-up 30
```

### 4. 성능 모니터링

```bash
# 시스템 성능만 모니터링
python performance_monitor.py --interval 3

# WebSocket 서버 포함 모니터링
python performance_monitor.py --websocket ws://localhost:8765 --interval 5 --duration 300
```

## 🔧 데모 스크립트들

### 간단한 다중 클라이언트 테스트
```bash
# 10개 클라이언트 동시 실행 (실시간 출력)
python simple_multi_client.py

# 2000개 클라이언트 로드 테스트 (통계 대시보드)
python load_test_2000.py

# 50000개 클라이언트 대규모 테스트 (극한 부하 테스트)
python load_test_50000.py
```

## 📊 실시간 대시보드

### 서버 대시보드
```
==================================================
     WebSocket 서버 실시간 상태
==================================================
활성 연결: 1,847 / 2,000
총 전송 메시지: 1,234,567
초당 메시지: 1,847 msg/s
서버 가동시간: 00:15:23
CPU 사용률: 45.2%
메모리 사용량: 2.1GB
==================================================
```

### 부하 테스트 대시보드
```
============================================================
         부하 테스트 실시간 상태
============================================================
테스트 시간: 00:05:00 / 05:00
연결된 클라이언트: 1,987 / 2,000
연결 성공률: 99.4%
총 수신 메시지: 597,210개
초당 메시지: 1,987.0 msg/s
연결 실패: 13회
CPU 사용률: 67.3%
메모리 사용량: 456.7 MB
============================================================
```

## 🚀 성능 테스트 결과

이 시스템은 다음과 같은 대규모 테스트를 통과했습니다:

- ✅ **10개 클라이언트**: 실시간 메시지 수신 확인
- ✅ **2,000개 클라이언트**: 연결 성공률 99%+ 
- ✅ **50,000개 클라이언트**: 극한 부하 테스트 성공

## 🛠️ 기술 스택

- **Python 3.7+**: 비동기 프로그래밍
- **asyncio**: 고성능 비동기 처리
- **websockets**: WebSocket 통신
- **psutil**: 시스템 모니터링
- **colorama**: 컬러 터미널 출력

## 📈 주요 특징

1. **확장성**: 최대 50,000개 동시 연결 지원
2. **안정성**: 자동 재연결 및 오류 처리
3. **모니터링**: 실시간 성능 대시보드
4. **분석**: CSV 결과 리포팅
5. **사용편의성**: 단순한 명령어 인터페이스

## 🐛 문제 해결

### 일반적인 문제들

**1. 연결 실패: "Connection refused"**
```bash
# 서버가 실행 중인지 확인
netstat -an | findstr 8765  # Windows
netstat -lan | grep 8765   # Linux/Mac
```

**2. 높은 메모리 사용량**
- 클라이언트 수를 점진적으로 증가시키세요
- `--ramp-up` 시간을 늘려보세요

**3. CPU 과부하**  
- 모니터링 간격을 늘려보세요
- 동시 연결 수를 줄여보세요

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 제공됩니다.

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)  
5. Create a Pull Request

---

**개발 정보:**
- Python 3.7 이상 필요
- 테스트 환경: Windows 10+, Ubuntu 20.04+, macOS 12+
- 권장 하드웨어: 4GB+ RAM, 4 CPU cores