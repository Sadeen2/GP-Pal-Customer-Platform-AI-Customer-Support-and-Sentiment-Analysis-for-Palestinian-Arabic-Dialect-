// Mock array of 8 realistic customer support messages

const dummyMessages = [
    {
        id: "MSG-001",
        customerName: "Alice Freeman",
        email: "alice.f@example.com",
        messagePreview: "My package was marked as delivered but I haven't received it.",
        fullMessage: "Hello support, my tracking number #TRK-88291 shows that my package was delivered yesterday at 3:00 PM. However, I have checked my porch, with my neighbors, and the mailroom, but it's nowhere to be found. Can you please help me track this down or issue a replacement?",
        sentiment: "Negative",
        intent: "Complaint",
        urgency: "High",
        timestamp: "2026-03-27T08:15:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 94,
        suggestedReply: "I'm so sorry to hear your package hasn't arrived, Alice. I'm opening an investigation with the courier right now. If they cannot locate it within 24 hours, we will immediately process a requested replacement or refund for you.",
        conversationHistory: [
            { sender: "Alice Freeman", text: "My package was marked as delivered but I haven't received it.", time: "08:15 AM" }
        ]
    },
    {
        id: "MSG-002",
        customerName: "Bob Smith",
        email: "bob.smith@example.com",
        messagePreview: "Question about the pro subscription features.",
        fullMessage: "Hi team, I am currently on the basic plan and considering an upgrade. Could you please clarify if the Pro subscription includes unlimited API calls, or is there a monthly cap? Thanks in advance.",
        sentiment: "Neutral",
        intent: "Inquiry",
        urgency: "Low",
        timestamp: "2026-03-27T08:42:00Z",
        status: "Pending",
        assignedAgent: "Sarah Ali",
        confidence: 88,
        suggestedReply: "Hi Bob, thanks for reaching out! Our Pro subscription includes up to 100,000 API calls per month. If you need unlimited calls, you might want to consider our Enterprise plan.",
        conversationHistory: [
            { sender: "Bob Smith", text: "Question about the pro subscription features.", time: "08:42 AM" }
        ]
    },
    {
        id: "MSG-003",
        customerName: "Carlos Diaz",
        email: "cdiaz@example.com",
        messagePreview: "Can't log in into my account. Password reset not working.",
        fullMessage: "This is very frustrating. I've been trying to log in for the past two hours. I hit 'Forgot Password' and never receive the reset email. Please fix this immediately, I need to access my invoices.",
        sentiment: "Negative",
        intent: "Request",
        urgency: "High",
        timestamp: "2026-03-27T09:05:00Z",
        status: "Escalated",
        assignedAgent: "Michael Brown",
        confidence: 91,
        suggestedReply: "Hi Carlos, I sincerely apologize for the inconvenience. I have manually triggered a password reset link to a secondary email if you have one, or I can verify your identity manually. Let's get this sorted right away.",
        conversationHistory: [
            { sender: "Carlos Diaz", text: "Can't log in into my account. Password reset not working.", time: "09:05 AM" }
        ]
    },
    {
        id: "MSG-004",
        customerName: "Diana Prince",
        email: "diana.p@example.com",
        messagePreview: "Great service, just wanting to leave some feedback!",
        fullMessage: "I just wanted to drop a quick note to say thank you to your support rep John. He helped me set up my integration perfectly, and it works flawlessly. Keep up the great work!",
        sentiment: "Positive",
        intent: "Feedback",
        urgency: "Low",
        timestamp: "2026-03-27T09:30:00Z",
        status: "Responded",
        assignedAgent: "John Carter",
        confidence: 98,
        suggestedReply: "Thank you so much for the kind words, Diana! We'll be sure to pass along your praise to John. Have a wonderful day!",
        conversationHistory: [
            { sender: "Diana Prince", text: "I just wanted to drop a quick note to say thank you...", time: "09:30 AM" },
            { sender: "Agent (John Carter)", text: "Thank you so much for the kind words, Diana!...", time: "09:45 AM" }
        ]
    },
    {
        id: "MSG-005",
        customerName: "Evan Zhao",
        email: "ezhao88@example.com",
        messagePreview: "I need a refund for my last invoice.",
        fullMessage: "Hello, I noticed a charge on my credit card this morning for an annual renewal that I did not authorize. Please cancel my account immediately and refund the $120 charge.",
        sentiment: "Negative",
        intent: "Request",
        urgency: "Medium",
        timestamp: "2026-03-27T09:45:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 85,
        suggestedReply: "Hi Evan, I've gone ahead and cancelled your subscription as requested. The refund of $120 has been processed and should reflect in your account in 3-5 business days.",
        conversationHistory: [
            { sender: "Evan Zhao", text: "I need a refund for my last invoice.", time: "09:45 AM" }
        ]
    },
    {
        id: "MSG-006",
        customerName: "Fiona Gallagher",
        email: "fiona.g@example.com",
        messagePreview: "Following up on my previous ticket (#TK-441)",
        fullMessage: "Hi, I submitted a ticket three days ago about the export feature bug on the dashboard and haven't heard back. Is there any update on this?",
        sentiment: "Neutral",
        intent: "Inquiry",
        urgency: "Medium",
        timestamp: "2026-03-27T10:10:00Z",
        status: "Pending",
        assignedAgent: "Noor Hassan",
        confidence: 77,
        suggestedReply: "Hi Fiona, I apologize for the delay. Our engineering team is currently looking into ticket #TK-441. I will bump the priority on this and update you directly by the end of the day.",
        conversationHistory: [
            { sender: "Fiona Gallagher", text: "Following up on my previous ticket (#TK-441)", time: "10:10 AM" }
        ]
    },
    {
        id: "MSG-007",
        customerName: "George Miller",
        email: "gmiller@example.com",
        messagePreview: "Is it possible to change my shipping address?",
        fullMessage: "Hi, I just placed an order 10 minutes ago, but I realize I used my old address. Can you please update my shipping address to 123 New Way Rd, Springfield?",
        sentiment: "Neutral",
        intent: "Request",
        urgency: "High",
        timestamp: "2026-03-27T10:25:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 92,
        suggestedReply: "Hi George! I've successfully intercepted your order and updated the shipping address to 123 New Way Rd, Springfield. You'll receive a confirmation email shortly.",
        conversationHistory: [
            { sender: "George Miller", text: "Is it possible to change my shipping address?", time: "10:25 AM" }
        ]
    },
    {
        id: "MSG-008",
        customerName: "Hannah Abbott",
        email: "hannah.a@example.com",
        messagePreview: "Wow, the new update is amazing!",
        fullMessage: "Just wanted to let your team know that the new dark mode and overhauled UI is spectacular. It's so much easier on the eyes. Thanks!",
        sentiment: "Positive",
        intent: "Feedback",
        urgency: "Low",
        timestamp: "2026-03-27T10:50:00Z",
        status: "Pending",
        assignedAgent: "Unassigned",
        confidence: 99,
        suggestedReply: "Hi Hannah, we are thrilled to hear that you're enjoying the new dark mode! Feedback like yours makes our day.",
        conversationHistory: [
            { sender: "Hannah Abbott", text: "Wow, the new update is amazing!", time: "10:50 AM" }
        ]
    }
];

if (typeof module !== 'undefined' && module.exports) {
    module.exports = dummyMessages;
} else {
    window.messagesData = dummyMessages;
}
