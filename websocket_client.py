#!/usr/bin/env python3
"""
WebSocket 부하 테스트 클라이언트
서버로부터 브로드캐스트 메시지를 수신하고 자동 재연결을 지원하는 클라이언트
"""

import asyncio
import websockets
import logging
import argparse
import json
from datetime import datetime
from typing import Optional, Dict
import random
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

class WebSocketClient:
    """WebSocket 클라이언트 클래스"""
    
    def __init__(self, server_uri: str, client_id: str = None):
        self.server_uri = server_uri
        self.client_id = client_id or f"client-{random.randint(1000, 9999)}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.connected = False
        
        # 재연결 설정
        self.max_retries = 10
        self.retry_delay = 1.0
        self.max_retry_delay = 30.0
        self.current_retry = 0
        
        # 통계
        self.messages_received = 0
        self.connect_time = None
        self.last_message_time = None
        self.connection_failures = 0
        
    async def connect(self) -> bool:
        """서버에 연결"""
        try:
            logger.info(f"[{self.client_id}] 서버 연결 시도: {self.server_uri}")
            
            # 연결 시도
            self.websocket = await websockets.connect(
                self.server_uri,
                ping_interval=20,  # 20초마다 ping
                ping_timeout=10,   # ping 타임아웃 10초
                close_timeout=5    # 연결 종료 타임아웃 5초
            )
            
            self.connected = True
            self.connect_time = datetime.now()
            self.current_retry = 0
            
            logger.info(f"{Fore.GREEN}[{self.client_id}] 서버 연결 성공")
            return True
            
        except Exception as e:
            self.connected = False
            self.connection_failures += 1
            logger.error(f"{Fore.RED}[{self.client_id}] 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """서버 연결 해제"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        
        self.connected = False
        logger.info(f"[{self.client_id}] 서버 연결 해제")
    
    async def listen_for_messages(self):
        """서버로부터 메시지 수신 대기"""
        if not self.websocket:
            return
        
        try:
            async for message in websocket:
                self.messages_received += 1
                self.last_message_time = datetime.now()
                
                # 메시지 파싱 시도 (JSON 또는 문자열)
                try:
                    # JSON 파싱 시도
                    parsed_message = json.loads(message)
                    if isinstance(parsed_message, dict) and 'timestamp' in parsed_message:
                        timestamp = parsed_message['timestamp']
                        sequence = parsed_message.get('sequence', 'N/A')
                        logger.debug(f"[{self.client_id}] JSON 메시지 수신: {timestamp} (seq: {sequence})")
                    else:
                        logger.debug(f"[{self.client_id}] JSON 메시지 수신: {message}")
                except json.JSONDecodeError:
                    # 일반 문자열 메시지
                    logger.debug(f"[{self.client_id}] 메시지 수신: {message}")
                
                # 5초마다 통계 출력
                if self.messages_received % 5 == 0:
                    self.print_stats()
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"[{self.client_id}] 서버 연결이 종료됨")
            self.connected = False
        except Exception as e:
            logger.error(f"[{self.client_id}] 메시지 수신 오류: {e}")
            self.connected = False
    
    async def reconnect(self) -> bool:
        """재연결 시도"""
        if self.current_retry >= self.max_retries:
            logger.error(f"[{self.client_id}] 최대 재시도 횟수 초과 ({self.max_retries})")
            return False
        
        # 지수 백오프 계산
        delay = min(self.retry_delay * (2 ** self.current_retry), self.max_retry_delay)
        jitter = random.uniform(0, delay * 0.1)  # 10% 지터 추가
        total_delay = delay + jitter
        
        logger.info(f"[{self.client_id}] {total_delay:.1f}초 후 재연결 시도... ({self.current_retry + 1}/{self.max_retries})")
        await asyncio.sleep(total_delay)
        
        self.current_retry += 1
        return await self.connect()
    
    async def keep_alive(self):
        """Keep-alive 메시지 전송 (선택사항)"""
        while self.running and self.connected:
            try:
                if self.websocket and not self.websocket.closed:
                    # ping 메시지는 websockets 라이브러리에서 자동 처리되므로 
                    # 여기서는 단순히 연결 상태만 확인
                    await asyncio.sleep(30)  # 30초마다 확인
                else:
                    self.connected = False
                    break
            except Exception as e:
                logger.error(f"[{self.client_id}] Keep-alive 오류: {e}")
                self.connected = False
                break
    
    def print_stats(self):
        """클라이언트 통계 출력"""
        if self.connect_time:
            uptime = datetime.now() - self.connect_time
            uptime_str = f"{int(uptime.total_seconds()//3600):02d}:{int((uptime.total_seconds()%3600)//60):02d}:{int(uptime.total_seconds()%60):02d}"
        else:
            uptime_str = "00:00:00"
        
        last_msg_str = "없음"
        if self.last_message_time:
            time_since_last = (datetime.now() - self.last_message_time).total_seconds()
            if time_since_last < 60:
                last_msg_str = f"{time_since_last:.1f}초 전"
            else:
                last_msg_str = f"{int(time_since_last//60)}분 전"
        
        stats = f"""
{Fore.CYAN}[{self.client_id}] 클라이언트 상태:
{Fore.GREEN}  연결 상태: {Fore.WHITE}{'연결됨' if self.connected else '연결 안됨'}
{Fore.GREEN}  수신 메시지: {Fore.WHITE}{self.messages_received:,}개
{Fore.GREEN}  연결 시간: {Fore.WHITE}{uptime_str}
{Fore.GREEN}  마지막 메시지: {Fore.WHITE}{last_msg_str}
{Fore.GREEN}  연결 실패 횟수: {Fore.WHITE}{self.connection_failures}회
        """
        print(stats)
    
    async def run(self):
        """클라이언트 메인 실행 루프"""
        self.running = True
        logger.info(f"[{self.client_id}] 클라이언트 시작")
        
        while self.running:
            try:
                # 연결 시도
                if not self.connected:
                    if not await self.connect():
                        # 재연결 시도
                        if not await self.reconnect():
                            logger.error(f"[{self.client_id}] 재연결 실패, 클라이언트 종료")
                            break
                        continue
                
                # 메시지 수신 및 keep-alive를 동시 실행
                listen_task = asyncio.create_task(self.listen_for_messages())
                keepalive_task = asyncio.create_task(self.keep_alive())
                
                # 둘 중 하나가 완료되면 종료
                done, pending = await asyncio.wait(
                    [listen_task, keepalive_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 남은 태스크 취소
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # 연결이 끊어진 경우 재연결 시도
                if not self.connected:
                    await self.disconnect()
                    continue
                    
            except KeyboardInterrupt:
                logger.info(f"[{self.client_id}] 사용자에 의한 종료")
                break
            except Exception as e:
                logger.error(f"[{self.client_id}] 실행 중 오류: {e}")
                self.connected = False
                await asyncio.sleep(1)  # 잠시 대기 후 재시도
        
        # 정리
        await self.disconnect()
        logger.info(f"[{self.client_id}] 클라이언트 종료")
        
        # 최종 통계 출력
        self.print_final_stats()
    
    def print_final_stats(self):
        """최종 통계 출력"""
        total_time = 0
        if self.connect_time:
            total_time = (datetime.now() - self.connect_time).total_seconds()
        
        print(f"""
{Fore.YELLOW}{'='*50}
{Fore.CYAN}[{self.client_id}] 최종 통계
{Fore.YELLOW}{'='*50}
{Fore.GREEN}총 수신 메시지: {Fore.WHITE}{self.messages_received:,}개
{Fore.GREEN}총 연결 시간: {Fore.WHITE}{total_time:.1f}초
{Fore.GREEN}평균 메시지 수신율: {Fore.WHITE}{self.messages_received/max(total_time, 1):.2f} msg/s
{Fore.GREEN}연결 실패 횟수: {Fore.WHITE}{self.connection_failures}회
{Fore.YELLOW}{'='*50}
        """)

async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="WebSocket 부하 테스트 클라이언트")
    parser.add_argument("--server", default="ws://localhost:8765", help="서버 URI (기본값: ws://localhost:8765)")
    parser.add_argument("--client-id", help="클라이언트 ID (기본값: 자동 생성)")
    parser.add_argument("--max-retries", type=int, default=10, help="최대 재시도 횟수 (기본값: 10)")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="재시도 기본 지연 시간 (기본값: 1.0초)")
    
    args = parser.parse_args()
    
    # 클라이언트 생성
    client = WebSocketClient(args.server, args.client_id)
    client.max_retries = args.max_retries
    client.retry_delay = args.retry_delay
    
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("사용자에 의한 클라이언트 종료")
    except Exception as e:
        logger.error(f"클라이언트 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())