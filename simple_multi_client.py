#!/usr/bin/env python3
"""
간단한 실시간 다중 클라이언트 데모
10개 클라이언트가 동시에 서버에서 메시지를 받는 모습을 콘솔에 실시간 출력
"""

import asyncio
import websockets
import time
from datetime import datetime
from colorama import init, Fore, Style
import threading
import logging

init(autoreset=True)

# 로깅 레벨 설정
logging.basicConfig(level=logging.WARNING)

class SimpleClient:
    def __init__(self, client_id: int, server_uri: str):
        self.client_id = client_id
        self.server_uri = server_uri
        self.messages_received = 0
        self.is_connected = False
        self.start_time = None
        
    async def run(self):
        """클라이언트 실행"""
        try:
            print(f"{Fore.YELLOW}[클라이언트-{self.client_id:02d}] 연결 시도 중...")
            
            async with websockets.connect(self.server_uri) as websocket:
                self.is_connected = True
                self.start_time = time.time()
                
                print(f"{Fore.GREEN}[클라이언트-{self.client_id:02d}] ✅ 연결 성공!")
                
                async for message in websocket:
                    self.messages_received += 1
                    elapsed = time.time() - self.start_time
                    
                    # 메시지 수신 실시간 출력
                    print(f"{Fore.CYAN}[클라이언트-{self.client_id:02d}] "
                          f"{Fore.WHITE}메시지 #{self.messages_received:3d} 수신 "
                          f"{Fore.GREEN}| 연결시간: {elapsed:5.1f}초 "
                          f"{Fore.BLUE}| 내용: {message[:30]}...")
                    
        except websockets.exceptions.ConnectionClosedException:
            print(f"{Fore.RED}[클라이언트-{self.client_id:02d}] ❌ 연결 종료됨")
        except Exception as e:
            print(f"{Fore.RED}[클라이언트-{self.client_id:02d}] ❌ 오류: {str(e)[:50]}")
        finally:
            self.is_connected = False
            print(f"{Fore.YELLOW}[클라이언트-{self.client_id:02d}] 최종 수신: {self.messages_received}개 메시지")

class MultiClientRunner:
    def __init__(self, server_uri: str, num_clients: int):
        self.server_uri = server_uri
        self.num_clients = num_clients
        self.clients = []
        self.start_time = None
        
    async def start_all_clients(self):
        """모든 클라이언트 시작"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.YELLOW}   10개 클라이언트 동시 연결 데모 시작!")
        print(f"{Fore.CYAN}{'='*70}")
        print(f"{Fore.WHITE}서버: {self.server_uri}")
        print(f"{Fore.WHITE}클라이언트 수: {self.num_clients}개")
        print(f"{Fore.CYAN}{'-'*70}\n")
        
        self.start_time = time.time()
        
        # 모든 클라이언트를 생성하고 비동기로 실행
        tasks = []
        for i in range(1, self.num_clients + 1):
            client = SimpleClient(i, self.server_uri)
            self.clients.append(client)
            
            # 각 클라이언트를 0.2초 간격으로 시작
            await asyncio.sleep(0.2)
            task = asyncio.create_task(client.run())
            tasks.append(task)
            
        print(f"{Fore.GREEN}\n모든 클라이언트 시작 완료! 실시간 메시지 수신 중...\n")
        print(f"{Fore.YELLOW}{'='*70}")
        print(f"{Fore.CYAN}실시간 메시지 수신 현황 (Ctrl+C로 종료):")
        print(f"{Fore.YELLOW}{'-'*70}\n")
        
        # 모든 클라이언트 완료까지 대기
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}사용자에 의한 종료...")
            
        # 최종 통계
        self.show_final_stats()
    
    def show_final_stats(self):
        """최종 통계 출력"""
        total_messages = sum(client.messages_received for client in self.clients)
        connected_count = sum(1 for client in self.clients if client.messages_received > 0)
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.YELLOW}             최종 통계")
        print(f"{Fore.CYAN}{'='*70}")
        print(f"{Fore.GREEN}총 실행 시간: {Fore.WHITE}{elapsed:.1f}초")
        print(f"{Fore.GREEN}성공한 연결: {Fore.WHITE}{connected_count}/{self.num_clients}개")
        print(f"{Fore.GREEN}총 수신 메시지: {Fore.WHITE}{total_messages}개")
        print(f"{Fore.GREEN}평균 메시지/초: {Fore.WHITE}{total_messages/max(elapsed, 1):.1f}")
        
        # 각 클라이언트별 통계
        print(f"\n{Fore.CYAN}클라이언트별 통계:")
        print(f"{Fore.CYAN}{'-'*40}")
        for client in self.clients:
            if client.messages_received > 0:
                print(f"{Fore.WHITE}클라이언트-{client.client_id:02d}: {Fore.GREEN}{client.messages_received:3d}개 메시지")
            else:
                print(f"{Fore.WHITE}클라이언트-{client.client_id:02d}: {Fore.RED}연결 실패")
        
        print(f"{Fore.CYAN}{'='*70}")

async def main():
    server_uri = "ws://localhost:8765"
    num_clients = 10
    
    print(f"{Fore.CYAN}실시간 다중 클라이언트 WebSocket 데모")
    print(f"{Fore.WHITE}서버가 {server_uri}에서 실행 중이어야 합니다.")
    print(f"{Fore.YELLOW}3초 후 시작...")
    
    await asyncio.sleep(3)
    
    runner = MultiClientRunner(server_uri, num_clients)
    await runner.start_all_clients()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}프로그램 종료")