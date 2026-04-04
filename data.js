// بيانات وهمية - 8 رسائل دعم عملاء باللهجة الفلسطينية

const dummyMessages = [
    {
        id: "MSG-001",
        customerName: "ريم أبو علي",
        email: "reem.abuali@example.com",
        messagePreview: "الطلبية تبعتي مكتوب عليها استلمت بس ما وصلتني.",
        fullMessage: "مرحبا، رقم التتبع #TRK-88291 بيقول إنو الطلبية وصلت امبارح الساعة 3 العصر. بس بحثت عند الباب وعند الجيران وعند أمانات البناية وما لقيتها. ممكن تساعدوني تتابعوا الموضوع ولا تبعتولي بديل؟",
        sentiment: "Negative",
        intent: "شكوى",
        urgency: "High",
        timestamp: "2026-03-27T08:15:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 94,
        suggestedReply: "آسفين كتير يا ريم إنو الطلبية ما وصلتك. فتحنا تحقيق مع شركة التوصيل هلق. إذا ما قدروا يحددوا مكانها خلال 24 ساعة، رح نرسلك بديل أو نرجعلك الفلوس فوراً.",
        conversationHistory: [
            { sender: "ريم أبو علي", text: "الطلبية تبعتي مكتوب عليها استلمت بس ما وصلتني.", time: "08:15 ص" }
        ]
    },
    {
        id: "MSG-002",
        customerName: "محمد الخطيب",
        email: "m.khatib@example.com",
        messagePreview: "عندي سؤال عن مميزات الاشتراك المدفوع.",
        fullMessage: "هلا، أنا هلق على الباقة الأساسية وعم بفكر أترقى. ممكن توضحولي إذا اشتراك Pro بيشمل طلبات API بدون حد، ولا في حد شهري؟ شكراً مسبقاً.",
        sentiment: "Neutral",
        intent: "استفسار",
        urgency: "Low",
        timestamp: "2026-03-27T08:42:00Z",
        status: "Pending",
        assignedAgent: "سارة علي",
        confidence: 88,
        suggestedReply: "هلا محمد، شكراً لتواصلك معنا! اشتراك Pro بيشمل لغاية 100,000 طلب API بالشهر. إذا بدك بدون حد، ممكن تفكر بباقة Enterprise.",
        conversationHistory: [
            { sender: "محمد الخطيب", text: "عندي سؤال عن مميزات الاشتراك المدفوع.", time: "08:42 ص" }
        ]
    },
    {
        id: "MSG-003",
        customerName: "كريم الشريف",
        email: "k.sharif@example.com",
        messagePreview: "مش قادر أدخل على حسابي وإعادة تعيين كلمة السر ما بتشتغل.",
        fullMessage: "هاد الشي محبط كتير. من ساعتين وأنا بحاول أدخل. ضغطت على 'نسيت كلمة السر' بس ما جاني أي إيميل. ارجوكم حلوا هاد الموضوع بسرعة، محتاج أوصل لفواتيري.",
        sentiment: "Negative",
        intent: "طلب",
        urgency: "High",
        timestamp: "2026-03-27T09:05:00Z",
        status: "Escalated",
        assignedAgent: "مايكل براون",
        confidence: 91,
        suggestedReply: "هلا كريم، آسفين جداً على هاد الإزعاج. بعثتلك رابط إعادة تعيين يدوي على الإيميل الاحتياطي إذا عندك، أو ممكن نتحقق من هويتك بطريقة ثانية. خلينا نحل الموضوع هلق.",
        conversationHistory: [
            { sender: "كريم الشريف", text: "مش قادر أدخل على حسابي وإعادة تعيين كلمة السر ما بتشتغل.", time: "09:05 ص" }
        ]
    },
    {
        id: "MSG-004",
        customerName: "دانا النجار",
        email: "dana.najjar@example.com",
        messagePreview: "خدمة ممتازة، بدي أشارككم رأيي!",
        fullMessage: "بدي أشكركم على موظف الدعم جون. ساعدني أربط النظام بشكل مثالي وصار يشتغل بدون أي مشكلة. استمروا بهيك مستوى!",
        sentiment: "Positive",
        intent: "تقييم",
        urgency: "Low",
        timestamp: "2026-03-27T09:30:00Z",
        status: "Responded",
        assignedAgent: "جون كارتر",
        confidence: 98,
        suggestedReply: "شكراً كتير يا دانا على كلامك الحلو! رح نوصل شكرك لجون بالتأكيد. يوم سعيد!",
        conversationHistory: [
            { sender: "دانا النجار", text: "بدي أشكركم على موظف الدعم جون وعلى الخدمة الممتازة.", time: "09:30 ص" },
            { sender: "موظف (جون كارتر)", text: "شكراً كتير يا دانا على كلامك الحلو! يوم سعيد!", time: "09:45 ص" }
        ]
    },
    {
        id: "MSG-005",
        customerName: "إياد حمدان",
        email: "iyad.hamdan@example.com",
        messagePreview: "بدي استرجع فلوس آخر فاتورة.",
        fullMessage: "مرحبا، لاحظت اليوم الصبح إنو في خصم من بطاقتي لتجديد سنوي ما وافقت عليه. ارجوكم ألغوا اشتراكي فوراً وارجعوا لي الـ 120 دولار.",
        sentiment: "Negative",
        intent: "طلب",
        urgency: "Medium",
        timestamp: "2026-03-27T09:45:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 85,
        suggestedReply: "هلا إياد، ألغينا اشتراكك كما طلبت. عملية استرداد الـ 120 دولار تمت وراح تظهر بحسابك خلال 3-5 أيام عمل.",
        conversationHistory: [
            { sender: "إياد حمدان", text: "بدي استرجع فلوس آخر فاتورة.", time: "09:45 ص" }
        ]
    },
    {
        id: "MSG-006",
        customerName: "سمر العمري",
        email: "samar.omari@example.com",
        messagePreview: "متابعة على طلبي السابق (#TK-441)",
        fullMessage: "هلا، منذ ثلاثة أيام أرسلت تذكرة عن خلل في ميزة التصدير بالداشبورد وما رد عليّ أحد. في أي تحديث؟",
        sentiment: "Neutral",
        intent: "استفسار",
        urgency: "Medium",
        timestamp: "2026-03-27T10:10:00Z",
        status: "Pending",
        assignedAgent: "نور حسن",
        confidence: 77,
        suggestedReply: "هلا سمر، آسفين على التأخير. فريق الهندسة هلق شغال على تذكرة #TK-441. رح نرفع أولويتها ونرجعلك بتحديث قبل نهاية اليوم.",
        conversationHistory: [
            { sender: "سمر العمري", text: "متابعة على طلبي السابق (#TK-441)", time: "10:10 ص" }
        ]
    },
    {
        id: "MSG-007",
        customerName: "خالد أبو رية",
        email: "khaled.aburayya@example.com",
        messagePreview: "ممكن أغير عنوان التوصيل؟",
        fullMessage: "هلا، طلبت طلبية قبل 10 دقائق بس لاحظت إني حطيت العنوان القديم. ممكن تغيروا عنوان التوصيل لـ شارع النجاح 123، رام الله؟",
        sentiment: "Neutral",
        intent: "طلب",
        urgency: "High",
        timestamp: "2026-03-27T10:25:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 92,
        suggestedReply: "هلا خالد! عدّلنا عنوان التوصيل لشارع النجاح 123، رام الله بنجاح. راح يوصلك إيميل تأكيد هلق.",
        conversationHistory: [
            { sender: "خالد أبو رية", text: "ممكن أغير عنوان التوصيل؟", time: "10:25 ص" }
        ]
    },
    {
        id: "MSG-008",
        customerName: "نور البطش",
        email: "nour.battsh@example.com",
        messagePreview: "والله التحديث الجديد روعة!",
        fullMessage: "بس بدي أقولكم إن الوضع الليلي الجديد والواجهة الجديدة شي ما بيتوصف. كتير أريح للعين. شكراً للفريق!",
        sentiment: "Positive",
        intent: "تقييم",
        urgency: "Low",
        timestamp: "2026-03-27T10:50:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 99,
        suggestedReply: "هلا نور، يسعدنا إنك عاجبك الوضع الليلي الجديد! كلامك الحلو بسعدنا كتير.",
        conversationHistory: [
            { sender: "نور البطش", text: "والله التحديث الجديد روعة!", time: "10:50 ص" }
        ]
    }
];

if (typeof module !== 'undefined' && module.exports) {
    module.exports = dummyMessages;
} else {
    window.messagesData = dummyMessages;
}
