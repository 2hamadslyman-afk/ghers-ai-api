# Ghers AI — API جاهزة للنشر (نسخة تجريبية)

خدمة مخصصة لربط شاشة **Ghers AI** في تطبيق MIT App Inventor بـ:

1. **تصنيف الغطاء الأرضي لعام 2025** المستنتج من نموذج عالمي مدرب مسبقًا، عبر Esri / Impact Observatory / Microsoft.
2. **الحرارة والرطوبة الحالية المقدّرتين بالنماذج**، و**مجموع الأمطار المقدّر في آخر 7 أيام مكتملة** من Open-Meteo.

**لا تقوم هذه الخدمة بتدريب نموذج جديد ولا تتوقع نجاح إنبات البذور أو ملاءمة نوع نباتي بعينه.**

## المتطلبات

- Python 3.10+ (يفضل 3.11)
- إنترنت يمكنه الوصول إلى Esri وOpen-Meteo
- استضافة FastAPI (مثل Render) للحصول على رابط HTTPS عام

## تشغيل محلي

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

- فحص: `http://127.0.0.1:8000/health`
- وثائق وتجربة API: `http://127.0.0.1:8000/docs`
- عنوان التحليل: `POST http://127.0.0.1:8000/analyze`

**مهم:** رابط localhost لا يعمل من آيفون زميلك إذا كان الخادم يعمل على جهازك فقط؛ تحتاج نشر الخدمة للحصول على رابط HTTPS عام.

## نشر على Render

1. ضع ملفات المشروع (`main.py`, `requirements.txt`, `render.yaml`) في مستودع GitHub.
2. سجّل الدخول إلى [Render](https://render.com/)، ثم اختر New → Web Service واربط مستودع GitHub.
3. اختر Python ونوع الخطة Free للاختبار، وأدخل عند الحاجة:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. بعد اكتمال النشر، افتح `https://YOUR-SERVICE.onrender.com/health` للتحقق.
5. رابط التطبيق يصبح `https://YOUR-SERVICE.onrender.com/analyze`، **واستبدل YOUR-SERVICE باسم الخدمة الفعلي**.
6. جرّب طلبًا حقيقيًا من `/docs` (أو Postman)، ولا تكتفِ بعودة `/health`.

خدمة Render المجانية قد تتوقف عند عدم الاستخدام ثم تستيقظ عند أول طلب؛ ضع مهلة مناسبة في تطبيق الآيفون، وجرّب التطبيق قبل العرض.

## عقد الـ API المتفق عليه مع مطور التطبيق

**الطريقة:** `POST`  
**المسار:** `/analyze`  
**Content-Type:** `application/json`  
**المصادقة:** لا توجد في الإعداد الافتراضي للعرض التجريبي. إذا أضفت متغير البيئة `GHERS_API_KEY` على الخادم، يجب إرسال Header باسم `X-API-Key` بالقيمة المطابقة.

مثال الطلب:

```json
{
  "latitude": 26.3592,
  "longitude": 43.9818
}
```

**مثال الاستجابة** في ملف `example_response.json` **افتراضي لأغراض الاختبار البصري**، وليس قراءة حقيقية لبريدة.

الحقول المطلوبة في التطبيق:

- `land_cover` = اسم فئة الغطاء الأرضي باللغة الإنجليزية، أو `Unavailable` إن فشل مصدرها.
- `summary` = نص شرح للموقع وحدود تفسيره.
- `climate.temperature_c` = حرارة حالية تقديرية بالدرجة المئوية، أو `null`.
- `climate.humidity_pct` = رطوبة نسبية حالية تقديرية (%)، أو `null`.
- `climate.precipitation_mm` = **مجموع الأمطار في الأيام السبعة المكتملة السابقة** (ملم)، أو `null`. **ليست أمطار السنة أو الساعة الحالية**.
- `status` = `ok` (المصدران) / `partial` (مصدر واحد فقط) / `unavailable` (كلاهما لا يعمل).
- `details.land_cover_year` = 2025 (تصنيف تاريخي وليس صورة آنية).

## MIT App Inventor — خطوات البلوكات

1. من زر Analyze Location، خذ `latitude` و`longitude` **كأرقام** من مركز الخريطة.
2. اضبط `Web1.Url` على رابط النشر HTTPS متبوعًا بـ `/analyze`.
3. اضبط `Web1.RequestHeaders` كقائمة فيها القائمة الفرعية `["Content-Type", "application/json"]`.
4. أنشئ **dictionary** فيه مفتاحان `latitude` و `longitude` وقيمتان رقميتان، ثم استخدم `Web1.JsonObjectEncode` لتحويله إلى JSON text.
5. استدعِ `Web1.PostText` مع النص الناتج.
6. في `when Web1.GotText`: تحقق أولًا أن `responseCode=200`، ثم استدعِ `Web1.JsonTextDecodeWithDictionaries(responseContent)`، واقرأ `land_cover` و`summary` والقاموس الفرعي `climate`.
7. استعمل مفاتيح `temperature_c`, `humidity_pct`, `precipitation_mm` من القاموس الفرعي. عند `null` أو `Unavailable`، اعرض `N/A` بدل أي رقم تخميني. انتبه لقيمة `status=partial`.
8. في حال `503` أو `TimedOut`، أظهر رسالة خطأ واترك نتيجة المعاينة التجريبية واضحة أنها **Demo**، ولا تحفظها على أنها نتيجة فعلية.
9. إن احتجتم مزامنة نتيجة التحليل مع TinyDB، احفظوها تحت معرّف عملية الغرس أو إحداثياتها وتاريخ التقييم، مع `status` ونسخة البيانات، لتجنب الخلط بين النتائج القديمة والجديدة.

## اختبار تجريبي بعد النشر

```bash
curl -X POST 'https://YOUR-SERVICE.onrender.com/analyze' \
  -H 'Content-Type: application/json' \
  -d '{"latitude":26.3592,"longitude":43.9818}'
```

رموز الاستجابة:

- `200`: على الأقل أحد مصدري البيانات أعاد نتيجة؛ افحص `status`.
- `422`: الإحداثيات غير صالحة أو JSON غير صحيح.
- `401`: مفتاح API غير موجود أو غير صحيح عند تفعيل المصادقة.
- `503`: لم يصل أي مصدر، ويعود خطأ JSON يشرح المشكلة.

## مصادر وترخيص وقيود

- [Esri ImageServer](https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer): Impact Observatory, Microsoft, Esri. خريطة الغطاء الأرضي السنوية 2025 بدقة 10 أمتار تقريبًا، وترخيص خرائط Maps for Good هو CC BY 4.0 مع وجوب نسب المصدر.
- [Open-Meteo](https://open-meteo.com/en/docs): تقديرات نماذج الطقس؛ تحقق من شروط استخدام واجهة API ومستوى الاستخدام غير التجاري.
- التقييم يصف الغطاء الأرضي والطقس **فقط**. لا يوجد تحليل تربة أو ملوحة أو متطلبات النوع النباتي. لا تعرض درجة «مناسبة للغرس» أو «احتمال نجاح» اعتمادًا على هذه الخدمة وحدها.
- تصنيف Esri سنوي لعام 2025، وقد يختلف عن حالة الأرض وقت الغرس. إحداثيات GPS التقريبية والدقة المكانية للخرائط قد تؤثر في النتيجة.
- تعذر التحقق من استجابة الجهات الخارجية مباشرة من بيئة إعداد هذا الملف؛ اختبارات الوحدة محلية مع محاكاة لاستجابات المصدر. **اجعل طلبًا حيًا ناجحًا من 3 مواقع سعودية شرطًا لقبول النسخة للعرض**.

## اختبارات الكود المحلي

```bash
pip install pytest
pytest -q tests/test_api.py
```

الاختبارات تستخدم **Mock responses** ولا تثبت اتصالًا فعليًا بمصادر البيانات أو بدقة تصنيف المواقع.
