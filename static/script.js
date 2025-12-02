// --- Element Selectors ---
const sidebarOverlay = document.getElementById('sidebar-overlay');
const headerNewChatBtn = document.getElementById('header-new-chat-btn'); 
const newChatBtn = document.getElementById('new-chat-btn');
const sidebar = document.getElementById('sidebar');
const menuBtn = document.getElementById('menu-btn');
const chatContainer = document.getElementById('chat-container');
const welcomeMessageContainer = document.getElementById('welcome-message-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const addBtn = document.getElementById('add-btn');
const addMenu = document.getElementById('add-menu');
const uploadFileBtn = document.getElementById('upload-file-btn');
const uploadCodeBtn = document.getElementById('upload-code-btn');
const fileInput = document.getElementById('file-input');
const filePreviewContainer = document.getElementById('file-preview-container');
const webSearchToggleBtn = document.getElementById('web-search-toggle-btn');
const micBtn = document.getElementById('mic-btn');
const voiceModeBtn = document.getElementById('voice-mode-btn');
const modeIndicatorContainer = document.getElementById('mode-indicator-container');
const voiceOverlay = document.getElementById('voice-overlay');
const voiceStatusText = document.getElementById('voice-status-text');
const voiceInterimTranscript = document.getElementById('voice-interim-transcript');
const voiceVisualizer = document.getElementById('voice-visualizer');
const endVoiceBtn = document.getElementById('end-voice-btn');
const userMenuBtn = document.getElementById('user-menu-btn');
const userMenu = document.getElementById('user-menu');
const settingsMenuItem = document.getElementById('settings-menu-item');
const chatHistoryContainer = document.getElementById('chat-history-container');
const searchHistoryInput = document.getElementById('search-history-input');
const tempChatBanner = document.getElementById('temp-chat-banner');
const saveToDbBtn = document.getElementById('save-to-db-btn');

// Cyber Training Elements
const cyberTrainingBtn = document.getElementById('cyber-training-btn');
const cyberModal = document.getElementById('cyber-modal');
const closeCyberModalBtn = document.getElementById('close-cyber-modal');
const levelBtns = document.querySelectorAll('.level-btn');
const cyberGameControls = document.getElementById('cyber-game-controls');
const endCyberGameBtn = document.getElementById('end-cyber-game-btn');

// Settings Modal
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const closeSettingsBtnDesktop = document.getElementById('close-settings-btn-desktop');
const generalTabBtn = document.getElementById('general-tab-btn');
const profileTabBtn = document.getElementById('profile-tab-btn');
const usageTabBtn = document.getElementById('usage-tab-btn');
const generalSettingsContent = document.getElementById('general-settings-content');
const profileSettingsContent = document.getElementById('profile-settings-content');
const usageSettingsContent = document.getElementById('usage-settings-content');
const settingsContentTitle = document.getElementById('settings-content-title');
const languageSelect = document.getElementById('language-select');
const themeBtns = document.querySelectorAll('.theme-btn');
const logoutBtn = document.getElementById('logout-btn');
const deleteAccountBtn = document.getElementById('delete-account-btn');
const logoutMenuItem = document.getElementById('logout-menu-item');
const emailVerificationStatusText = document.getElementById('email-verification-status-text');
const verifyEmailBtn = document.getElementById('verify-email-btn');

// Library Modal
const libraryBtn = document.getElementById('library-btn');
const libraryModal = document.getElementById('library-modal');
const closeLibraryBtn = document.getElementById('close-library-btn');
const libraryGrid = document.getElementById('library-grid');
const libraryEmptyMsg = document.getElementById('library-empty-msg');

// Plan & Usage Elements
const upgradePlanSidebarBtn = document.getElementById('upgrade-plan-sidebar-btn');
const menuUsername = document.getElementById('menu-username');
const sidebarUserPlan = document.getElementById('sidebar-user-plan');
const sidebarUsageDisplay = document.getElementById('sidebar-usage-display');
const planTitle = document.getElementById('plan-title');
const usageCounter = document.getElementById('usage-counter');
const usageProgressBar = document.getElementById('usage-progress-bar');
const upgradeSection = document.getElementById('upgrade-section');
const premiumSection = document.getElementById('premium-section');
const razorpayBtn = document.getElementById('razorpay-btn');
const usagePlanSection = document.getElementById('usage-plan-section');


// --- Global State ---
const markdownConverter = new showdown.Converter();
let fileData = null;
let fileType = null;
let fileInfoForDisplay = null;
let currentMode = null; 
let recognition;
let isVoiceConversationActive = false;
let isTemporaryChatActive = false;
let chatHistory = [];
let currentChat = [];
let currentChatId = null;

// Cyber Game State
let isCyberGameActive = false;
let currentCyberLevel = 'Basic';

// Plan & Usage State
let usageCounts = {
    messages: 0,
    webSearches: 0
};
const usageLimits = {
    messages: 15,
    webSearches: 1
};
let isPremium = false;
let isAdmin = false;

// --- Sidebar & Temp Chat Logic ---
function openSidebar() {
    sidebar.classList.remove('-translate-x-full');
    sidebarOverlay.classList.remove('hidden');
}

function closeSidebar() {
    sidebar.classList.add('-translate-x-full');
    sidebarOverlay.classList.add('hidden');
}

menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (sidebar.classList.contains('-translate-x-full')) {
        openSidebar();
    } else {
        closeSidebar();
    }
});
sidebarOverlay.addEventListener('click', closeSidebar);

headerNewChatBtn.addEventListener('click', () => {
    isTemporaryChatActive = false;
    startNewChat();
});

newChatBtn.addEventListener('click', () => {
    isTemporaryChatActive = false;
    startNewChat();
    closeSidebar();
});

// --- Event Listeners ---
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });

// --- MODIFIED FILE UPLOAD LISTENERS ---
uploadFileBtn.addEventListener('click', () => {
    fileInput.accept = "image/*,.pdf,.doc,.docx";
    fileInput.click();
});

uploadCodeBtn.addEventListener('click', () => {
    fileInput.accept = ".txt,.py,.js,.java,.c,.cpp,.h,.html,.css,.json,.md,.sh,.rb,.go,.php,.swift,.kt";
    fileInput.click();
});

fileInput.addEventListener('change', handleFileSelect);

addBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    addMenu.classList.toggle('hidden');
});

userMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    userMenu.classList.toggle('hidden');
});

window.addEventListener('click', (e) => {
     if (!addMenu.classList.contains('hidden') && !addBtn.contains(e.target)) {
        addMenu.classList.add('hidden');
    }
    if (userMenu && !userMenu.classList.contains('hidden') && !userMenuBtn.contains(e.target) && !userMenu.contains(e.target)) {
        userMenu.classList.add('hidden');
    }
});

messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    let newHeight = messageInput.scrollHeight;
    messageInput.style.height = `${newHeight}px`;
    
    const hasText = messageInput.value.trim() !== '';
    const shouldShowSend = hasText || fileData;
    
    sendBtn.classList.toggle('hidden', !shouldShowSend);
    micBtn.classList.toggle('hidden', hasText);
    voiceModeBtn.classList.toggle('hidden', hasText);
});

saveToDbBtn.addEventListener('click', saveTemporaryChatToDB);

// --- Settings Modal Logic ---
function openSettingsModal() { settingsModal.classList.remove('hidden'); settingsModal.classList.add('flex'); }
function closeSettingsModal() { settingsModal.classList.add('hidden'); settingsModal.classList.remove('flex'); }
settingsMenuItem.addEventListener('click', (e) => { e.preventDefault(); userMenu.classList.add('hidden'); openSettingsModal(); });
closeSettingsBtn.addEventListener('click', closeSettingsModal);
closeSettingsBtnDesktop.addEventListener('click', closeSettingsModal);
settingsModal.addEventListener('click', (e) => { if (e.target === settingsModal) { closeSettingsModal(); } });

function switchSettingsTab(tab) {
    const tabs = document.querySelectorAll('.settings-tab-btn');
    tabs.forEach(t => {
        t.classList.remove('active', 'bg-gray-100', 'text-gray-800', 'font-semibold');
        t.classList.add('text-gray-600', 'hover:bg-gray-100');
    });
    
    const contents = document.querySelectorAll('#general-settings-content, #profile-settings-content, #usage-settings-content');
    contents.forEach(c => c.classList.add('hidden'));

    let titleKey = 'settings'; // Default
    if (tab === 'general') {
        generalTabBtn.classList.add('active', 'bg-gray-100', 'text-gray-800', 'font-semibold');
        generalTabBtn.classList.remove('text-gray-600', 'hover:bg-gray-100');
        generalSettingsContent.classList.remove('hidden');
        titleKey = 'general';
    } else if (tab === 'profile') {
        profileTabBtn.classList.add('active', 'bg-gray-100', 'text-gray-800', 'font-semibold');
        profileTabBtn.classList.remove('text-gray-600', 'hover:bg-gray-100');
        profileSettingsContent.classList.remove('hidden');
        titleKey = 'profile';
    } else if (tab === 'usage') {
        usageTabBtn.classList.add('active', 'bg-gray-100', 'text-gray-800', 'font-semibold');
        usageTabBtn.classList.remove('text-gray-600', 'hover:bg-gray-100');
        usageSettingsContent.classList.remove('hidden');
        titleKey = 'usagePlan';
    }
    
    // Update title using current language
    settingsContentTitle.textContent = translations[currentLang][titleKey] || translations['en'][titleKey];
    settingsContentTitle.setAttribute('data-current-tab', titleKey); // Store for language switching
}

generalTabBtn.addEventListener('click', (e) => { e.preventDefault(); switchSettingsTab('general'); });
profileTabBtn.addEventListener('click', (e) => { e.preventDefault(); switchSettingsTab('profile'); });
usageTabBtn.addEventListener('click', (e) => { e.preventDefault(); switchSettingsTab('usage'); });

// --- Cyber Security Training Logic ---
cyberTrainingBtn.addEventListener('click', () => {
    // Close sidebar on mobile if open
    if (!sidebar.classList.contains('-translate-x-full')) closeSidebar();
    cyberModal.classList.remove('hidden');
    cyberModal.classList.add('flex');
});

closeCyberModalBtn.addEventListener('click', () => {
    cyberModal.classList.add('hidden');
    cyberModal.classList.remove('flex');
});

levelBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const level = btn.getAttribute('data-level');
        startCyberGame(level);
    });
});

endCyberGameBtn.addEventListener('click', endCyberGame);

function startCyberGame(level) {
    // 1. Reset UI
    cyberModal.classList.add('hidden');
    cyberModal.classList.remove('flex');
    startNewChat(); // Clear existing chat
    
    // 2. Set State
    isCyberGameActive = true;
    currentCyberLevel = level;
    cyberGameControls.classList.remove('hidden');
    
    // 3. Define the System Persona based on level
    let personaPrompt = "";
    if (level === 'Basic') {
        personaPrompt = "Act as a naive scammer (e.g., Nigerian Prince or Lottery winner). Use slightly poor grammar, make obvious demands for money or bank details. Do not break character. Keep responses short.";
    } else if (level === 'Intermediate') {
        personaPrompt = "Act as a somewhat convincing scammer posing as 'Amazon Support' or 'Your Bank'. Use urgent language claiming a transaction was authorized. Try to get the user to download 'AnyDesk' or give an OTP. Do not break character. Keep responses short.";
    } else {
        personaPrompt = "Act as a sophisticated Expert Hacker/Social Engineer. Use a Spear Phishing approach. You are posing as a 'Senior IT Administrator' from the user's company (use technical jargon). You need them to run a specific command or visit a specific 'internal' link to patch a security flaw. Be polite, professional, and very convincing. Do not break character. Keep responses short.";
    }
    
    // 4. Send the hidden system prompt to Sofia
    const introMsg = {
        text: `[SYSTEM: SIMULATION STARTED - LEVEL: ${level}]\n${personaPrompt}\n\nStart the conversation now by greeting the victim.`,
        sender: 'user', // We spoof this so the AI replies to it
        mode: 'chat'
    };
    
    // UI Message showing start
    const startMsg = { 
        text: `🏁 **Cyber Security Challenge Started: ${level} Level**\n\nThe AI is now a scammer. Defend yourself!\nWhen you think you've caught them, click **Analyze & End**.`, 
        sender: 'system' 
    };
    addMessage(startMsg);
    
    // Trigger the AI to start speaking
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(introMsg)
    })
    .then(res => res.json())
    .then(data => {
        const aiMsg = { text: data.response, sender: 'ai' };
        addMessage(aiMsg);
        currentChat.push(introMsg); // Add prompt to history for context now
        currentChat.push(aiMsg);
    })
    .catch(err => console.error("Game start error", err));
}

async function endCyberGame() {
    if (!confirm("Are you sure you want to end the simulation and get your report?")) return;

    endCyberGameBtn.textContent = "Analyzing...";
    endCyberGameBtn.disabled = true;

    try {
        // 1. Get and Render the Report
        const response = await fetch('/api/cyber/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: currentChat,
                level: currentCyberLevel
            })
        });

        const report = await response.json();
        renderCyberReport(report);

        // 2. CRITICAL FIX: Automatically reset the AI Persona
        // We send a command to the AI forcing it to confirm it is Sofia again.
        const resetMessage = {
            text: "[SYSTEM COMMAND: The simulation is successfully finished. STOP roleplaying as a scammer immediately. RESET your persona to 'Sofia AI' (helpful assistant). Reply briefly confirming you are back to normal.]",
            sender: 'user', // We send as 'user' to force the model to obey
            mode: 'chat'
        };

        // Add to history (but we won't show this specific prompt in the UI to keep it clean)
        currentChat.push(resetMessage);

        // Call the chat API to process this reset
        const resetResponse = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(resetMessage)
        });

        const resetData = await resetResponse.json();

        // 3. Show Sofia's "Back to Normal" response
        const aiResetMsg = { 
            text: resetData.response, 
            sender: 'ai' 
        };
        addMessage(aiResetMsg);
        currentChat.push(aiResetMsg);
        
        // Save the updated history so the context is permanently fixed
        saveChatSession();

    } catch (error) {
        console.error("Evaluation or Reset failed", error);
        addMessage({ text: "Error generating report. Please check console.", sender: 'system' });
    } finally {
        // Reset State
        isCyberGameActive = false;
        cyberGameControls.classList.add('hidden');
        endCyberGameBtn.textContent = "Analyze & End";
        endCyberGameBtn.disabled = false;
    }
}

function renderCyberReport(report) {
    let colorClass = 'score-low';
    if (report.score >= 80) colorClass = 'score-high';
    else if (report.score >= 50) colorClass = 'score-med';

    const tipsHtml = report.tips ? report.tips.map(tip => `<li class="mb-1">💡 ${tip}</li>`).join('') : '<li>No specific tips.</li>';

    const html = `
        <div class="cyber-report-card">
            <h3 class="text-xl font-bold text-center mb-4 border-b pb-2">🛡️ Security Analysis Report</h3>
            
            <div class="report-score-circle ${colorClass}">
                ${report.score}
            </div>
            
            <div class="text-center font-bold text-lg mb-4">Verdict: ${report.verdict}</div>
            
            <div class="mb-4">
                <h4 class="font-semibold text-gray-700 dark:text-gray-300">Analysis:</h4>
                <p class="text-sm text-gray-600 dark:text-gray-400">${report.analysis}</p>
            </div>
            
            <div>
                <h4 class="font-semibold text-gray-700 dark:text-gray-300">How to Improve:</h4>
                <ul class="text-sm text-gray-600 dark:text-gray-400 list-none pl-0 mt-2">
                    ${tipsHtml}
                </ul>
            </div>
        </div>
    `;

    const messageBubble = document.createElement('div');
    messageBubble.innerHTML = html;
    messageBubble.className = 'message-bubble ai-message w-full'; // Full width for report
    chatContainer.appendChild(messageBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Save this report to chat history logic if needed
    currentChat.push({ text: `**Security Report:** Score ${report.score}/100 - ${report.verdict}`, sender: 'ai' });
}


// --- Language and Theme Logic ---
let currentLang = 'en';
const translations = {
    'en': { 
        settings: 'Settings', 
        general: 'General', 
        profile: 'Profile', 
        theme: 'Theme', 
        light: 'Light', 
        dark: 'Dark', 
        system: 'System', 
        language: 'Language', 
        profileImage: 'Profile Image', 
        upload: 'Upload', 
        username: 'Username', 
        newChat: 'New chat', 
        library: 'Library', 
        chatHistory: 'Chat History', 
        chatHistoryEmpty: 'Your chat history will appear here.', 
        help: 'Help', 
        logOut: 'Log out', 
        welcome: 'What can I help with?', 
        addFiles: 'Add photos & file', 
        askAnything: 'Ask anything', 
        search: 'Search', 
        sofiaTitle: 'Sofia AI',
        uploadCode: 'Upload code',
        usagePlan: 'Usage & Plan',
        upgradePlan: 'Upgrade your plan',
        cyberTraining: 'Cyber Training',
        upgrade: 'Upgrade',
        verify: 'Verify',
        verified: 'Verified',
        delete: 'Delete',
        emailVerification: 'Email Verification',
        logoutAllDevices: 'Log out of all devices',
        deleteAccountLabel: 'Delete account',
        themeLabel: 'Theme',
        emailNotVerifiedMsg: 'Your email is not verified.',
        emailVerifiedMsg: 'Your email has been verified.',
        // --- NEW KEYS FOR USAGE TABLE ---
        feature: 'Feature',
        dailyTextMessages: 'Daily Text Messages',
        voiceCommands: 'Voice-to-Voice Commands',
        readDocs: 'Read Image/PDF/Docs',
        webSearchLimit: 'Web Search',
        saveHistory: 'Save & Search History',
        messages: 'messages',
        unlimited: 'Unlimited',
        perDay: 'per day',
        perMonth: '1 per month (5 pages)',
        yesForever: '✔ Yes, Forever',
        msgsUsedMonth: 'messages used this month',
        freePlanTitle: 'Free Plan',
        premiumPlanTitle: 'Sofia AI Pro',
        upgradeBtnText: 'Upgrade for ₹99/month',
        used: 'Used'
    },
    'hi': { 
        settings: 'सेटिंग्स', 
        general: 'सामान्य', 
        profile: 'प्रोफ़ाइल', 
        theme: 'थीम', 
        light: 'लाइट', 
        dark: 'डार्क', 
        system: 'सिस्टम', 
        language: 'भाषा', 
        profileImage: 'प्रोफ़ाइल छवि', 
        upload: 'अपलोड', 
        username: 'उपयोगकर्ता नाम', 
        newChat: 'नई चैट', 
        library: 'लाइब्रेरी', 
        chatHistory: 'चैट इतिहास', 
        chatHistoryEmpty: 'आपका चैट इतिहास यहाँ दिखाई देगा।', 
        help: 'मदद', 
        logOut: 'लॉग आउट', 
        welcome: 'मैं आपकी क्या मदद कर सकता हूँ?', 
        addFiles: 'तस्वीरें और फ़ाइलें जोड़ें', 
        askAnything: 'कुछ भी पूछें', 
        search: 'खोजें', 
        sofiaTitle: 'सोफिया एआई',
        uploadCode: 'कोड अपलोड करें',
        usagePlan: 'उपयोग और योजना',
        upgradePlan: 'अपना प्लान अपग्रेड करें',
        cyberTraining: 'साइबर प्रशिक्षण',
        upgrade: 'अपग्रेड करें',
        verify: 'सत्यापित करें',
        verified: 'सत्यापित',
        delete: 'हटाएं',
        emailVerification: 'ईमेल सत्यापन',
        logoutAllDevices: 'सभी उपकरणों से लॉग आउट करें',
        deleteAccountLabel: 'खाता हटाएं',
        themeLabel: 'थीम',
        emailNotVerifiedMsg: 'आपका ईमेल सत्यापित नहीं है।',
        emailVerifiedMsg: 'आपका ईमेल सत्यापित हो गया है।',
        // --- NEW KEYS FOR USAGE TABLE ---
        feature: 'सुविधा',
        dailyTextMessages: 'दैनिक टेक्स्ट संदेश',
        voiceCommands: 'वॉयस-टू-वॉयस कमांड',
        readDocs: 'छवि/पीडीएफ/दस्तावेज़ पढ़ें',
        webSearchLimit: 'वेब खोज',
        saveHistory: 'इतिहास सहेजें और खोजें',
        messages: 'संदेश',
        unlimited: 'असीमित',
        perDay: 'प्रति दिन',
        perMonth: '1 प्रति माह (5 पृष्ठ)',
        yesForever: '✔ हाँ, हमेशा के लिए',
        msgsUsedMonth: 'इस महीने उपयोग किए गए संदेश',
        freePlanTitle: 'फ्री प्लान',
        premiumPlanTitle: 'सोफिया एआई प्रो',
        upgradeBtnText: '₹99/माह में अपग्रेड करें',
        used: 'उपयोग किया गया'
    },
    'bn': { 
        settings: 'সেটিংস', 
        general: 'সাধারণ', 
        profile: 'প্রোফাইল', 
        theme: 'থিম', 
        light: 'লাইট', 
        dark: 'ডার্ক', 
        system: 'সিস্টেম', 
        language: 'ভাষা', 
        profileImage: 'প্রোফাইল ছবি', 
        upload: 'আপলোড', 
        username: 'ব্যবহারকারীর নাম', 
        newChat: 'নতুন চ্যাট', 
        library: 'লাইব্রেরি', 
        chatHistory: 'চ্যাট ইতিহাস', 
        chatHistoryEmpty: 'আপনার চ্যাট ইতিহাস এখানে প্রদর্শিত হবে।', 
        help: 'সাহায্য', 
        logOut: 'লগ আউট', 
        welcome: 'আমি আপনাকে কীভাবে সাহায্য করতে পারি?', 
        addFiles: 'ছবি এবং ফাইল যোগ করুন', 
        askAnything: 'যা খুশি জিজ্ঞাসা করুন', 
        search: 'অনুসন্ধান', 
        sofiaTitle: 'সোফিয়া এআই',
        uploadCode: 'কোড আপলোড করুন',
        usagePlan: 'ব্যবহার এবং পরিকল্পনা',
        upgradePlan: 'আপনার পরিকল্পনা আপগ্রেড করুন',
        cyberTraining: 'সাইবার প্রশিক্ষণ',
        upgrade: 'আপগ্রেড করুন',
        verify: 'যাচাই করুন',
        verified: 'যাচাইকৃত',
        delete: 'মুছুন',
        emailVerification: 'ইমেল যাচাইকরণ',
        logoutAllDevices: 'সমস্ত ডিভাইস থেকে লগ আউট করুন',
        deleteAccountLabel: 'অ্যাকাউন্ট মুছুন',
        themeLabel: 'থিম',
        emailNotVerifiedMsg: 'আপনার ইমেল যাচাই করা হয়নি।',
        emailVerifiedMsg: 'আপনার ইমেল যাচাই করা হয়েছে।',
        // --- NEW KEYS FOR USAGE TABLE ---
        feature: 'বৈশিষ্ট্য',
        dailyTextMessages: 'দৈনিক টেক্সট বার্তা',
        voiceCommands: 'ভয়েস-টু-ভয়েস কমান্ড',
        readDocs: 'ছবি/পিডিএফ/ডক্স পড়ুন',
        webSearchLimit: 'ওয়েব অনুসন্ধান',
        saveHistory: 'ইতিহাস সংরক্ষণ ও অনুসন্ধান',
        messages: 'বার্তা',
        unlimited: 'সীমাহীন',
        perDay: 'প্রতিদিন',
        perMonth: 'মাসে ১টি (৫ পৃষ্ঠা)',
        yesForever: '✔ হ্যাঁ, চিরকাল',
        msgsUsedMonth: 'এই মাসে ব্যবহৃত বার্তা',
        freePlanTitle: 'ফ্রি প্ল্যান',
        premiumPlanTitle: 'সোফিয়া এআই প্রো',
        upgradeBtnText: '৯৯ টাকা/মাসে আপগ্রেড করুন',
        used: 'ব্যবহৃত'
    }
};

const languages = { "en": "English", "hi": "हिंदी", "bn": "বাংলা" };

function applyLanguage(lang) {
    currentLang = lang;
    document.querySelectorAll('[data-lang]').forEach(el => {
        const key = el.getAttribute('data-lang');
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
     document.querySelectorAll('[data-lang-placeholder]').forEach(el => {
        const key = el.getAttribute('data-lang-placeholder');
        if (translations[lang] && translations[lang][key]) {
            el.placeholder = translations[lang][key];
        }
    });

    // Handle settings title specifically since it changes with tabs
    const currentTab = settingsContentTitle.getAttribute('data-current-tab') || 'general';
    settingsContentTitle.textContent = translations[lang][currentTab] || translations['en'][currentTab];

    // --- MANUAL UPDATES FOR ELEMENTS MISSING data-lang TAGS ---
    
    // 1. Sidebar & Menu Buttons
    const uploadCodeSpan = document.querySelector('#upload-code-btn span');
    if (uploadCodeSpan) uploadCodeSpan.textContent = translations[lang]['uploadCode'];

    const usageTabSpan = document.querySelector('#usage-tab-btn span');
    if (usageTabSpan) usageTabSpan.textContent = translations[lang]['usagePlan'];

    const upgradeSidebarSpan = document.querySelector('#upgrade-plan-sidebar-btn span');
    if (upgradeSidebarSpan) upgradeSidebarSpan.textContent = translations[lang]['upgradePlan'];

    const cyberTrainingSpan = document.querySelector('#cyber-training-btn span');
    if (cyberTrainingSpan) cyberTrainingSpan.textContent = translations[lang]['cyberTraining'];
    
    // 2. Settings - General Tab (Theme Buttons & Label)
    const themeLabel = document.querySelector('#general-settings-content label');
    if (themeLabel) themeLabel.textContent = translations[lang]['themeLabel'];

    const lightSpan = document.querySelector('#theme-light span');
    if (lightSpan) lightSpan.textContent = translations[lang]['light'];

    const darkSpan = document.querySelector('#theme-dark span');
    if (darkSpan) darkSpan.textContent = translations[lang]['dark'];

    const systemSpan = document.querySelector('#theme-system span');
    if (systemSpan) systemSpan.textContent = translations[lang]['system'];

    // 2.5 Settings Tabs - General & Profile
    const generalTabSpan = document.querySelector('#general-tab-btn span');
    if (generalTabSpan) generalTabSpan.textContent = translations[lang]['general'];

    const profileTabSpan = document.querySelector('#profile-tab-btn span');
    if (profileTabSpan) profileTabSpan.textContent = translations[lang]['profile'];

    // 3. Settings - Usage & Plan Table (The Fix for your Screenshot)
    const planTable = document.querySelector('.plan-table');
    if (planTable) {
        // Table Headers
        const headerRow = planTable.querySelector('.flex.justify-between.items-end');
        if (headerRow) {
            headerRow.children[0].textContent = translations[lang]['feature'];
            headerRow.children[1].textContent = translations[lang]['freePlanTitle'];
            // For Pro plan, we keep the price part hardcoded or simple for now, mostly updating title
            headerRow.children[2].innerHTML = `${translations[lang]['premiumPlanTitle']} <span class="text-sm font-normal">(₹99/month)</span>`;
        }

        // Table Rows (targeting by structure since there are no IDs)
        const rows = planTable.querySelectorAll('.bg-gray-50 > div, .dark\\:bg-gray-800 > div'); // Handles bg-gray-50 container
        
        if (rows.length >= 5) {
            // Row 1: Daily Text Messages
            rows[0].children[0].textContent = translations[lang]['dailyTextMessages'];
            rows[0].children[1].textContent = `15 ${translations[lang]['messages']}`;
            rows[0].children[2].textContent = translations[lang]['unlimited'];

            // Row 2: Voice Commands
            rows[1].children[0].textContent = translations[lang]['voiceCommands'];
            rows[1].children[1].textContent = `5 ${translations[lang]['perDay']}`;
            rows[1].children[2].textContent = translations[lang]['unlimited'];

            // Row 3: Read Docs
            rows[2].children[0].textContent = translations[lang]['readDocs'];
            rows[2].children[1].textContent = translations[lang]['perMonth'];
            rows[2].children[2].textContent = translations[lang]['unlimited'];

            // Row 4: Web Search
            rows[3].children[0].textContent = translations[lang]['webSearchLimit'];
            rows[3].children[1].textContent = `1 ${translations[lang]['perDay']}`;
            rows[3].children[2].textContent = `${translations[lang]['unlimited']}*`;

            // Row 5: Save History
            rows[4].children[0].textContent = translations[lang]['saveHistory'];
            rows[4].children[1].textContent = translations[lang]['yesForever'];
            rows[4].children[2].textContent = translations[lang]['yesForever'];
        }
    }

    // Usage Section Titles and Buttons
    if (planTitle) planTitle.textContent = translations[lang]['freePlanTitle'];
    if (razorpayBtn) razorpayBtn.textContent = translations[lang]['upgradeBtnText'];

    // Update dynamic usage text immediately
    updateUsageUI();


    // 4. Settings - Profile Tab Labels
    const profileContent = document.getElementById('profile-settings-content');
    if (profileContent) {
        // Find specific labels by hierarchy
        const emailVerLabel = profileContent.querySelector('div.space-y-6 > div:nth-child(3) > div > p.font-medium');
        if (emailVerLabel) emailVerLabel.textContent = translations[lang]['emailVerification'];

        const logoutLabel = profileContent.querySelector('div.space-y-6 > div:nth-child(4) > p');
        if (logoutLabel) logoutLabel.textContent = translations[lang]['logoutAllDevices'];

        const deleteAccountLabel = profileContent.querySelector('div.space-y-6 > div:nth-child(5) > p');
        if (deleteAccountLabel) deleteAccountLabel.textContent = translations[lang]['deleteAccountLabel'];

        // Dynamic Status Text for Email
        if (emailVerificationStatusText) {
             // If verify btn is disabled, it means email is already verified
            if (verifyEmailBtn && verifyEmailBtn.disabled) {
                emailVerificationStatusText.textContent = translations[lang]['emailVerifiedMsg'];
            } else {
                emailVerificationStatusText.textContent = translations[lang]['emailNotVerifiedMsg'];
            }
        }
    }

    // 5. Update Verify/Delete buttons manually if needed
    if (verifyEmailBtn) {
        // preserve disabled state logic text slightly
        if (!verifyEmailBtn.disabled) verifyEmailBtn.textContent = translations[lang]['verify'];
        else if (verifyEmailBtn.textContent !== 'Sending...') verifyEmailBtn.textContent = translations[lang]['verified'];
    }
    if (deleteAccountBtn) deleteAccountBtn.textContent = translations[lang]['delete'];
    if (logoutBtn) logoutBtn.textContent = translations[lang]['logOut'];

    document.documentElement.lang = lang;
}

function populateLanguages() {
    languageSelect.innerHTML = '';
    for (const [code, name] of Object.entries(languages)) {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = name;
        if (code === currentLang) {
            option.selected = true;
        }
        languageSelect.appendChild(option);
    }
}

languageSelect.addEventListener('change', (e) => {
    const newLang = e.target.value;
    applyLanguage(newLang);
});

function applyTheme(theme) {
    localStorage.setItem('theme', theme);
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else if (theme === 'light') {
        document.documentElement.classList.remove('dark');
    } else { // system
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }
}

themeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        themeBtns.forEach(b => b.classList.remove('border-indigo-600', 'border-2', 'ring-2', 'ring-indigo-200'));
        btn.classList.add('border-indigo-600', 'border-2', 'ring-2', 'ring-indigo-200');
        const theme = btn.id.replace('theme-', '');
        applyTheme(theme);
    });
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
    const savedTheme = localStorage.getItem('theme');
    if(savedTheme === 'system') {
         applyTheme('system');
    }
});

// --- Core Functions ---
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    addMenu.classList.add('hidden');
    const reader = new FileReader();
    reader.onload = function(e) {
        fileData = e.target.result.split(',')[1];
        fileType = file.type;
        fileInfoForDisplay = { name: file.name, type: file.type, dataUrl: e.target.result };
        showFilePreview(file);
        sendBtn.classList.remove('hidden');
    };
    reader.onerror = function(error) {
        console.error("Error reading file:", error);
        addMessage({ text: "Sorry, there was an error reading your file.", sender: 'system'});
    };
    reader.readAsDataURL(file);
}

function showFilePreview(file) {
    filePreviewContainer.innerHTML = '';
    const previewItem = document.createElement('div');
    previewItem.className = 'preview-item';
    
    if (file.type.startsWith('image/')) {
         previewItem.classList.add('image-preview');
         previewItem.innerHTML = `<img src="${fileInfoForDisplay.dataUrl}" alt="${file.name}"><button class="remove-preview-btn" onclick="removeFile()">&times;</button>`;
    } else {
         previewItem.classList.add('doc-preview');
         previewItem.innerHTML = `<div class="file-icon"><svg class="h-6 w-6 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg></div><span class="file-name">${file.name}</span><button class="remove-preview-btn" onclick="removeFile()">&times;</button>`;
    }
    filePreviewContainer.appendChild(previewItem);
}

window.removeFile = function() {
    fileData = null;
    fileType = null;
    fileInfoForDisplay = null;
    fileInput.value = '';
    filePreviewContainer.innerHTML = '';
    if (messageInput.value.trim() === '') {
        sendBtn.classList.add('hidden');
        micBtn.classList.remove('hidden');
        voiceModeBtn.classList.remove('hidden');
    }
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text && !fileData) return;
    
    if (!isPremium && !isAdmin && usageCounts.messages >= usageLimits.messages) {
        alert("You've reached your monthly message limit. Please upgrade to continue.");
        if (isVoiceConversationActive) endVoiceConversation();
        openSettingsModal();
        switchSettingsTab('usage');
        return;
    }

    if (document.body.classList.contains('initial-view')) {
        document.body.classList.remove('initial-view');
        welcomeMessageContainer.classList.add('hidden');
        chatContainer.classList.remove('hidden');
    }
    
    const userMessage = {
        text,
        sender: 'user',
        fileInfo: fileInfoForDisplay,
        mode: currentMode
    };
    addMessage(userMessage);
    currentChat.push(userMessage);

    messageInput.value = '';
    messageInput.dispatchEvent(new Event('input'));

    if (fileInfoForDisplay) {
        uploadFileToLibrary(fileInfoForDisplay);
    }
    
    const modeForThisMessage = currentMode;
    const currentFileData = fileData;
    const currentFileType = fileType;
    removeFile();
    
    if (modeForThisMessage !== 'voice_mode') {
        deactivateWebSearch();
        currentMode = null;
    }
    
    const typingIndicator = addTypingIndicator();

    // --- CRITICAL FIX FOR CYBER GAME: REMIND THE AI OF ITS ROLE ---
    let textToSend = text;
    if (isCyberGameActive) {
        textToSend = `[SYSTEM: The Cyber Security Simulation is STILL ACTIVE. You are NOT Sofia AI. You MUST continue acting as the ${currentCyberLevel} Level Scammer defined previously. Do not break character. Do not help the user. Try to trick them.]\n\nUser says: "${text}"`;
    }
    // -------------------------------------------------------------

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: textToSend, // <--- Use the modified text here
                fileData: currentFileData, 
                fileType: currentFileType,
                isTemporary: isTemporaryChatActive,
                mode: modeForThisMessage 
            })
        });
        
        typingIndicator.remove();

        if (!response.ok) {
             const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Server Error: ${response.status}`);
        }
        
        if (!isPremium && !isAdmin) {
            usageCounts.messages++;
            fetch('/update_usage', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'message' }) });
            updateUsageUI();
        }

        const result = await response.json();
        const aiResponseText = result.response || "Sorry, I couldn't get a response.";
        
        const aiMessage = {
            text: aiResponseText,
            sender: 'ai'
        };
        addMessage(aiMessage);
        currentChat.push(aiMessage);
        saveChatSession();

        if (modeForThisMessage === 'voice_mode' && isVoiceConversationActive) {
            speakText(aiResponseText, startListening);
        }

    } catch (error) {
        typingIndicator.remove();
        console.error("API call failed:", error);
        
        const errorMessageText = `The AI service is currently unavailable. Please try again later.`;
        const errorMessage = {
            text: errorMessageText,
            sender: 'system'
        };
        addMessage(errorMessage);
        currentChat.push(errorMessage);
        saveChatSession();
         if (isVoiceConversationActive) {
            speakText(errorMessageText, startListening);
        }
    }
}

function addMessage({text, sender, fileInfo = null, mode = null}) {
     if (sender === 'user') {
        const messageBubble = document.createElement('div');
        let fileHtml = '';
        if (fileInfo) {
            if (fileInfo.type.startsWith('image/')) {
                 fileHtml = `<img src="${fileInfoForDisplay.dataUrl}" alt="User upload" class="rounded-lg mb-2 max-w-xs">`;
            } else {
                fileHtml = `<div class="flex items-center bg-blue-100 rounded-lg p-2 mb-2"><svg class="h-6 w-6 text-blue-500 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg><span class="text-sm text-blue-800">${fileInfo.name}</span></div>`;
            }
        }
        
        let modeHtml = '';
        if (mode === 'web_search' || mode === 'mic_input' || mode === 'voice_mode') {
            let modeText = 'Google Search';
            if (mode === 'mic_input') modeText = 'Voice Input';
            if (mode === 'voice_mode') modeText = 'Voice Mode';
            
            modeHtml = `<div class="mt-2 flex items-center gap-1.5"><div class="flex-shrink-0 w-5 h-5 rounded-full bg-green-500 text-white flex items-center justify-center"><svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg></div><span class="text-xs text-white/80">${modeText}</span></div>`;
        }

        messageBubble.innerHTML = fileHtml + `<div>${text}</div>` + modeHtml;
        messageBubble.className = 'message-bubble user-message ml-auto';
        chatContainer.appendChild(messageBubble);

    } else if (sender === 'ai') {
        const aiMessageContainer = document.createElement('div');
        aiMessageContainer.className = 'ai-message-container';
        const avatar = `<div class="ai-avatar"><span class="text-2xl">🌎</span></div>`;
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble ai-message';
        
        let contentHtml = markdownConverter.makeHtml(text);
        
        const actionsHtml = `
            <div class="message-actions">
                <button class="action-btn copy-btn" title="Copy text">
                    <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM5 11a1 1 0 100 2h4a1 1 0 100-2H5z"/></svg>
                </button>
                <button class="action-btn like-btn" title="Good response">
                   <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.821 2.311l-1.055 1.636a1 1 0 00-1.423 .23z"/></svg>
                </button>
                <button class="action-btn dislike-btn" title="Bad response">
                    <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.106-1.79l-.05-.025A4 4 0 0011.057 2H5.642a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.821-2.311l1.055-1.636a1 1 0 001.423 .23z"/></svg>
                </button>
                <button class="action-btn share-btn" title="Share">
                    <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M15 8a3 3 0 10-2.977-2.63l-4.94 2.47a3 3 0 100 4.319l4.94 2.47a3 3 0 10.895-1.789l-4.94-2.47a3.027 3.027 0 000-.74l4.94-2.47C13.456 7.68 14.19 8 15 8z" /></svg>
                </button>
                <button class="action-btn speak-btn" title="Speak">
                    <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clip-rule="evenodd" /></svg>
                </button>
            </div>
        `;

        messageBubble.innerHTML = contentHtml + actionsHtml;
        
        aiMessageContainer.innerHTML = avatar;
        aiMessageContainer.appendChild(messageBubble);
        chatContainer.appendChild(aiMessageContainer);

        // Code Block Highlight
        const codeBlocks = messageBubble.querySelectorAll('pre');
        codeBlocks.forEach((pre) => {
            const copyButton = document.createElement('button');
            copyButton.className = 'code-copy-btn';
            copyButton.textContent = 'Copy Code';

            copyButton.addEventListener('click', () => {
                const code = pre.querySelector('code');
                if (code) {
                    navigator.clipboard.writeText(code.innerText);
                    copyButton.textContent = 'Copied!';
                    setTimeout(() => {
                        copyButton.textContent = 'Copy Code';
                    }, 2000);
                }
            });

            pre.appendChild(copyButton);
        });

        if (window.Prism) {
            Prism.highlightAll();
        }

        messageBubble.querySelector('.copy-btn').addEventListener('click', (e) => {
            const button = e.currentTarget;
            const originalContent = button.innerHTML;
            navigator.clipboard.writeText(text).then(() => {
                button.innerHTML = '<span class="text-xs">Copied!</span>';
                setTimeout(() => {
                    button.innerHTML = originalContent;
                }, 2000);
            });
        });

        messageBubble.querySelector('.like-btn').addEventListener('click', (e) => {
            e.currentTarget.classList.toggle('text-blue-600');
            messageBubble.querySelector('.dislike-btn').classList.remove('text-red-600');
        });

        messageBubble.querySelector('.dislike-btn').addEventListener('click', (e) => {
            e.currentTarget.classList.toggle('text-red-600');
            messageBubble.querySelector('.like-btn').classList.remove('text-blue-600');
        });

        messageBubble.querySelector('.share-btn').addEventListener('click', async () => {
            const button = messageBubble.querySelector('.share-btn');
            const originalContent = button.innerHTML;
            if (navigator.share) {
                try {
                    await navigator.share({ title: 'Sofia AI Assistance', text: text });
                } catch (error) {
                    console.error('Error sharing:', error);
                    navigator.clipboard.writeText(text);
                    button.innerHTML = '<span class="text-xs">Copied!</span>';
                    setTimeout(() => { button.innerHTML = originalContent; }, 2000);
                }
            } else {
                navigator.clipboard.writeText(text);
                button.innerHTML = '<span class="text-xs">Copied!</span>';
                setTimeout(() => { button.innerHTML = originalContent; }, 2000);
            }
        });

        messageBubble.querySelector('.speak-btn').addEventListener('click', () => {
            speakText(text, null);
        });

    } else if (sender === 'system') {
        const messageBubble = document.createElement('div');
        messageBubble.textContent = text;
        messageBubble.className = 'message-bubble system-message';
        chatContainer.appendChild(messageBubble);
    }
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addTypingIndicator() {
    const typingIndicatorContainer = document.createElement('div');
    typingIndicatorContainer.className = 'ai-message-container typing-indicator items-center';
    const animatedAvatarHTML = `
        <div class="ai-avatar-animated">
            <div class="orbiting-circle"></div>
            <span class="globe text-2xl">🌎</span>
        </div>
        <span class="text-gray-600 font-medium ml-2">Just a sec...</span>
    `;
    typingIndicatorContainer.innerHTML = animatedAvatarHTML;
    chatContainer.appendChild(typingIndicatorContainer);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return typingIndicatorContainer;
}

// --- Feature Toggles ---
function activateWebSearch() {
     if (!isPremium && !isAdmin && usageCounts.webSearches >= usageLimits.webSearches) {
        alert("You've reached your daily web search limit. Please upgrade for unlimited searches.");
        openSettingsModal();
        switchSettingsTab('usage');
        return;
    }
    currentMode = 'web_search';
    const indicator = document.createElement('div');
    indicator.className = 'mode-indicator ml-2';
    indicator.innerHTML = `
        <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" viewBox="0 0 48 48"><path fill="#4CAF50" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"></path><path fill="#FFC107" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"></path><path fill="#FF3D00" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"></path><path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.574l6.19,5.238C39.902,35.636,44,29.598,44,24C44,22.659,43.862,21.35,43.611,20.083z"></path></svg>
        <span>Web Search Active</span>
        <button id="close-search-mode-btn" class="ml-2 p-1 rounded-full hover:bg-indigo-200 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 text-indigo-800" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </button>
    `;
    modeIndicatorContainer.innerHTML = '';
    modeIndicatorContainer.appendChild(indicator);
    document.getElementById('close-search-mode-btn').addEventListener('click', deactivateWebSearch);
    webSearchToggleBtn.classList.add('text-blue-600');
    messageInput.focus();
}

function deactivateWebSearch() {
    currentMode = null;
    modeIndicatorContainer.innerHTML = '';
    webSearchToggleBtn.classList.remove('text-blue-600');
}

webSearchToggleBtn.addEventListener('click', () => {
    if (currentMode === 'web_search') {
        deactivateWebSearch();
    } else {
        activateWebSearch();
    }
});

// --- Voice Functions ---
function setVoiceUIState(state) {
    if (state === 'listening') {
        voiceStatusText.textContent = "Listening...";
        voiceVisualizer.classList.add('listening');
        voiceVisualizer.classList.remove('bg-gray-500');
        voiceVisualizer.innerHTML = `<svg class="h-10 w-10 text-white" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>`;
    } else if (state === 'thinking') {
        voiceStatusText.textContent = "Thinking...";
        voiceVisualizer.classList.remove('listening');
        voiceVisualizer.classList.add('bg-gray-500');
        voiceVisualizer.innerHTML = `<div class="w-8 h-8 border-4 border-white border-t-transparent rounded-full animate-spin"></div>`;
    } else if (state === 'speaking') {
        voiceStatusText.textContent = "Sofia is speaking...";
        voiceVisualizer.classList.remove('listening');
        voiceVisualizer.classList.remove('bg-gray-500');
    }
}

function speakText(text, onEndCallback) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const cleanedText = text.replace(/[*_`#]/g, '');
        const utterance = new SpeechSynthesisUtterance(cleanedText);
        utterance.lang = currentLang;
        utterance.onstart = () => {
            if (isVoiceConversationActive) setVoiceUIState('speaking');
        };
        utterance.onend = () => { if(onEndCallback) onEndCallback(); };
        utterance.onerror = (event) => {
            console.error('SpeechSynthesisUtterance.onerror', event);
             if (isVoiceConversationActive) {
                addMessage({ text: 'Sorry, I had trouble speaking. Please try again.', sender: 'system' });
            }
            if(onEndCallback) onEndCallback();
        };
        window.speechSynthesis.speak(utterance);
    } else {
         addMessage({ text: 'Sorry, my voice response is not available on your browser.', sender: 'system' });
        if (onEndCallback) onEndCallback();
    }
}

function startListening() {
    if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        addMessage({ text: 'Speech recognition is not supported in this browser.', sender: 'system' });
        endVoiceConversation();
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = currentLang;

    recognition.onstart = () => {
        if (isVoiceConversationActive) {
            setVoiceUIState('listening');
        } else {
            micBtn.classList.add('text-red-500');
        }
    };

    recognition.onend = () => {
        micBtn.classList.remove('text-red-500');
        // The user stopped talking. If we have a final transcript, send it.
        const finalTranscript = voiceInterimTranscript.textContent.trim();
         if (isVoiceConversationActive && finalTranscript) {
            messageInput.value = finalTranscript;
            sendMessage();
            setVoiceUIState('thinking');
        } else if (isVoiceConversationActive) {
            // If no speech was detected, just start listening again
            startListening();
        }
    };
    
    recognition.onresult = (event) => {
         let interim_transcript = '';
         let final_transcript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                final_transcript += event.results[i][0].transcript;
            } else {
                interim_transcript += event.results[i][0].transcript;
            }
        }
        voiceInterimTranscript.textContent = final_transcript || interim_transcript;
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error !== 'aborted' && isVoiceConversationActive) {
            addMessage({ text: `Speech recognition error: ${event.error}`, sender: 'system' });
        }
        if (isVoiceConversationActive) {
            endVoiceConversation();
        }
    };
    
    try {
         recognition.start();
    } catch(e) {
        console.error("Recognition start error", e);
        if (isVoiceConversationActive) {
            endVoiceConversation();
        }
    }
}

micBtn.addEventListener('click', () => {
    currentMode = 'mic_input';
    isVoiceConversationActive = false;
    startListening();
});

function startVoiceConversation() {
    if ('speechSynthesis' in window && window.speechSynthesis.getVoices().length === 0) {
         window.speechSynthesis.speak(new SpeechSynthesisUtterance(''));
    }
    window.speechSynthesis.cancel();
    
    currentMode = 'voice_mode';
    isVoiceConversationActive = true;
    voiceOverlay.classList.remove('hidden');
    voiceOverlay.classList.add('flex');
    voiceInterimTranscript.textContent = '';
    startListening();
}

function endVoiceConversation() {
    isVoiceConversationActive = false;
    voiceOverlay.classList.add('hidden');
    if (recognition) {
        recognition.abort();
    }
    window.speechSynthesis.cancel();
    currentMode = null;
}

voiceModeBtn.addEventListener('click', startVoiceConversation);
endVoiceBtn.addEventListener('click', endVoiceConversation);


// --- Chat History Functions ---
async function saveChatSession() {
    if (isTemporaryChatActive || currentChat.length === 0) {
        return;
    }

    try {
        const response = await fetch('/api/chats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: currentChatId,
                title: currentChat.find(m => m.sender === 'user')?.text.substring(0, 40) || 'Untitled Chat',
                messages: currentChat
            })
        });
        if (response.ok) {
            const savedChat = await response.json();
            if (!currentChatId) {
                currentChatId = savedChat.id;
            }
            // Refresh history from DB to ensure consistency
            loadChatsFromDB();
        } else {
            console.error('Failed to save chat session to DB');
        }
    } catch (error) {
        console.error('Error saving chat session:', error);
    }
}

async function saveTemporaryChatToDB() {
    if (currentChat.length === 0) {
        alert("Cannot save an empty chat.");
        return;
    }

    saveToDbBtn.textContent = 'Saving...';
    saveToDbBtn.disabled = true;

    try {
        const response = await fetch('/api/chats', { // Changed endpoint
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: currentChat })
        });

        if (!response.ok) {
            throw new Error('Failed to save chat to the database.');
        }

        const savedChat = await response.json();

        isTemporaryChatActive = false;
        
        currentChatId = savedChat.id; // The server should return the new ID
        chatHistory.unshift({ id: savedChat.id, title: savedChat.title, messages: [...currentChat] });
        renderChatHistorySidebar();

        saveToDbBtn.textContent = 'Saved!';
        setTimeout(() => {
            tempChatBanner.classList.add('hidden');
        }, 1500);

    } catch (error) {
        console.error("Error saving temporary chat:", error);
        alert("Could not save the chat. Please try again.");
        saveToDbBtn.textContent = 'Save Chat';
        saveToDbBtn.disabled = false;
    }
}

async function loadChatsFromDB() {
    try {
        const response = await fetch('/api/chats');
        if (response.ok) {
            chatHistory = await response.json();
            renderChatHistorySidebar();
        } else {
            console.error('Failed to load chats from DB');
            chatHistoryContainer.innerHTML = `<div class="p-2 text-sm text-red-500">Could not load history.</div>`;
        }
    } catch (error) {
        console.error('Error loading chats:', error);
        chatHistoryContainer.innerHTML = `<div class="p-2 text-sm text-red-500">Error loading history.</div>`;
    }
}


function renderChatHistorySidebar() {
    chatHistoryContainer.innerHTML = '';
    if (chatHistory.length === 0) {
         chatHistoryContainer.innerHTML = `<div class="p-2 text-sm text-gray-600 dark:text-gray-400" data-lang="chatHistoryEmpty">Your chat history will appear here.</div>`;
         applyLanguage(currentLang);
         return;
    }

    // Sort history by the most recent (assuming IDs are timestamp-based or server sends them sorted)
    const sortedHistory = chatHistory.sort((a, b) => b.id - a.id);

    sortedHistory.forEach(chat => {
        const item = document.createElement('div');
        item.className = 'chat-history-item group';
        if (chat.id === currentChatId) {
            item.classList.add('active');
        }
        item.dataset.chatId = chat.id;

        const titleSpan = document.createElement('span');
        titleSpan.className = 'chat-title';
        titleSpan.textContent = chat.title;
        titleSpan.addEventListener('click', () => loadChat(chat.id));
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'flex items-center opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity';
        
        actionsDiv.innerHTML = `
            <button class="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600" title="Rename">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L16.732 3.732z" /></svg>
            </button>
            <button class="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600" title="Delete">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
        `;

        actionsDiv.querySelector('button[title="Rename"]').addEventListener('click', (e) => {
            e.stopPropagation();
            renameChat(chat.id);
        });
        actionsDiv.querySelector('button[title="Delete"]').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteChat(chat.id);
        });

        item.appendChild(titleSpan);
        item.appendChild(actionsDiv);
        chatHistoryContainer.appendChild(item);
    });
}

async function renameChat(chatId) {
    const newTitle = prompt("Enter new chat title:");
    if (newTitle && newTitle.trim() !== '') {
        try {
            const response = await fetch(`/api/chats/${chatId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle.trim() })
            });
            if(response.ok) {
                loadChatsFromDB(); // Refresh from DB
            } else {
                alert('Failed to rename chat.');
            }
        } catch(error) {
            console.error('Error renaming chat:', error);
            alert('An error occurred while renaming.');
        }
    }
}

async function deleteChat(chatId) {
    if (confirm('Are you sure you want to delete this chat? This will be permanent.')) {
         try {
            const response = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' });
            if(response.ok) {
                if (currentChatId === chatId) {
                    startNewChat();
                }
                loadChatsFromDB(); // Refresh from DB
            } else {
                alert('Failed to delete chat.');
            }
        } catch(error) {
             console.error('Error deleting chat:', error);
             alert('An error occurred while deleting.');
        }
    }
}

searchHistoryInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    const items = chatHistoryContainer.querySelectorAll('.chat-history-item');
    items.forEach(item => {
        const title = item.querySelector('.chat-title').textContent.toLowerCase();
        if (title.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
});

function loadChat(chatId) {
    isTemporaryChatActive = false;
    tempChatBanner.classList.add('hidden');
    
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;
    
    currentChatId = chatId;
    currentChat = [...chat.messages];

    chatContainer.innerHTML = '';
    welcomeMessageContainer.classList.add('hidden');
    chatContainer.classList.remove('hidden');
    document.body.classList.remove('initial-view');

    currentChat.forEach(message => addMessage(message));
    renderChatHistorySidebar();
}

function startNewChat() {
    if (!isTemporaryChatActive) {
        tempChatBanner.classList.add('hidden');
    }

    currentChat = [];
    currentChatId = null;
    
    chatContainer.innerHTML = '';
    welcomeMessageContainer.classList.remove('hidden');
    chatContainer.classList.add('hidden');
    document.body.classList.add('initial-view');
    deactivateWebSearch();
    currentMode = null;
    removeFile();
    messageInput.value = '';
    renderChatHistorySidebar();
}

// --- Library Functions ---
function dataURLtoBlob(dataurl) {
    var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
        bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
    while(n--){
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], {type:mime});
}

async function uploadFileToLibrary(fileInfo) {
    console.log("Auto-saving file to library:", fileInfo.name);
    try {
        const blob = dataURLtoBlob(fileInfo.dataUrl);
        const formData = new FormData();
        formData.append('file', blob, fileInfo.name);
        
        const response = await fetch('/library/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Auto-save to library failed');
        }
        console.log(`Successfully auto-saved ${fileInfo.name} to library.`);
        if (!libraryModal.classList.contains('hidden')) {
            fetchLibraryFiles();
        }
    } catch(error) {
        console.error('Error auto-saving to library:', error);
    }
}

function openLibraryModal() {
    libraryModal.classList.remove('hidden');
    libraryModal.classList.add('flex');
    fetchLibraryFiles();
}

function closeLibraryModal() {
    libraryModal.classList.add('hidden');
    libraryModal.classList.remove('flex');
}

async function fetchLibraryFiles() {
    libraryGrid.innerHTML = '<p class="text-gray-500">Loading library...</p>';
    libraryEmptyMsg.classList.add('hidden');

    try {
        const response = await fetch('/library/files');
        if (!response.ok) {
            throw new Error('Failed to fetch library files.');
        }
        const files = await response.json();
        renderLibraryFiles(files);
    } catch (error) {
        console.error('Error fetching library files:', error);
        libraryGrid.innerHTML = '<p class="text-red-500">Could not load library. Please try again.</p>';
    }
}

function renderLibraryFiles(files) {
    libraryGrid.innerHTML = '';
    if (!files || files.length === 0) {
        libraryEmptyMsg.classList.remove('hidden');
        libraryGrid.appendChild(libraryEmptyMsg);
        return;
    }

    libraryEmptyMsg.classList.add('hidden');

    files.forEach(file => {
        const item = document.createElement('div');
        item.className = 'relative group border rounded-lg p-2 flex flex-col items-center text-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700';
        item.addEventListener('click', () => selectLibraryFile(file));

        let previewHtml = '';
        if (file.fileCategory === 'image') {
            previewHtml = `<img src="data:${file.fileType};base64,${file.fileData}" alt="${file.fileName}" class="w-20 h-20 object-cover rounded-md mb-2">`;
        } else if (file.fileCategory === 'document') {
            previewHtml = `<svg class="w-20 h-20 mb-2 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        } else if (file.fileCategory === 'code') {
            previewHtml = `<svg class="w-20 h-20 mb-2 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l-4 4-4-4M6 16l-4-4 4-4" /></svg>`;
        } else {
            previewHtml = `<svg class="w-20 h-20 mb-2 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>`;
        }
        
        item.innerHTML = `
            ${previewHtml}
            <p class="text-xs break-all w-full">${file.fileName}</p>
            <button class="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100">&times;</button>
        `;
        
        item.querySelector('button').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteLibraryFile(file._id);
        });

        libraryGrid.appendChild(item);
    });
}

async function deleteLibraryFile(fileId) {
    if (!confirm("Are you sure you want to delete this file from your library?")) return;
    
    try {
         const response = await fetch(`/library/files/${fileId}`, { method: 'DELETE' });
         if (!response.ok) {
             throw new Error('Deletion failed');
         }
         fetchLibraryFiles();
    } catch (error) {
        console.error('Error deleting library file:', error);
        alert('Could not delete file.');
    }
}

function selectLibraryFile(file) {
    fileData = file.fileData;
    fileType = file.fileType;
    fileInfoForDisplay = { name: file.fileName, type: file.fileType, dataUrl: `data:${file.fileType};base64,${file.fileData}` };
    
    showFilePreview({name: file.fileName, type: file.fileType});
    sendBtn.classList.remove('hidden');
    closeLibraryModal();
}

libraryBtn.addEventListener('click', openLibraryModal);
closeLibraryBtn.addEventListener('click', closeLibraryModal);


// --- Plan, Usage & Payment Functions ---
upgradePlanSidebarBtn.addEventListener('click', (e) => {
    e.preventDefault();
    userMenu.classList.add('hidden');
    openSettingsModal();
    switchSettingsTab('usage');
});

function updateUsageUI() {
     if (isAdmin) {
        sidebarUserPlan.textContent = "Admin";
        upgradePlanSidebarBtn.classList.add('hidden');
        usageTabBtn.classList.add('hidden');
        sidebarUsageDisplay.classList.add('hidden');
    } else if (isPremium) {
        sidebarUserPlan.textContent = "Premium";
        usagePlanSection.classList.add('hidden');
        upgradeSection.classList.add('hidden');
        premiumSection.classList.remove('hidden');
        upgradePlanSidebarBtn.classList.add('hidden');
        sidebarUsageDisplay.classList.add('hidden');
    } else {
        sidebarUserPlan.textContent = "Free";
        upgradePlanSidebarBtn.classList.remove('hidden');
        usageTabBtn.classList.remove('hidden');
        sidebarUsageDisplay.classList.remove('hidden');
        
        const percentage = Math.min((usageCounts.messages / usageLimits.messages) * 100, 100);
        
        // --- TRANSLATION FIX HERE ---
        const usedWord = translations[currentLang]['used'] || 'Used';
        const msgsUsedWord = translations[currentLang]['msgsUsedMonth'] || 'messages used this month';
        
        sidebarUsageDisplay.textContent = `${usageCounts.messages} / ${usageLimits.messages} ${usedWord}`;
        usageCounter.textContent = `${usageCounts.messages} / ${usageLimits.messages} ${msgsUsedWord}`;
        // ----------------------------
        
        usageProgressBar.style.width = `${percentage}%`;
    }
}

razorpayBtn.addEventListener('click', () => {
     const options = {
        "key": "rzp_test_YourKeyHere", // IMPORTANT: Replace with your Razorpay Test Key ID
        "amount": "9900", // Amount in the smallest currency unit (99 * 100 = 9900 paise)
        "currency": "INR",
        "name": "Sofia AI",
        "description": "Premium Plan - Monthly",
        "image": "https://placehold.co/100x100/3b82f6/FFFFFF?text=S",
        // "order_id": "order_xyz", // IMPORTANT: This should be generated from your backend for security
        "handler": function (response){
            alert("Payment Successful! Payment ID: " + response.razorpay_payment_id);
            // TODO: You should now send response.razorpay_payment_id to your backend
            // to verify the payment signature and update the user's status in your database.
            
            // For this demo, we'll just upgrade the user on the frontend
            isPremium = true;
            updateUsageUI();
            closeSettingsModal();
        },
        "prefill": {
            "name": document.getElementById('profile-name').textContent,
            "email": document.getElementById('profile-email').textContent,
        },
        "theme": {
            "color": "#3b82f6"
        }
    };
    const rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){
            alert("Payment Failed. Error: " + response.error.description);
    });
    rzp1.open();
});


// --- Initializations ---
async function fetchAndDisplayUserInfo() {
    try {
        const response = await fetch('/get_user_info');
         if (!response.ok) {
            window.location.href = '/login.html'; 
            return;
        }
        const userData = await response.json();
       
        isAdmin = userData.isAdmin || false;
        isPremium = userData.isPremium || false;

        usageCounts = userData.usageCounts || { messages: 0, webSearches: 0 };
        
        updateUsageUI();

        let userInitial = 'U';
        let displayName = 'User';

        if(userData.name) {
            displayName = userData.name;
            userInitial = userData.name.charAt(0).toUpperCase();
        } else if (userData.email) {
            displayName = userData.email.split('@')[0];
            userInitial = userData.email.charAt(0).toUpperCase();
        }
        
        document.getElementById('profile-name').textContent = displayName;
        document.getElementById('sidebar-username').textContent = displayName;
        menuUsername.textContent = displayName;
        
        const avatarImg = document.getElementById('sidebar-user-avatar');
        if (avatarImg) {
            avatarImg.src = `https://placehold.co/32x32/E2E8F0/4A5568?text=${userInitial}`;
        }


        if(userData.email) {
             document.getElementById('profile-email').textContent = userData.email;
             if (userData.emailVerified) {
                 emailVerificationStatusText.textContent = 'Your email has been verified.';
                 emailVerificationStatusText.classList.remove('text-yellow-600', 'text-gray-500');
                 emailVerificationStatusText.classList.add('text-green-600');
                 verifyEmailBtn.textContent = 'Verified';
                 verifyEmailBtn.disabled = true;
                 verifyEmailBtn.classList.add('bg-gray-200', 'cursor-not-allowed', 'dark:bg-gray-600', 'dark:text-gray-400');
                 verifyEmailBtn.classList.remove('hover:bg-gray-100', 'dark:hover:bg-gray-700');
             } else {
                 emailVerificationStatusText.textContent = 'Your email is not verified.';
                 emailVerificationStatusText.classList.remove('text-green-600', 'text-gray-500');
                 emailVerificationStatusText.classList.add('text-yellow-600');
                 verifyEmailBtn.textContent = 'Verify';
                 verifyEmailBtn.disabled = false;
                 verifyEmailBtn.classList.remove('bg-gray-200', 'cursor-not-allowed', 'dark:bg-gray-600', 'dark:text-gray-400');
                 verifyEmailBtn.classList.add('hover:bg-gray-100', 'dark:hover:bg-gray-700');
             }
        } else {
             document.getElementById('profile-email').textContent = 'N/A';
             emailVerificationStatusText.textContent = 'Add an email to enable verification.';
             verifyEmailBtn.textContent = 'Verify';
             verifyEmailBtn.disabled = true;
             verifyEmailBtn.classList.add('bg-gray-200', 'cursor-not-allowed', 'dark:bg-gray-600', 'dark:text-gray-400');
             verifyEmailBtn.classList.remove('hover:bg-gray-100', 'dark:hover:bg-gray-700');
        }

    } catch (error) {
        console.error('Failed to fetch user info:', error);
        document.getElementById('profile-name').textContent = 'Error loading user';
        document.getElementById('profile-email').textContent = 'Please refresh';
        document.getElementById('sidebar-username').textContent = 'Error';
        const avatarImg = document.getElementById('sidebar-user-avatar');
        if (avatarImg) {
            avatarImg.src = `https://placehold.co/32x32/E2E8F0/4A5568?text=!`;
        }
    }
}

function initializeApp() {
    const savedTheme = localStorage.getItem('theme') || 'system';
    document.getElementById(`theme-${savedTheme}`).click();
    applyTheme(savedTheme);

    populateLanguages();
    applyLanguage(currentLang);
    loadChatsFromDB();
    
    fetchAndDisplayUserInfo();
    
    const handleLogout = async () => {
        try {
            const response = await fetch('/logout', { method: 'POST' });
            if(response.ok) {
                alert('You have been logged out.');
                window.location.href = '/login.html';
            } else {
                alert('Logout failed. Please try again.');
            }
        } catch (error) {
            console.error('Logout error:', error);
            alert('An error occurred during logout.');
        }
    };

    const handleLogoutAll = async () => {
        if (!confirm('This will log you out from all other devices and this one. Are you sure?')) {
            return;
        }
        try {
            const response = await fetch('/logout-all', { method: 'POST' });
            if(response.ok) {
                alert('Successfully logged out of all devices.');
                window.location.href = '/login.html';
            } else {
                alert('Failed to log out of all devices. Please try again.');
            }
        } catch (error) {
            console.error('Logout all error:', error);
            alert('An error occurred while logging out of all devices.');
        }
    };
    
    logoutBtn.addEventListener('click', handleLogoutAll);
    logoutMenuItem.addEventListener('click', (e) => {
        e.preventDefault();
        handleLogout();
    });
    
    verifyEmailBtn.addEventListener('click', async () => {
        verifyEmailBtn.disabled = true;
        verifyEmailBtn.textContent = 'Sending...';
        try {
            const response = await fetch('/send_verification_email', { method: 'POST' });
            if (response.ok) {
                alert('A new verification email has been sent to your address.');
                verifyEmailBtn.textContent = 'Resend';
            } else {
                const errorData = await response.json().catch(() => ({error: 'Server error'}));
                alert(`Failed to send email: ${errorData.error}`);
                verifyEmailBtn.textContent = 'Verify';
            }
        } catch (error) {
            console.error('Send verification email error:', error);
            alert('An error occurred while sending the verification email. This is a demo feature.');
            verifyEmailBtn.textContent = 'Verify';
        } finally {
            verifyEmailBtn.disabled = false;
        }
    });

    deleteAccountBtn.addEventListener('click', async () => {
        if(confirm('Are you sure you want to delete your account? This action is permanent and cannot be undone.')) {
             try {
                const response = await fetch('/delete_account', { method: 'DELETE' });
                if(response.ok) {
                    alert('Your account has been successfully deleted.');
                    window.location.href = '/login.html';
                } else {
                     const errorData = await response.json().catch(() => ({error: 'Server error'}));
                     alert(`Failed to delete account: ${errorData.error}`);
                }
            } catch (error) {
                 console.error('Delete account error:', error);
                 alert('An error occurred while deleting your account.');
            }
        }
    });
}

initializeApp();
