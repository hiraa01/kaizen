# Şekil — kAIzen uygulaması iş akış diyagramı

Aşağıdaki diyagram, klasik **Başla → karar → işlem → veri katmanı** düzenindedir (örnekteki “Cebimde Hizmet” şemasıyla aynı *tarz*; iş kuralları farklıdır: bizde işletme / hizmet veren rolü yoktur).

```mermaid
flowchart TB
  START([Başla])

  START --> D1{Tanıtım daha önce görüldü mü?}
  D1 -->|Hayır| E1[Tanıtım ekranı]
  E1 --> D1
  D1 -->|Evet| D2{Kayıtlı oturum var mı?}

  D2 -->|Hayır| E2[Giriş veya kayıt]
  E2 --> D3{İlk kurulum tamamlandı mı?}

  D2 -->|Evet| D3

  D3 -->|Hayır| E3[İlk kurulum sihirbazı]
  E3 --> D3

  D3 -->|Evet| E4[Ana uygulama — alt menü]

  E4 --> F1[Ana sayfa]
  E4 --> F2[Denemeler / netler]
  E4 --> F3[Keşif / hedefler]
  E4 --> F4[Öneriler]
  E4 --> F5[Ajanda]
  E4 --> F6[Koç sohbeti]
  E4 --> F7[Profil ve ayarlar]

  F1 & F2 & F3 & F4 & F5 & F6 & F7 & E2 & E3 --> API[Sunucuya istek — API]

  API --> DB[(Sunucu ve veritabanı)]
```

## Referans şemasından farklar (kısa)

| Örnek uygulama (görsel) | kAIzen |
|-------------------------|--------|
| İki rol: kullanıcı / işletme | Tek kullanıcı rolü; işletme paneli yok |
| Firebase | Veri ve oturum mantığı **backend + ilişkisel veritabanı** (ve gerekirse önbellek) üzerinden |
| “Randevu / ilan” modülleri | YKS odaklı modüller: deneme, öneri, ajanda, koç vb. |

## Önizleme

` ```mermaid ` … ` ``` ` bloğunu Mermaid Chart veya Markdown önizlemesi ile aç.
