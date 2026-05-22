"""
Backend performans test scripti
Optimize edilmiş endpoint'leri test eder
"""
import os
import time
import requests
import statistics

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8003/api")

def test_endpoint(endpoint: str, iterations: int = 5):
    """Bir endpoint'i birden fazla kez test et ve ortalama süreyi hesapla"""
    times = []
    print(f"\n🧪 Testing: {endpoint}")
    
    for i in range(iterations):
        start = time.time()
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
            elapsed = time.time() - start
            times.append(elapsed)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"  {status} Request {i+1}: {elapsed:.2f}s (Status: {response.status_code})")
        except Exception as e:
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  ❌ Request {i+1}: {elapsed:.2f}s (Error: {str(e)[:50]})")
    
    if times:
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        print(f"  📊 Average: {avg_time:.2f}s | Min: {min_time:.2f}s | Max: {max_time:.2f}s")
        return avg_time
    return None

def main():
    print("=" * 60)
    print("🚀 Backend Performans Testi - Optimize Edilmiş Endpoint'ler")
    print("=" * 60)
    
    # Test edilecek endpoint'ler
    endpoints = [
        "/health",
        "/universities/cities/",
        "/universities/field-types/",
        "/universities/?limit=10",
        "/universities/departments/?limit=10",
    ]
    
    results = {}
    for endpoint in endpoints:
        avg_time = test_endpoint(endpoint)
        if avg_time:
            results[endpoint] = avg_time
    
    print("\n" + "=" * 60)
    print("📈 ÖZET")
    print("=" * 60)
    for endpoint, avg_time in results.items():
        status = "✅ İYİ" if avg_time < 2.0 else "⚠️ YAVAŞ" if avg_time < 5.0 else "❌ ÇOK YAVAŞ"
        print(f"{status} {endpoint}: {avg_time:.2f}s")
    
    print("\n✅ Test tamamlandı!")

if __name__ == "__main__":
    main()

