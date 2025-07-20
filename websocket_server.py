#!/usr/bin/env python3
"""
WebSocket 부하 테스트 서버
2,000개 동시 연결을 지원하는 고성능 WebSocket 서버 구현
"""

import asyncio
import websockets
import json
import logging
import signal
import argparse
from datetime import datetime
from typing import Set, Dict, Optional
from dataclasses import dataclass, field
import psutil
import time
from colorama import init, Fore, Style

init(autoreset=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class ConnectionInfo:
    """연결 정보를 저장하는 데이터 클래스"""
    websocket: websockets.WebSocketServerProtocol
    client_id: str
    connect_time: datetime = field(default_factory=datetime.now)
    last_message_time: datetime = field(default_factory=datetime.now)
    message_count: int = 0

@dataclass
class ServerStats:
    """서버 통계 정보"""
    active_connections: int = 0
    total_messages_sent: int = 0
    messages_per_second: float = 0.0
    uptime: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0

class TimestampGenerator:
    """시간 정보를 생성하는 유틸리티 클래스"""
    
    @staticmethod
    def generate_timestamp() -> str:
        """현재 시간을 문자열 형태로 반환"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    @staticmethod
    def generate_json_timestamp() -> str:
        """JSON 형태의 타임스탬프 메시지 생성"""
        timestamp = TimestampGenerator.generate_timestamp()
        message = {
            "timestamp": timestamp,
            "server_id": "ws-server-01",
            "sequence": int(time.time() * 1000000) % 1000000
        }
        return json.dumps(message, ensure_ascii=False)

class ConnectionManager:
    """WebSocket 연결을 관리하는 클래스"""
    
    def __init__(self):
        self.connections: Dict[websockets.WebSocketServerProtocol, ConnectionInfo] = {}
        self.max_connections = 2000
        
    def add_connection(self, websocket: websockets.WebSocketServerProtocol, client_id: str = None) -> bool:
        """새로운 연결을 추가"""
        if len(self.connections) >= self.max_connections:
            logger.warning(f"최대 연결 수 초과: {len(self.connections)}/{self.max_connections}")
            return False
            
        if client_id is None:
            client_id = f"client-{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            
        connection_info = ConnectionInfo(websocket=websocket, client_id=client_id)
        self.connections[websocket] = connection_info
        
        logger.info(f"클라이언트 연결됨: {client_id} (총 {len(self.connections)}개)")
        return True
    
    def remove_connection(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """연결을 제거"""
        if websocket in self.connections:
            connection_info = self.connections.pop(websocket)
            logger.info(f"클라이언트 연결 해제됨: {connection_info.client_id} (총 {len(self.connections)}개)")
    
    def get_connection_count(self) -> int:
        """현재 연결 수 반환"""
        return len(self.connections)
    
    def get_all_connections(self) -> Set[websockets.WebSocketServerProtocol]:
        """모든 활성 연결 반환"""
        return set(self.connections.keys())
    
    def update_message_count(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """메시지 카운트 업데이트"""
        if websocket in self.connections:
            self.connections[websocket].message_count += 1
            self.connections[websocket].last_message_time = datetime.now()

class BroadcastManager:
    """브로드캐스트 메시지 전송을 관리하는 클래스"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.failed_connections = set()
    
    async def broadcast_message(self, message: str) -> Dict[str, int]:
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트"""
        connections = self.connection_manager.get_all_connections()
        if not connections:
            return {"sent": 0, "failed": 0}
        
        # 동시 전송을 위한 태스크 생성
        tasks = []
        for websocket in connections:
            task = asyncio.create_task(self.broadcast_to_connection(websocket, message))
            tasks.append(task)
        
        # 모든 전송 태스크 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sent_count = sum(1 for result in results if result is True)
        failed_count = len(results) - sent_count
        
        if failed_count > 0:
            await self.cleanup_failed_connections()
        
        logger.debug(f"브로드캐스트 완료: {sent_count}/{len(connections)} 성공")
        return {"sent": sent_count, "failed": failed_count}
    
    async def broadcast_to_connection(self, websocket: websockets.WebSocketServerProtocol, message: str) -> bool:
        """개별 연결에 메시지 전송"""
        try:
            await websocket.send(message)
            self.connection_manager.update_message_count(websocket)
            return True
        except websockets.exceptions.ConnectionClosed:
            self.failed_connections.add(websocket)
            return False
        except Exception as e:
            logger.error(f"메시지 전송 실패: {e}")
            self.failed_connections.add(websocket)
            return False
    
    async def cleanup_failed_connections(self) -> None:
        """실패한 연결들을 정리"""
        for websocket in self.failed_connections:
            self.connection_manager.remove_connection(websocket)
        self.failed_connections.clear()

class WebSocketServer:
    """메인 WebSocket 서버 클래스"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.server = None
        self.running = False
        self.start_time = None
        
        # 매니저들 초기화
        self.connection_manager = ConnectionManager()
        self.broadcast_manager = BroadcastManager(self.connection_manager)
        
        # 통계
        self.stats = ServerStats()
        self.total_messages_sent = 0
        
    async def handle_client(self, websocket, path):
        """클라이언트 연결 처리"""
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        # 연결 추가
        if not self.connection_manager.add_connection(websocket, client_address):
            await websocket.close(code=1013, reason="서버 과부하")
            return
        
        try:
            # 클라이언트 메시지 대기 (Keep-alive)
            async for message in websocket:
                logger.debug(f"클라이언트로부터 메시지 수신: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"클라이언트 연결 종료: {client_address}")
        except Exception as e:
            logger.error(f"클라이언트 처리 중 오류: {e}")
        finally:
            self.connection_manager.remove_connection(websocket)
    
    async def broadcast_timer(self):
        """1초마다 타임스탬프를 브로드캐스트"""
        while self.running:
            try:
                # 현재 시간 생성
                timestamp_message = TimestampGenerator.generate_timestamp()
                
                # 모든 클라이언트에게 브로드캐스트
                result = await self.broadcast_manager.broadcast_message(timestamp_message)
                self.total_messages_sent += result["sent"]
                
                # 1초 대기
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"브로드캐스트 타이머 오류: {e}")
                await asyncio.sleep(1.0)
    
    async def stats_monitor(self):
        """시스템 통계를 주기적으로 출력"""
        last_message_count = 0
        
        while self.running:
            try:
                # 시스템 통계 수집
                process = psutil.Process()
                
                self.stats.active_connections = self.connection_manager.get_connection_count()
                self.stats.total_messages_sent = self.total_messages_sent
                self.stats.memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                self.stats.cpu_usage = process.cpu_percent()
                
                if self.start_time:
                    self.stats.uptime = time.time() - self.start_time
                
                # 초당 메시지 계산
                current_messages = self.total_messages_sent
                messages_delta = current_messages - last_message_count
                self.stats.messages_per_second = messages_delta / 5.0  # 5초마다 업데이트
                last_message_count = current_messages
                
                # 대시보드 출력
                self.print_dashboard()
                
                await asyncio.sleep(5.0)  # 5초마다 업데이트
                
            except Exception as e:
                logger.error(f"통계 모니터링 오류: {e}")
                await asyncio.sleep(5.0)
    
    def print_dashboard(self):
        """실시간 대시보드 출력"""
        uptime_str = f"{int(self.stats.uptime//3600):02d}:{int((self.stats.uptime%3600)//60):02d}:{int(self.stats.uptime%60):02d}"
        
        dashboard = f"""
{Fore.CYAN}{'='*50}
{Fore.YELLOW}     WebSocket 서버 실시간 상태
{Fore.CYAN}{'='*50}
{Fore.GREEN}활성 연결: {Fore.WHITE}{self.stats.active_connections:,} / 2,000
{Fore.GREEN}총 전송 메시지: {Fore.WHITE}{self.stats.total_messages_sent:,}
{Fore.GREEN}초당 메시지: {Fore.WHITE}{self.stats.messages_per_second:.1f} msg/s
{Fore.GREEN}서버 가동시간: {Fore.WHITE}{uptime_str}
{Fore.GREEN}CPU 사용률: {Fore.WHITE}{self.stats.cpu_usage:.1f}%
{Fore.GREEN}메모리 사용량: {Fore.WHITE}{self.stats.memory_usage:.1f} MB
{Fore.CYAN}{'='*50}
        """
        print(dashboard)
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"WebSocket 서버 시작: ws://{self.host}:{self.port}")
        
        self.running = True
        self.start_time = time.time()
        
        # 서버 생성
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            max_size=None,  # 메시지 크기 제한 없음
            max_queue=None,  # 큐 크기 제한 없음
        )
        
        # 백그라운드 태스크 시작
        broadcast_task = asyncio.create_task(self.broadcast_timer())
        stats_task = asyncio.create_task(self.stats_monitor())
        
        try:
            # 서버 실행 대기
            await asyncio.gather(broadcast_task, stats_task)
        except asyncio.CancelledError:
            logger.info("서버 종료 중...")
        finally:
            await self.stop_server()
    
    async def stop_server(self):
        """서버 정지"""
        logger.info("서버 종료 중...")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("서버 종료 완료")

def signal_handler(server):
    """시그널 핸들러"""
    def handler(sig, frame):
        logger.info(f"종료 시그널 수신: {sig}")
        asyncio.create_task(server.stop_server())
    return handler

async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="WebSocket 부하 테스트 서버")
    parser.add_argument("--host", default="0.0.0.0", help="서버 호스트 (기본값: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="서버 포트 (기본값: 8765)")
    parser.add_argument("--max-connections", type=int, default=2000, help="최대 연결 수 (기본값: 2000)")
    
    args = parser.parse_args()
    
    # 서버 생성
    server = WebSocketServer(args.host, args.port)
    server.connection_manager.max_connections = args.max_connections
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler(server))
    signal.signal(signal.SIGTERM, signal_handler(server))
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("사용자에 의한 서버 종료")
    except Exception as e:
        logger.error(f"서버 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())