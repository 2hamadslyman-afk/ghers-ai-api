# ربط غرس بالآيفون — قائمة التحقق

- Web1.Url: رابط HTTPS الفعلي متبوعًا بـ /analyze، بعد نشر الخدمة.
- Web1.SaveResponse: false حتى تصل الاستجابة إلى GotText.
- Web1.RequestHeaders: قائمة تحتوي قائمة فرعية من Content-Type وapplication/json.
- استخدم JsonObjectEncode لقاموس latitude وlongitude بأرقام، ثم PostText.
- في GotText افحص responseCode قبل فك JSON.
- 200: اقرأ status ثم land_cover وsummary وقاموس climate.
- partial: اعرض البيانات المتاحة فقط وعبارة «بيانات غير مكتملة».
- 503: النتيجة داخل detail؛ أظهر تعذر الوصول إلى المصدرين.
- 401: تحقق من X-API-Key إذا فُعّل على الخادم.
- 422: تحقق من الإحداثيات والطلب.
- عالج TimedOut وScreen.ErrorOccurred وأعد تفعيل زر التحليل.
- افحص القيمة null فعليًا في نسخة Companion المستعملة؛ لا تحول القيمة المفقودة إلى صفر.
- أظهر نسب المصادر Esri / Impact Observatory / Microsoft وOpen-Meteo.
- الاختبار النهائي يجب أن يتم على الآيفون: ثلاث إحداثيات، حالة فشل الشبكة، وعدم عرض نتيجة قديمة على أنها جديدة.

الكود الرسمي لمكوّن Web على iOS يتضمن JsonObjectEncode وJsonTextDecodeWithDictionaries وGotText:
https://github.com/mit-cml/appinventor-sources/blob/master/appinventor/components-ios/src/Web.swift

لم يُرفق ملف التطبيق .aia؛ لم تُعدل بلوكاته أو تُختبر نسخة آيفون حتى الآن.
