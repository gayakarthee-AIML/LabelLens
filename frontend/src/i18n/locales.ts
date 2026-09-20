// Lightweight i18n architecture — no hardcoded UI strings scattered through
// components (brief section 12). This is intentionally dependency-free
// (no react-i18next) since this environment can't npm-install to verify one;
// the pattern (a flat key -> string dictionary per language, looked up
// through useTranslation()) is the same shape react-i18next uses, so
// swapping in that library later is a drop-in change, not a rewrite.
//
// Coverage note: translation is wired through the navigation shell, login,
// settings, and the New Inspection flow end-to-end (mode selector, capture,
// e-commerce listing input, results, human verification) plus the shared
// DeclarationTable / RuleResultList / ComplianceStamp components used
// elsewhere. Secondary screens (Dashboard, Analytics, Enforcement
// Monitoring, Rule Management, User Management, Search, Reports, Evidence
// Viewer) still have literal English JSX text — extending them follows the
// same `t("key")` pattern already used throughout the files above.
// Rule/declaration *content* itself (rule names, findings, detected label
// text) comes from the backend and is not translated — real localization of
// that would need backend-side i18n, which is a larger, separate change.
export type SupportedLanguage = "en" | "hi";

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  hi: "हिन्दी (Hindi)"
};

const en = {
  "app.name": "LabelLens",
  "app.tagline": "Legal Metrology Compliance System",
  "nav.dashboard": "Dashboard",
  "nav.newInspection": "New Inspection",
  "nav.fontSizeCheck": "Font Size Check",
  "nav.search": "Search & Repository",
  "nav.evidence": "Evidence Viewer",
  "nav.reports": "Reports",
  "nav.enforcement": "Enforcement Monitoring",
  "nav.analytics": "Analytics",
  "nav.rules": "Rule Management",
  "nav.users": "User Management",
  "nav.offlineQueue": "Offline Queue",
  "nav.settings": "Settings",
  "login.selectAccessType": "Select your access type",
  "login.continue": "Continue",
  "login.secureLogin": "Secure Login",
  "settings.language": "Language",
  "settings.title": "Settings",

  "inspection.mode.title": "Inspection Mode",
  "inspection.mode.package.label": "Scan Package",
  "inspection.mode.package.blurb": "Capture all sides of a physical package.",
  "inspection.mode.label.label": "Scan Label",
  "inspection.mode.label.blurb": "Capture just the label panel(s).",
  "inspection.mode.ecommerce.label": "E-Commerce Listing",
  "inspection.mode.ecommerce.blurb": "Analyze an online product listing by URL.",
  "inspection.details.title": "Product Details",
  "inspection.details.productName": "Product / common name",
  "inspection.details.brand": "Brand",
  "inspection.details.category": "Category",
  "inspection.details.continueCamera": "Continue to Camera",
  "inspection.details.continueListing": "Continue to Listing URL",
  "inspection.capture.title.package": "Multi-Angle Capture",
  "inspection.capture.title.label": "Label Capture",
  "inspection.capture.spinToggleOn": "🔄 Use Spin-Scan (video) instead",
  "inspection.capture.spinToggleOff": "↺ Switch to individual photos",
  "inspection.capture.spinHint": "Rotate the product in front of the camera instead of taking each angle separately — sharp, distinct frames are kept automatically.",
  "inspection.capture.runAnalysis": "Run OCR & Compliance Analysis",
  "inspection.ecommerce.title": "🌐 E-Commerce Listing",
  "inspection.ecommerce.explain": "LabelLens will fetch the listing page, extract product information (page text, JSON-LD structured data, price/MRP, and product images), run the existing PaddleOCR pipeline on any product/label images, and use AI only to help understand unstructured content where needed. The same deterministic Legal Metrology rule engine used for physical inspections makes every compliance decision — the AI never does.",
  "inspection.ecommerce.urlLabel": "Product Listing URL",
  "inspection.ecommerce.analyzeButton": "Analyze Listing",
  "inspection.processing.title": "Analyzing",
  "inspection.processing.ecommerce": "Fetching the listing, extracting structured product data and images, running OCR and AI-assisted extraction, and evaluating against the Legal Metrology rule engine…",
  "inspection.processing.photo": "Running image preprocessing, OCR, declaration extraction, and rule evaluation…",
  "inspection.saved.title": "Saved Offline",
  "inspection.saved.goToQueue": "Go to Offline Queue",
  "inspection.result.title": "Inspection Result",
  "inspection.result.listingSource": "🌐 Listing Source",
  "inspection.result.declarations": "Mandatory Declarations",
  "inspection.result.barcode": "Barcode / QR Verification",
  "inspection.result.barcode.notApplicable": "Barcode/QR scanning applies only to electronic products — not run for this category.",
  "inspection.result.ruleCompliance": "Rule Compliance",
  "inspection.result.humanVerification": "Human Verification",
  "inspection.result.humanVerification.blurb": "Review the AI findings above. Add notes, then finalize. Any manual edits are recorded in the audit log server-side.",
  "inspection.result.notes": "Inspector notes",
  "inspection.result.confirmSave": "Confirm & Save Inspection",

  "declaration.table.empty": "No declarations extracted yet. Run analysis to populate this section.",
  "declaration.table.header.declaration": "Declaration",
  "declaration.table.header.detectedText": "Detected Text",
  "declaration.table.header.source": "Source",
  "declaration.table.header.confidence": "Confidence",
  "declaration.table.header.textHeight": "Text Height",
  "declaration.table.header.readability": "Readability",
  "declaration.table.header.status": "Status",
  "declaration.table.notDetected": "Not detected",
  "declaration.source.webpage": "Listing text",
  "declaration.source.aiExtraction": "AI Extracted",

  "rule.severity": "Severity",
  "rule.confidence": "Confidence",
  "rule.source": "Source",
  "rule.recommendation": "Recommendation",
  "rule.noResults": "No rule evaluations yet.",

  "status.compliant": "Compliant",
  "status.nonCompliant": "Non-Compliant",
  "status.reviewRequired": "Review Required",
  "status.draft": "Draft"
};

const hi: Record<keyof typeof en, string> = {
  "app.name": "लेबल लेंस",
  "app.tagline": "लीगल मेट्रोलॉजी अनुपालन प्रणाली",
  "nav.dashboard": "डैशबोर्ड",
  "nav.newInspection": "नया निरीक्षण",
  "nav.fontSizeCheck": "फ़ॉन्ट आकार जाँच",
  "nav.search": "खोज और भंडार",
  "nav.evidence": "साक्ष्य दर्शक",
  "nav.reports": "रिपोर्ट",
  "nav.enforcement": "प्रवर्तन निगरानी",
  "nav.analytics": "विश्लेषण",
  "nav.rules": "नियम प्रबंधन",
  "nav.users": "उपयोगकर्ता प्रबंधन",
  "nav.offlineQueue": "ऑफ़लाइन कतार",
  "nav.settings": "सेटिंग्स",
  "login.selectAccessType": "अपना प्रवेश प्रकार चुनें",
  "login.continue": "जारी रखें",
  "login.secureLogin": "सुरक्षित लॉगिन",
  "settings.language": "भाषा",
  "settings.title": "सेटिंग्स",

  "inspection.mode.title": "निरीक्षण मोड",
  "inspection.mode.package.label": "पैकेज स्कैन करें",
  "inspection.mode.package.blurb": "भौतिक पैकेज के सभी किनारों को कैप्चर करें।",
  "inspection.mode.label.label": "लेबल स्कैन करें",
  "inspection.mode.label.blurb": "केवल लेबल पैनल कैप्चर करें।",
  "inspection.mode.ecommerce.label": "ई-कॉमर्स लिस्टिंग",
  "inspection.mode.ecommerce.blurb": "URL के ज़रिए ऑनलाइन उत्पाद लिस्टिंग का विश्लेषण करें।",
  "inspection.details.title": "उत्पाद विवरण",
  "inspection.details.productName": "उत्पाद / सामान्य नाम",
  "inspection.details.brand": "ब्रांड",
  "inspection.details.category": "श्रेणी",
  "inspection.details.continueCamera": "कैमरे पर जारी रखें",
  "inspection.details.continueListing": "लिस्टिंग URL पर जारी रखें",
  "inspection.capture.title.package": "मल्टी-एंगल कैप्चर",
  "inspection.capture.title.label": "लेबल कैप्चर",
  "inspection.capture.spinToggleOn": "🔄 इसके बजाय स्पिन-स्कैन (वीडियो) उपयोग करें",
  "inspection.capture.spinToggleOff": "↺ अलग-अलग फ़ोटो पर स्विच करें",
  "inspection.capture.spinHint": "प्रत्येक कोण अलग से लेने के बजाय उत्पाद को कैमरे के सामने घुमाएँ — स्पष्ट, अलग-अलग फ़्रेम स्वतः रखे जाते हैं।",
  "inspection.capture.runAnalysis": "OCR और अनुपालन विश्लेषण चलाएँ",
  "inspection.ecommerce.title": "🌐 ई-कॉमर्स लिस्टिंग",
  "inspection.ecommerce.explain": "लेबललेंस लिस्टिंग पृष्ठ प्राप्त करेगा, उत्पाद जानकारी (पृष्ठ पाठ, JSON-LD संरचित डेटा, मूल्य/MRP, और उत्पाद छवियाँ) निकालेगा, किसी भी उत्पाद/लेबल छवि पर मौजूदा PaddleOCR पाइपलाइन चलाएगा, और आवश्यकता पड़ने पर असंरचित सामग्री को समझने में सहायता के लिए ही AI का उपयोग करेगा। भौतिक निरीक्षणों के लिए उपयोग किया जाने वाला वही नियतात्मक लीगल मेट्रोलॉजी नियम इंजन हर अनुपालन निर्णय लेता है — AI कभी नहीं।",
  "inspection.ecommerce.urlLabel": "उत्पाद लिस्टिंग URL",
  "inspection.ecommerce.analyzeButton": "लिस्टिंग का विश्लेषण करें",
  "inspection.processing.title": "विश्लेषण जारी है",
  "inspection.processing.ecommerce": "लिस्टिंग प्राप्त की जा रही है, संरचित उत्पाद डेटा और छवियाँ निकाली जा रही हैं, OCR और AI-सहायित निष्कर्षण चलाया जा रहा है, और लीगल मेट्रोलॉजी नियम इंजन के विरुद्ध मूल्यांकन किया जा रहा है…",
  "inspection.processing.photo": "छवि प्रीप्रोसेसिंग, OCR, घोषणा निष्कर्षण, और नियम मूल्यांकन चलाया जा रहा है…",
  "inspection.saved.title": "ऑफ़लाइन सहेजा गया",
  "inspection.saved.goToQueue": "ऑफ़लाइन कतार पर जाएँ",
  "inspection.result.title": "निरीक्षण परिणाम",
  "inspection.result.listingSource": "🌐 लिस्टिंग स्रोत",
  "inspection.result.declarations": "अनिवार्य घोषणाएँ",
  "inspection.result.barcode": "बारकोड / QR सत्यापन",
  "inspection.result.barcode.notApplicable": "बारकोड/QR स्कैनिंग केवल इलेक्ट्रॉनिक उत्पादों पर लागू होती है — इस श्रेणी के लिए नहीं चलाई जाती।",
  "inspection.result.ruleCompliance": "नियम अनुपालन",
  "inspection.result.humanVerification": "मानव सत्यापन",
  "inspection.result.humanVerification.blurb": "ऊपर दिए गए AI निष्कर्षों की समीक्षा करें। टिप्पणियाँ जोड़ें, फिर अंतिम रूप दें। किसी भी मैन्युअल संपादन को सर्वर-साइड ऑडिट लॉग में दर्ज किया जाता है।",
  "inspection.result.notes": "निरीक्षक टिप्पणियाँ",
  "inspection.result.confirmSave": "पुष्टि करें और निरीक्षण सहेजें",

  "declaration.table.empty": "अभी तक कोई घोषणा नहीं निकाली गई। इस अनुभाग को भरने के लिए विश्लेषण चलाएँ।",
  "declaration.table.header.declaration": "घोषणा",
  "declaration.table.header.detectedText": "पहचाना गया पाठ",
  "declaration.table.header.source": "स्रोत",
  "declaration.table.header.confidence": "विश्वास स्तर",
  "declaration.table.header.textHeight": "पाठ ऊँचाई",
  "declaration.table.header.readability": "पठनीयता",
  "declaration.table.header.status": "स्थिति",
  "declaration.table.notDetected": "नहीं मिला",
  "declaration.source.webpage": "लिस्टिंग पाठ",
  "declaration.source.aiExtraction": "AI द्वारा निकाला गया",

  "rule.severity": "गंभीरता",
  "rule.confidence": "विश्वास स्तर",
  "rule.source": "स्रोत",
  "rule.recommendation": "सिफ़ारिश",
  "rule.noResults": "अभी तक कोई नियम मूल्यांकन नहीं हुआ।",

  "status.compliant": "अनुपालक",
  "status.nonCompliant": "गैर-अनुपालक",
  "status.reviewRequired": "समीक्षा आवश्यक",
  "status.draft": "प्रारूप"
};

export type TranslationKey = keyof typeof en;

export const TRANSLATIONS: Record<SupportedLanguage, Record<TranslationKey, string>> = { en, hi };
