#!/usr/bin/env python3
"""
50,000개 클라이언트 WebSocket 대규모 로드 테스트
실시간 통계 대시보드와 함께 극한 부하 테스트
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

# 로깅 레벨 설정 (ERROR로 설정하여 로그 최소화)
logging.basicConfig(level=logging.ERROR)

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
        """클라이언트 실행 - 극도로 최적화된 버전"""
        retry_count = 0
        max_retries = 2  # 재시도 횟수 줄임
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(
                    self.server_uri,
                    ping_interval=30,  # 핑 간격 늘림
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2**16,  # 메시지 크기 제한
                    compression=None  # 압축 비활성화로 성능 향상
                ) as websocket:
                    self.stats.is_connected = True
                    self.stats.start_time = time.time()
                    
                    # 첫 연결 시에만 통계 업데이트
                    if self.stats.messages_received == 0:
                        self.stats_manager.update_client_stats(self.stats)
                    
                    async for message in websocket:
                        self.stats.messages_received += 1
                        self.stats.last_message_time = time.time()
                        
                        # 통계 업데이트 간격을 더 늘림 (매 50개 메시지마다)
                        if self.stats.messages_received % 50 == 0:
                            self.stats_manager.update_client_stats(self.stats)
                            
            except websockets.exceptions.ConnectionClosedError:
                break
            except Exception as e:
                self.stats.connection_errors += 1
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(0.5)  # 재연결 대기 시간 단축
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
                        print(f"{Fore.CYAN}{'='*90}")
                        print(f"{Fore.YELLOW}           50,000개 클라이언트 WebSocket 대규모 로드 테스트")
                        print(f"{Fore.CYAN}{'='*90}")
                        print(f"{Fore.WHITE}시작 시간: {Fore.GREEN}{datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S')}")
                        print(f"{Fore.WHITE}경과 시간: {Fore.GREEN}{summary['elapsed_time']:.1f}초")
                        print(f"{Fore.CYAN}{'-'*90}")
                        print(f"{Fore.WHITE}총 클라이언트:     {Fore.YELLOW}{summary['total_clients']:,}개")
                        print(f"{Fore.WHITE}연결된 클라이언트:  {Fore.GREEN}{summary['connected_clients']:,}개")
                        print(f"{Fore.WHITE}성공한 연결:       {Fore.GREEN}{summary['successful_connections']:,}개")
                        print(f"{Fore.WHITE}연결 성공률:       {Fore.GREEN}{summary['success_rate']:.1f}%")
                        print(f"{Fore.WHITE}연결 오류:         {Fore.RED}{summary['total_errors']:,}개")
                        print(f"{Fore.CYAN}{'-'*90}")
                        print(f"{Fore.WHITE}총 수신 메시지:    {Fore.CYAN}{summary['total_messages']:,}개")
                        print(f"{Fore.WHITE}메시지/초:        {Fore.CYAN}{summary['messages_per_second']:.1f}")
                        print(f"{Fore.CYAN}{'-'*90}")
                        
                        # 진행률 바 표시
                        target = 50000
                        connected_progress = min((summary['connected_clients'] / target) * 60, 60)
                        success_progress = min((summary['successful_connections'] / target) * 60, 60)
                        
                        connected_bar = "█" * int(connected_progress) + "░" * (60 - int(connected_progress))
                        success_bar = "█" * int(success_progress) + "░" * (60 - int(success_progress))
                        
                        print(f"{Fore.WHITE}연결 진행률: [{Fore.GREEN}{connected_bar}{Fore.WHITE}] {summary['connected_clients']:,}/{target:,}")
                        print(f"{Fore.WHITE}성공 진행률: [{Fore.CYAN}{success_bar}{Fore.WHITE}] {summary['successful_connections']:,}/{target:,}")
                        
                        # 메모리 사용량 예측 표시
                        estimated_memory_mb = (summary['total_clients'] * 0.5) + (summary['total_messages'] * 0.001)
                        print(f"{Fore.WHITE}예상 메모리 사용: {Fore.YELLOW}{estimated_memory_mb:.1f}MB")
                        
                        print(f"{Fore.CYAN}{'='*90}")
                        print(f"{Fore.YELLOW}Ctrl+C를 눌러 테스트를 종료하세요.")
                        
                        # 진행률이 높으면 업데이트 간격을 늘림
                        if summary['connected_clients'] > 30000:
                            time.sleep(3)  # 높은 부하에서는 3초마다 업데이트
                        else:
                            time.sleep(2)  # 일반적으로 2초마다 업데이트
                    
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
        """클라이언트를 점진적으로 시작 - 50,000개 최적화"""
        print(f"{Fore.CYAN}50,000개 클라이언트를 점진적으로 시작합니다...")
        print(f"{Fore.WHITE}서버: {self.server_uri}")
        print(f"{Fore.YELLOW}잠시 후 실시간 대시보드가 표시됩니다...")
        print(f"{Fore.RED}⚠️  시스템 리소스를 모니터링해 주세요!")
        print(f"{Fore.CYAN}{'='*90}\n")
        
        # 대시보드 시작
        dashboard_thread = self.stats_manager.start_dashboard()
        
        # 클라이언트를 500개씩 묶어서 시작 (더 큰 배치)
        batch_size = 500
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
            
            # 배치 간 대기 시간 조정 (시스템 부하 분산)
            if batch_end < self.num_clients:
                if batch_end < 10000:
                    await asyncio.sleep(0.05)  # 처음 10K까지는 빠르게
                elif batch_end < 30000:
                    await asyncio.sleep(0.1)   # 30K까지는 중간 속도
                else:
                    await asyncio.sleep(0.2)   # 나머지는 천천히
        
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
            print(f"\n{Fore.CYAN}{'='*90}")
            print(f"{Fore.YELLOW}              최종 대규모 테스트 결과")
            print(f"{Fore.CYAN}{'='*90}")
            print(f"{Fore.GREEN}테스트 시간:       {Fore.WHITE}{summary['elapsed_time']:.1f}초")
            print(f"{Fore.GREEN}총 클라이언트:     {Fore.WHITE}{summary['total_clients']:,}개")
            print(f"{Fore.GREEN}성공한 연결:       {Fore.WHITE}{summary['successful_connections']:,}개")
            print(f"{Fore.GREEN}연결 성공률:       {Fore.WHITE}{summary['success_rate']:.1f}%")
            print(f"{Fore.GREEN}총 수신 메시지:    {Fore.WHITE}{summary['total_messages']:,}개")
            print(f"{Fore.GREEN}평균 메시지/초:    {Fore.WHITE}{summary['messages_per_second']:.1f}")
            print(f"{Fore.GREEN}연결 오류:         {Fore.WHITE}{summary['total_errors']:,}개")
            
            # 성능 평가
            if summary['success_rate'] > 90:
                print(f"{Fore.GREEN}🎉 성능 평가: 우수! 서버가 대규모 부하를 잘 처리했습니다.")
            elif summary['success_rate'] > 70:
                print(f"{Fore.YELLOW}⚠️  성능 평가: 보통. 일부 연결 문제가 있었습니다.")
            else:
                print(f"{Fore.RED}❌ 성능 평가: 개선 필요. 서버 용량이나 네트워크를 점검하세요.")
                
            print(f"{Fore.CYAN}{'='*90}")

def signal_handler(sig, frame):
    print(f"\n{Fore.YELLOW}테스트 중단됨...")
    sys.exit(0)

async def main():
    server_uri = "ws://localhost:8765"
    num_clients = 50000
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"{Fore.CYAN}{'='*90}")
    print(f"{Fore.YELLOW}        50,000개 클라이언트 WebSocket 대규모 로드 테스트")
    print(f"{Fore.CYAN}{'='*90}")
    print(f"{Fore.WHITE}서버: {server_uri}")
    print(f"{Fore.WHITE}클라이언트 수: {num_clients:,}개")
    print(f"{Fore.RED}⚠️  경고: 이는 극한 부하 테스트입니다!")
    print(f"{Fore.YELLOW}시스템 리소스를 주의 깊게 모니터링하세요.")
    print(f"{Fore.YELLOW}테스트를 시작합니다...")
    print(f"{Fore.CYAN}{'='*90}\n")
    
    runner = LoadTestRunner(server_uri, num_clients)
    await runner.start_clients_gradually()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}프로그램 종료")