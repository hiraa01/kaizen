# -*- coding: utf-8 -*-
"""
Gemini 1.5 Entegreli AI Chatbot Servisi
YKS Danışmanı - Öğrenci Profiline Uyarlanmış Cevaplar
"""
import os
from typing import Optional, Dict, Any, List
import google.generativeai as genai
import httpx
from core.logging_config import api_logger


class AIService:
    """LLM tabanlı YKS Danışmanı (Gemini/Groq)"""
    
    def __init__(self):
        """LLM sağlayıcısını başlat"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        explicit_provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()

        # Provider seçimi:
        # 1) LLM_PROVIDER verilmişse onu kullan
        # 2) gsk_ ile başlayan key varsa Groq
        # 3) aksi Gemini
        if explicit_provider in {"groq", "gemini"}:
            self.provider = explicit_provider
        elif (self.groq_api_key and self.groq_api_key.startswith("gsk_")) or (
            self.api_key and self.api_key.startswith("gsk_")
        ):
            self.provider = "groq"
        else:
            self.provider = "gemini"

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_model_candidates = [
            self.groq_model,
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen/qwen3-32b",
            "openai/gpt-oss-20b",
        ]
        self.model_candidates = [
            self.model_name,
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ]

        self.is_initialized = False

        if self.provider == "groq":
            # Groq key önceliği: GROQ_API_KEY > GEMINI_API_KEY > GOOGLE_API_KEY
            self.groq_api_key = (
                self.groq_api_key
                or self.api_key
                or os.getenv("GOOGLE_API_KEY")
            )
            if not self.groq_api_key:
                api_logger.warning(
                    "GROQ provider selected but no API key found "
                    "(GROQ_API_KEY / GEMINI_API_KEY / GOOGLE_API_KEY)."
                )
                return
            self.is_initialized = True
            api_logger.info(
                f"✅ Groq AI Service initialized successfully (model={self.groq_model})"
            )
            return

        if not self.api_key:
            api_logger.warning(
                "GEMINI_API_KEY not found in environment variables. "
                "AI Service will not function properly."
            )
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.is_initialized = True
            api_logger.info(
                f"✅ Gemini AI Service initialized successfully (model={self.model_name})"
            )
        except Exception as e:
            api_logger.error(f"Failed to initialize Gemini API: {str(e)}")
            self.is_initialized = False

    @staticmethod
    def _gemini_safety_settings() -> List[Dict[str, str]]:
        """
        Gemini API expects explicit harm categories.
        HARM_CATEGORY_UNSPECIFIED causes 400 validation errors.
        """
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    def _generate_with_model_fallback(self, prompt: str):
        """
        Try configured model first, then fallback models if API says model not found.
        """
        last_error: Optional[Exception] = None
        tried: set[str] = set()

        for model_name in self.model_candidates:
            if model_name in tried:
                continue
            tried.add(model_name)
            try:
                model = self.model if model_name == self.model_name else genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    safety_settings=self._gemini_safety_settings(),
                )
                if model_name != self.model_name:
                    # Cache successful fallback model for next requests.
                    self.model_name = model_name
                    self.model = model
                    api_logger.info(f"Switched Gemini model to fallback: {model_name}")
                return response
            except Exception as e:
                last_error = e
                error_text = str(e).lower()
                if "not found" in error_text or "is not supported" in error_text:
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("No Gemini model candidate available")

    def _generate_with_groq(self, messages: List[Dict[str, str]]) -> str:
        """Generate completion using Groq OpenAI-compatible endpoint."""
        if not self.groq_api_key:
            raise RuntimeError("Groq API key missing")
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        last_error_text = "Groq response error"

        with httpx.Client(timeout=60.0) as client:
            for model_name in self.groq_model_candidates:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 900,
                }
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )

                if response.status_code < 400:
                    data = response.json()
                    choices = data.get("choices") or []
                    if not choices:
                        return "Üzgünüm, yanıt oluşturamadım."
                    message = choices[0].get("message") or {}
                    if model_name != self.groq_model:
                        self.groq_model = model_name
                        api_logger.info(f"Switched Groq model to fallback: {model_name}")
                    return str(message.get("content") or "Üzgünüm, yanıt oluşturamadım.")

                response_text = response.text
                last_error_text = response_text
                lowered = response_text.lower()
                if (
                    "decommissioned" in lowered
                    or "model_not_found" in lowered
                    or "not supported" in lowered
                    or "invalid model" in lowered
                ):
                    continue
                response.raise_for_status()

        raise RuntimeError(last_error_text[:500])
    
    def _build_system_prompt(self, student_context: Dict[str, Any]) -> str:
        """
        ✅ Sistem Prompt'u oluştur (RAG)
        Öğrenci profilini bağlamda sunarak uyarlanmış cevaplar al
        
        Args:
            student_context: {
                'name': 'Ahmet',
                'field_type': 'SAY',
                'tyt_score': 250.0,
                'ayt_score': 300.0,
                'total_score': 350.0,
                'target_university': 'Boğaziçi',
                'target_department': 'Elektrik Mühendisliği',
                'preferred_cities': ['İstanbul', 'Ankara'],
                'interest_areas': ['Mühendislik', 'Teknoloji']
            }
        
        Returns:
            Sistem prompt metin
        """
        recommendation_summary = str(student_context.get("recommendation_summary", "") or "").strip()
        category_summary = str(student_context.get("category_summary", "") or "").strip()
        goal_proximity = str(student_context.get("goal_proximity", "") or "").strip()
        historical_trends = str(student_context.get("historical_trends", "") or "").strip()

        extra_context_blocks = []
        if recommendation_summary:
            extra_context_blocks.append(f"ÖNERİ ÖZETİ:\n{recommendation_summary}")
        if category_summary:
            extra_context_blocks.append(f"KATEGORİ ÖZETİ:\n{category_summary}")
        if goal_proximity:
            extra_context_blocks.append(f"HEDEF YAKINLIĞI:\n{goal_proximity}")
        if historical_trends:
            extra_context_blocks.append(f"TARİHSEL TRENDLER:\n{historical_trends}")
        exam_summary = str(student_context.get("exam_summary", "") or "").strip()
        preference_summary = str(student_context.get("preference_summary", "") or "").strip()
        performance_analysis = str(student_context.get("performance_analysis", "") or "").strip()
        personalized_plan_request = str(student_context.get("personalized_plan_request", "") or "").strip()
        response_style = str(student_context.get("response_style", "chat") or "chat").strip().lower()
        if exam_summary:
            extra_context_blocks.append(f"DENEME ÖZETİ:\n{exam_summary}")
        if preference_summary:
            extra_context_blocks.append(f"TERCİH ÖZETİ:\n{preference_summary}")
        if performance_analysis:
            extra_context_blocks.append(f"PERFORMANS ANALİZİ:\n{performance_analysis}")
        if personalized_plan_request:
            extra_context_blocks.append(f"PLAN ODAĞI:\n{personalized_plan_request}")
        extra_context = "\n\n".join(extra_context_blocks)

        style_instruction = (
            "YANIT BİÇİMİ: Doğal ve kısa konuşma dili kullan. Gereksiz başlık ekleme."
        )
        if response_style == "plan":
            style_instruction = (
                "YANIT BİÇİMİ: Plan odaklı cevap ver. "
                "Başlıklar kullan: 🎯 Kısa Özet, 🗺️ Adım Adım Plan, ✅ Bu Hafta Görevleri, 💡 Kısa Motivasyon."
            )
        elif response_style == "calculation":
            style_instruction = (
                "YANIT BİÇİMİ: Hesaplama odaklı kısa açıklama ver. "
                "En fazla 1-2 kısa başlık kullan; haftalık plan çıkarma."
            )
        elif response_style == "decision":
            style_instruction = (
                "YANIT BİÇİMİ: Karşılaştırmalı ve karar destekli cevap ver. "
                "Artı/eksi ve uygunluk analizi yap; sadece istenirse detaylı plan yaz."
            )

        context_text = f"""
        Sen YKS 3. Oturum Tercih Danışmanısın. Şu öğrenci profiline göre cevap vermelisin:
        
        ÖĞRENCİ PROFİLİ:
        - İsim: {student_context.get('name', 'Bilinmiyor')}
        - Alan: {student_context.get('field_type', 'Belirtilmemiş')}
        - TYT Puanı: {student_context.get('tyt_score', 'Hesaplanmamış')}
        - AYT Puanı: {student_context.get('ayt_score', 'Hesaplanmamış')}
        - Toplam Yerleştirme Puanı: {student_context.get('total_score', 'Hesaplanmamış')}
        - Hedef Üniversite: {student_context.get('target_university', 'Seçilmemiş')}
        - Hedef Bölüm: {student_context.get('target_department', 'Seçilmemiş')}
        - Tercih Edilen Şehirler: {', '.join(student_context.get('preferred_cities', []))}
        - İlgi Alanları: {', '.join(student_context.get('interest_areas', []))}
        
        KURALLAR:
        1. Cevaplarda öğrencinin netlerini ve puanlarını referans al
        2. Eğer öğrenci SAY'sa, SAY denemesi alınmayan SÖZ bölümünü önerme
        3. Eğer öğrenci SÖZ'se, SÖZ denemesi alınmayan SAY bölümünü önerme
        4. Hedef üniversite ve bölüm doğrultusunda tavsiyelerde bulun
        5. Tercih edilen şehirleri ve ilgi alanlarını göz önüne al
        6. Cevapları Türkçe, açık ve cesaret verici tonda yaz
        7. Eğer öğrenci hedefine ulaşamıyor ise, alternatif seçenekler öner
        8. Her zaman öğrenciye motivasyon ver
        9. Cevabı genel geçer yazma; mutlaka öğrenciye ait en az 2 somut veri (puan, net, tercih, deneme trendi) kullan
        10. Soru tipine göre cevap ver:
            - Puan hesaplama sorulursa alakasız haftalık plan yazma
            - Puan hesaplamada kesin bilmediğin formülü UYDURMA; öğrencinin mevcut TYT/AYT/TOPLAM puanını referans alıp uygulamadaki hesaplama akışını açıkla
            - Çalışma planı sorulursa net artırmaya dönük günlük görev ve hedef net ver
            - Tercih sorulursa öneri listesindeki bölüm/şehir bilgilerine dayalı karşılaştırma yap
        11. Soru tipine uygun format seç; her yanıtta aynı şablonu kullanma.
        12. Kullanıcı istemediyse uzun plan yazma.
        13. "1, 2, 3" gibi kuru numaralandırmayı gereksiz kullanma.
        14. İlk satırda mutlaka öğrencinin ismiyle hitap et: "Merhaba <isim>,"
        15. Eğer PERFORMANS ANALİZİ verildiyse, planda doğrudan bu metriklere atıf yap (son_net/ortalama/trend).
        16. Haftalık plan dengeli olsun: hedef ders odaklı ama diğer çekirdek derslerden tamamen kopmadan.
        17. {style_instruction}
        
        {extra_context}
        """
        return context_text.strip()
    
    def chat(
        self,
        message: str,
        student_id: Optional[int] = None,
        student_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        ✅ Chatbot ile konuş
        
        Args:
            message: Öğrencinin sorusu
            student_id: Öğrenci ID'si (opsiyonel)
            student_context: Öğrenci profil bilgileri (RAG için)
            conversation_history: Geçmiş konuşmalar
        
        Returns:
            {
                'success': True/False,
                'response': 'Cevap metni',
                'error': 'Hata mesajı (varsa)',
                'student_id': student_id
            }
        """
        try:
            # LLM'i başlat
            if not self.is_initialized:
                api_logger.error("LLM service not initialized")
                return {
                    'success': False,
                    'response': 'Üzgünüm, AI Danışman şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.',
                    'error': 'LLM service not initialized',
                    'student_id': student_id
                }
            
            # Sistem prompt'u hazırla (RAG)
            system_prompt = ""
            if student_context:
                system_prompt = self._build_system_prompt(student_context)
            else:
                system_prompt = "Sen YKS 3. Oturum Tercih Danışmanısın. Öğrencilerin tercih kararlarında yardımcı ol."
            
            api_logger.info(
                f"Processing chat message for student {student_id}",
                student_id=student_id,
                message_length=len(message)
            )
            
            # Konuşma geçmişini hazırla (Groq için message listesi)
            messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

            # Geçmiş iletileri ekle
            if conversation_history:
                for msg in conversation_history[-5:]:  # Son 5 mesajı al (token limiti için)
                    messages.append({
                        'role': msg.get('role', 'user'),
                        'content': msg.get('content', '')
                    })
            
            # Kullanıcının yeni mesajını ekle
            messages.append({
                'role': 'user',
                'content': message
            })
            
            if self.provider == "groq":
                assistant_response = self._generate_with_groq(messages)
            else:
                full_prompt = f"{system_prompt}\n\nÖğrenci Sorusu: {message}"
                response = self._generate_with_model_fallback(full_prompt)
                assistant_response = response.text if response else "Üzgünüm, yanıt oluşturamadım."
            
            api_logger.info(
                f"Chat response generated successfully",
                student_id=student_id,
                response_length=len(assistant_response)
            )
            
            return {
                'success': True,
                'response': assistant_response,
                'error': None,
                'student_id': student_id,
                'model': self.groq_model if self.provider == "groq" else self.model_name
            }
        
        except ValueError as e:
            # Prompt injection, blocked content, vb.
            error_message = str(e)
            api_logger.warning(
                f"Prompt validation error: {error_message}",
                student_id=student_id
            )
            return {
                'success': False,
                'response': 'Sorunuz veya cevap güvenlik nedeniyle işlenemiyor. Lütfen farklı bir şekilde sorun.',
                'error': f'Validation error: {error_message}',
                'student_id': student_id
            }
        
        except Exception as e:
            # Genel hata (quota, connection, vb.)
            error_message = str(e)
            api_logger.error(
                f"LLM API error: {error_message}",
                student_id=student_id,
                error_type=type(e).__name__
            )
            
            # Hata türüne göre kullanıcı dostu mesaj
            if 'quota' in error_message.lower() or 'rate limit' in error_message.lower():
                user_message = 'API kota limiti aşıldı. Lütfen daha sonra tekrar deneyin.'
            elif 'api key' in error_message.lower() or 'unauthorized' in error_message.lower() or 'invalid_api_key' in error_message.lower():
                user_message = 'API anahtarı geçerli değil. Sistem yöneticisine başvurun.'
            elif 'timeout' in error_message.lower():
                user_message = 'Bağlantı zaman aşımına uğradı. Lütfen daha sonra tekrar deneyin.'
            else:
                user_message = f'Üzgünüm, bir hata oluştu: {error_message[:100]}'
            
            return {
                'success': False,
                'response': user_message,
                'error': error_message,
                'student_id': student_id
            }
    
    def get_recommendations_for_student(
        self,
        student_context: Dict[str, Any],
        top_departments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Öğrenci için akıllı öneriler oluştur
        
        Args:
            student_context: Öğrenci profili
            top_departments: Puanlanmış bölümler (id, name, university, score vb.)
        
        Returns:
            {
                'success': True/False,
                'recommendations': 'Metin format öneriler',
                'error': Optional
            }
        """
        try:
            if not self.is_initialized:
                return {
                    'success': False,
                    'recommendations': None,
                    'error': 'Gemini API not initialized'
                }
            
            # Bölümleri formatla
            departments_text = "\n".join([
                f"- {dept.get('name', 'Unknown')} "
                f"({dept.get('university', 'Unknown')} Üniversitesi) "
                f"[Uyum Puanı: {dept.get('score', 0):.1f}]"
                for dept in top_departments[:10]  # İlk 10'u al
            ])
            
            prompt = f"""
            {self._build_system_prompt(student_context)}
            
            Öğrenciye aşağıdaki önerileri değerlendir ve en uygun 3-5 bölüm seç:
            
            {departments_text}
            
            Önerilerini şu formatta sun:
            1. Bölüm adı - Neden uygun olduğu (1-2 cümle)
            2. ...
            
            Praktik ve motive edici ol.
            """
            
            if self.provider == "groq":
                recommendations_text = self._generate_with_groq(
                    [
                        {"role": "system", "content": "Sen YKS tercih danışmanısın. Türkçe yanıt ver."},
                        {"role": "user", "content": prompt},
                    ]
                )
            else:
                response = self._generate_with_model_fallback(prompt)
                recommendations_text = response.text if response else "Öneriler oluşturulamadı."
            
            api_logger.info(
                "Recommendations generated successfully",
                student_id=student_context.get('id', 'unknown')
            )
            
            return {
                'success': True,
                'recommendations': recommendations_text,
                'error': None
            }
        
        except Exception as e:
            api_logger.error(f"Error generating recommendations: {str(e)}")
            return {
                'success': False,
                'recommendations': None,
                'error': str(e)
            }


# Singleton instance
_ai_service = None


def get_ai_service() -> AIService:
    """AI Service'i al (Singleton pattern)"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
