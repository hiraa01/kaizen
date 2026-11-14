"""
DEPRECATED - bu dosya artık kullanılmıyor.

Aynı dizinde `models/` paketi de bulunduğu için Python importlarında
(`from models import ...`) her zaman paket kazanır; bu dosya hiçbir
yerden çalışma zamanında import edilmiyordu (ölü kod). Daha önce
AgendaItem/StudySession/ChatMessage sınıfları SADECE burada tanımlıydı
ve paketteki __init__.py bunları kendi kendine (self) import etmeye
çalışan bozuk bir fallback ile çözmeye çalışıyordu; bu da sessizce
None dönmesine ve `routers/study.py`, `routers/agenda.py` gibi yerlerde
runtime hatasına yol açıyordu.

Bu üç model artık gerçek paket dosyalarına taşındı:
  - backend/models/agenda.py  -> AgendaItem
  - backend/models/study.py   -> StudySession
  - backend/models/chat.py    -> ChatMessage

Bu dosya kasıtlı olarak boş bırakıldı (silinmedi, geçmişi korumak için).
Güvenle silinebilir.
"""
