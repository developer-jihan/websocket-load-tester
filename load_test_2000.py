#!/usr/bin/env python3
"""
2000개 클라이언트 WebSocket 로드 테스트
실시간 통계 대시보드와 함께 대규모 연결 테스트
"""

import asyncio
import websockets
import time
import threading
from datetime import datetime
from colorama import init, Fore, Style
import logging
import signal
import sys
from dataclasses import dataclass
from typing import List, Dict
import os

init(autoreset=True)

# 로깅 레벨 설정 (WARNING으로 설정하여 불필요한 로그 제거)
logging.basicConfig(level=logging.WARNING)

@dataclass
class ClientStats:
    client_id: int
    messages_received: int = 0
    is_connected: bool = False
    start_time: float = None
    last_message_time: float = None
    connection_errors: int = 0

class LoadTestClient:
    def __init__(self, client_id: int, server_uri: str, stats_manager):
        self.client_id = client_id
        self.server_uri = server_uri
        self.stats_manager = stats_manager
        self.stats = ClientStats(client_id)
        
    async def run(self):
        """클라이언트 실행 - 로그 최소화"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(
                    self.server_uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.stats.is_connected = True
                    self.stats.start_time = time.time()
                    self.stats_manager.update_client_stats(self.stats)
                    
                    async for message in websocket:
                        self.stats.messages_received += 1
                        self.stats.last_message_time = time.time()
                        
                        # 통계 업데이트 (매 10개 메시지마다만)
                        if self.stats.messages_received % 10 == 0:
                            self.stats_manager.update_client_stats(self.stats)
                            
            except websockets.exceptions.ConnectionClosedError:
                break
            except Exception as e:
                self.stats.connection_errors += 1
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(1)  # 재연결 대기
                continue
        
        self.stats.is_connected = False
        self.stats_manager.update_client_stats(self.stats)

class StatsManager:
    def __init__(self):
        self.clients: Dict[int, ClientStats] = {}
        self.start_time = time.time()
        self.running = True
        self.lock = threading.Lock()
        
    def update_client_stats(self, stats: ClientStats):
        with self.lock:
            self.clients[stats.client_id] = stats
    
    def get_summary(self):
        with self.lock:
            if not self.clients:
                return None
                
            total_clients = len(self.clients)
            connected_clients = sum(1 for c in self.clients.values() if c.is_connected)
            total_messages = sum(c.messages_received for c in self.clients.values())
            total_errors = sum(c.connection_errors for c in self.clients.values())
            
            # 연결 성공률 계산
            attempted_connections = len(self.clients)
            successful_connections = len([c for c in self.clients.values() if c.messages_received > 0])
            success_rate = (successful_connections / attempted_connections * 100) if attempted_connections > 0 else 0
            
            elapsed_time = time.time() - self.start_time
            messages_per_second = total_messages / max(elapsed_time, 1)
            
            return {
                'total_clients': total_clients,
                'connected_clients': connected_clients,
                'total_messages': total_messages,
                'total_errors': total_errors,
                'success_rate': success_rate,
                'elapsed_time': elapsed_time,
                'messages_per_second': messages_per_second,
                'successful_connections': successful_connections
            }

    def start_dashboard(self):
        """실시간 대시보드 스레드"""
        def display_dashboard():
            while self.running:
                try:
                    # 화면 지우기
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                    summary = self.get_summary()
                    if summary:
                        print(f"{Fore.CYAN}{'='*80}")
                        print(f"{Fore.YELLOW}           2000개 클라이언트 WebSocket 로드 테스트")
                        print(f"{Fore.CYAN}{'='*80}")
                        print(f"{Fore.WHITE}시작 시간: {Fore.GREEN}{datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S')}")
                        print(f"{Fore.WHITE}경과 시간: {Fore.GREEN}{summary['elapsed_time']:.1f}초")
                        print(f"{Fore.CYAN}{'-'*80}")
                        print(f"{Fore.WHITE}총 클라이언트:     {Fore.YELLOW}{summary['total_clients']:,}개")
                        print(f"{Fore.WHITE}연결된 클라이언트:  {Fore.GREEN}{summary['connected_clients']:,}개")
                        print(f"{Fore.WHITE}성공한 연결:       {Fore.GREEN}{summary['successful_connections']:,}개")
                        print(f"{Fore.WHITE}연결 성공률:       {Fore.GREEN}{summary['success_rate']:.1f}%")
                        print(f"{Fore.WHITE}연결 오류:         {Fore.RED}{summary['total_errors']:,}개")
                        print(f"{Fore.CYAN}{'-'*80}")
                        print(f"{Fore.WHITE}총 수신 메시지:    {Fore.CYAN}{summary['total_messages']:,}개")
                        print(f"{Fore.WHITE}메시지/초:        {Fore.CYAN}{summary['messages_per_second']:.1f}")
                        print(f"{Fore.CYAN}{'-'*80}")
                        
                        # 진행률 바 표시
                        target = 2000
                        connected_progress = (summary['connected_clients'] / target) * 50
                        success_progress = (summary['successful_connections'] / target) * 50
                        
                        connected_bar = "█" * int(connected_progress) + "░" * (50 - int(connected_progress))
                        success_bar = "█" * int(success_progress) + "░" * (50 - int(success_progress))
                        
                        print(f"{Fore.WHITE}연결 진행률: [{Fore.GREEN}{connected_bar}{Fore.WHITE}] {summary['connected_clients']}/{target}")
                        print(f"{Fore.WHITE}성공 진행률: [{Fore.CYAN}{success_bar}{Fore.WHITE}] {summary['successful_connections']}/{target}")
                        print(f"{Fore.CYAN}{'='*80}")
                        print(f"{Fore.YELLOW}Ctrl+C를 눌러 테스트를 종료하세요.")
                    
                    time.sleep(2)  # 2초마다 업데이트
                except KeyboardInterrupt:
                    break
                except Exception:
                    pass
        
        dashboard_thread = threading.Thread(target=display_dashboard, daemon=True)
        dashboard_thread.start()
        return dashboard_thread

class LoadTestRunner:
    def __init__(self, server_uri: str, num_clients: int):
        self.server_uri = server_uri
        self.num_clients = num_clients
        self.stats_manager = StatsManager()
        self.clients = []
        
    async def start_clients_gradually(self):
        """클라이언트를 점진적으로 시작"""
        print(f"{Fore.CYAN}2000개 클라이언트를 점진적으로 시작합니다...")
        print(f"{Fore.WHITE}서버: {self.server_uri}")
        print(f"{Fore.YELLOW}잠시 후 실시간 대시보드가 표시됩니다...\n")
        
        # 대시보드 시작
        dashboard_thread = self.stats_manager.start_dashboard()
        
        # 클라이언트를 100개씩 묶어서 시작
        batch_size = 100
        tasks = []
        
        for batch_start in range(0, self.num_clients, batch_size):
            batch_end = min(batch_start + batch_size, self.num_clients)
            
            # 배치 내 클라이언트들을 동시에 시작
            batch_tasks = []
            for i in range(batch_start, batch_end):
                client = LoadTestClient(i + 1, self.server_uri, self.stats_manager)
                self.clients.append(client)
                task = asyncio.create_task(client.run())
                batch_tasks.append(task)
            
            tasks.extend(batch_tasks)
            
            # 배치 간 잠깐 대기 (서버 부하 분산)
            if batch_end < self.num_clients:
                await asyncio.sleep(0.1)
        
        print(f"{Fore.GREEN}모든 클라이언트 시작 완료! 실시간 대시보드 확인 중...")
        
        # 모든 클라이언트 작업 완료 대기
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}사용자에 의한 종료...")
        
        # 최종 통계
        self.show_final_stats()
    
    def show_final_stats(self):
        """최종 통계 표시"""
        summary = self.stats_manager.get_summary()
        if summary:
            print(f"\n{Fore.CYAN}{'='*80}")
            print(f"{Fore.YELLOW}              최종 테스트 결과")
            print(f"{Fore.CYAN}{'='*80}")
            print(f"{Fore.GREEN}테스트 시간:       {Fore.WHITE}{summary['elapsed_time']:.1f}초")
            print(f"{Fore.GREEN}총 클라이언트:     {Fore.WHITE}{summary['total_clients']:,}개")
            print(f"{Fore.GREEN}성공한 연결:       {Fore.WHITE}{summary['successful_connections']:,}개")
            print(f"{Fore.GREEN}연결 성공률:       {Fore.WHITE}{summary['success_rate']:.1f}%")
            print(f"{Fore.GREEN}총 수신 메시지:    {Fore.WHITE}{summary['total_messages']:,}개")
            print(f"{Fore.GREEN}평균 메시지/초:    {Fore.WHITE}{summary['messages_per_second']:.1f}")
            print(f"{Fore.GREEN}연결 오류:         {Fore.WHITE}{summary['total_errors']:,}개")
            print(f"{Fore.CYAN}{'='*80}")

def signal_handler(sig, frame):
    print(f"\n{Fore.YELLOW}테스트 중단됨...")
    sys.exit(0)

async def main():
    server_uri = "ws://localhost:8765"
    num_clients = 2000
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.YELLOW}        2000개 클라이언트 WebSocket 로드 테스트")
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.WHITE}서버: {server_uri}")
    print(f"{Fore.WHITE}클라이언트 수: {num_clients:,}개")
    print(f"{Fore.YELLOW}테스트를 시작합니다...")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    runner = LoadTestRunner(server_uri, num_clients)
    await runner.start_clients_gradually()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}프로그램 종료")