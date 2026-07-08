"use client";

// Lightweight i18n: a dictionary + React context + a `t()` helper with {param}
// interpolation. Deliberately dependency-free — 4 locales and ~40 strings don't
// justify a full i18n framework (anti-overengineering).

import * as React from "react";

export type Lang = "en" | "hi" | "fr" | "de";

export const LANGUAGES: { code: Lang; label: string; flag: string }[] = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "hi", label: "हिन्दी", flag: "🇮🇳" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
];

type Dict = Record<string, string>;

const en: Dict = {
  "app.tagline": "Payments, refunded right",
  "page.title": "Admin Refund",
  "page.subtitle": "Transaction details and refund controls.",
  "page.viewAs": "View as (demo)",
  "role.admin": "Admin — MER-900 (can refund)",
  "role.support": "Support — no refund permission",
  "role.otherMerchant": "Admin — MER-111 (wrong scope)",
  "common.loading": "Loading…",
  "common.close": "Close",
  "txn.user": "User",
  "txn.merchant": "Merchant",
  "txn.amount": "Amount",
  "txn.paymentMethod": "Payment method",
  "txn.remaining": "Remaining refundable",
  "refund.issue": "Issue refund",
  "refund.notAllowed":
    "Refund not allowed (check status, currency, permission, or remaining amount)",
  "history.title": "Refund history",
  "history.empty": "No refunds yet.",
  "modal.title": "Refund {id}",
  "modal.remaining": "Remaining refundable",
  "modal.amount": "Amount ({currency})",
  "modal.reason": "Reason",
  "modal.amountPlaceholder": "Up to {remaining}",
  "modal.reasonPlaceholder": "Why is this being refunded?",
  "modal.confirm": "Confirm refund",
  "modal.processing": "Processing…",
  "modal.successTitle": "Refund created",
  "modal.refundId": "Refund ID",
  "modal.status": "Status",
  "validation.amountInvalid": "Enter a valid amount",
  "validation.amountInteger": "Amount must be a whole number",
  "validation.amountPositive": "Amount must be greater than 0",
  "validation.amountExceeds": "Amount cannot exceed remaining {remaining}",
  "validation.reasonRequired": "A reason is required",
  "error.generic": "Something went wrong. Please try again.",
  "nav.section": "Menu",
  "nav.overview": "Overview",
  "nav.details": "Transaction details",
  "nav.eligibility": "Refund eligibility",
  "nav.initiate": "Initiate refund",
  "nav.status": "Refund status",
  "nav.history": "Refund history",
  "chart.title": "Daily transactions",
  "chart.subtitle": "Last 14 days",
  "chart.count": "Transactions",
  "chart.amount": "Amount (₹)",
  "chart.days": "{n} days",
  "statusChart.title": "Refund status breakdown",
  "statusChart.empty": "No refunds to chart yet.",
  "eligibility.eligible": "Eligible for refund",
  "eligibility.notEligible": "Not eligible for refund",
  "eligibility.status": "Transaction succeeded",
  "eligibility.currency": "Currency is INR",
  "eligibility.remaining": "Refundable amount remaining",
  "eligibility.permission": "You have refund permission",
  "initiate.desc": "Start a full or partial refund for this transaction.",
  "status.totalRefunded": "Total refunded",
  "status.remaining": "Remaining",
  "status.count": "Refunds",
  "status.none": "No refunds yet.",
  "lang.label": "Language",
  "theme.label": "Theme",
  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.system": "System",
  "profile.label": "Account",
  "profile.role": "Signed in as Admin",
  "profile.settings": "Settings",
  "profile.signout": "Sign out",
  "footer.rights": "FinPay Inc. All rights reserved.",
  "footer.secure": "Secured & audited",
};

const hi: Dict = {
  "app.tagline": "भुगतान, सही तरीके से वापस",
  "page.title": "एडमिन रिफंड",
  "page.subtitle": "लेन-देन का विवरण और रिफंड नियंत्रण।",
  "page.viewAs": "इस रूप में देखें (डेमो)",
  "role.admin": "एडमिन — MER-900 (रिफंड कर सकते हैं)",
  "role.support": "सपोर्ट — रिफंड अनुमति नहीं",
  "role.otherMerchant": "एडमिन — MER-111 (गलत स्कोप)",
  "common.loading": "लोड हो रहा है…",
  "common.close": "बंद करें",
  "txn.user": "उपयोगकर्ता",
  "txn.merchant": "व्यापारी",
  "txn.amount": "राशि",
  "txn.paymentMethod": "भुगतान का तरीका",
  "txn.remaining": "शेष वापसी योग्य",
  "refund.issue": "रिफंड जारी करें",
  "refund.notAllowed":
    "रिफंड की अनुमति नहीं (स्थिति, मुद्रा, अनुमति या शेष राशि जांचें)",
  "history.title": "रिफंड इतिहास",
  "history.empty": "अभी तक कोई रिफंड नहीं।",
  "modal.title": "रिफंड {id}",
  "modal.remaining": "शेष वापसी योग्य",
  "modal.amount": "राशि ({currency})",
  "modal.reason": "कारण",
  "modal.amountPlaceholder": "{remaining} तक",
  "modal.reasonPlaceholder": "यह रिफंड क्यों किया जा रहा है?",
  "modal.confirm": "रिफंड की पुष्टि करें",
  "modal.processing": "प्रोसेस हो रहा है…",
  "modal.successTitle": "रिफंड बन गया",
  "modal.refundId": "रिफंड आईडी",
  "modal.status": "स्थिति",
  "validation.amountInvalid": "मान्य राशि दर्ज करें",
  "validation.amountInteger": "राशि पूर्ण संख्या होनी चाहिए",
  "validation.amountPositive": "राशि 0 से अधिक होनी चाहिए",
  "validation.amountExceeds": "राशि शेष {remaining} से अधिक नहीं हो सकती",
  "validation.reasonRequired": "कारण आवश्यक है",
  "error.generic": "कुछ गलत हुआ। कृपया पुनः प्रयास करें।",
  "nav.section": "मेन्यू",
  "nav.overview": "अवलोकन",
  "nav.details": "लेन-देन विवरण",
  "nav.eligibility": "रिफंड पात्रता",
  "nav.initiate": "रिफंड शुरू करें",
  "nav.status": "रिफंड स्थिति",
  "nav.history": "रिफंड इतिहास",
  "chart.title": "दैनिक लेन-देन",
  "chart.subtitle": "पिछले 14 दिन",
  "chart.count": "लेन-देन",
  "chart.amount": "राशि (₹)",
  "chart.days": "{n} दिन",
  "statusChart.title": "रिफंड स्थिति विवरण",
  "statusChart.empty": "चार्ट के लिए अभी कोई रिफंड नहीं।",
  "eligibility.eligible": "रिफंड के लिए पात्र",
  "eligibility.notEligible": "रिफंड के लिए अपात्र",
  "eligibility.status": "लेन-देन सफल हुआ",
  "eligibility.currency": "मुद्रा INR है",
  "eligibility.remaining": "शेष वापसी योग्य राशि",
  "eligibility.permission": "आपके पास रिफंड अनुमति है",
  "initiate.desc": "इस लेन-देन के लिए पूर्ण या आंशिक रिफंड शुरू करें।",
  "status.totalRefunded": "कुल रिफंड",
  "status.remaining": "शेष",
  "status.count": "रिफंड",
  "status.none": "अभी तक कोई रिफंड नहीं।",
  "lang.label": "भाषा",
  "theme.label": "थीम",
  "theme.light": "लाइट",
  "theme.dark": "डार्क",
  "theme.system": "सिस्टम",
  "profile.label": "खाता",
  "profile.role": "एडमिन के रूप में साइन इन",
  "profile.settings": "सेटिंग्स",
  "profile.signout": "साइन आउट",
  "footer.rights": "FinPay Inc. सर्वाधिकार सुरक्षित।",
  "footer.secure": "सुरक्षित और ऑडिटेड",
};

const fr: Dict = {
  "app.tagline": "Les paiements, remboursés comme il faut",
  "page.title": "Remboursement Admin",
  "page.subtitle": "Détails de la transaction et contrôles de remboursement.",
  "page.viewAs": "Voir en tant que (démo)",
  "role.admin": "Admin — MER-900 (peut rembourser)",
  "role.support": "Support — sans autorisation de remboursement",
  "role.otherMerchant": "Admin — MER-111 (mauvaise portée)",
  "common.loading": "Chargement…",
  "common.close": "Fermer",
  "txn.user": "Utilisateur",
  "txn.merchant": "Marchand",
  "txn.amount": "Montant",
  "txn.paymentMethod": "Moyen de paiement",
  "txn.remaining": "Remboursable restant",
  "refund.issue": "Émettre un remboursement",
  "refund.notAllowed":
    "Remboursement non autorisé (vérifiez le statut, la devise, l'autorisation ou le montant restant)",
  "history.title": "Historique des remboursements",
  "history.empty": "Aucun remboursement pour le moment.",
  "modal.title": "Rembourser {id}",
  "modal.remaining": "Remboursable restant",
  "modal.amount": "Montant ({currency})",
  "modal.reason": "Motif",
  "modal.amountPlaceholder": "Jusqu'à {remaining}",
  "modal.reasonPlaceholder": "Pourquoi ce remboursement ?",
  "modal.confirm": "Confirmer le remboursement",
  "modal.processing": "Traitement…",
  "modal.successTitle": "Remboursement créé",
  "modal.refundId": "ID de remboursement",
  "modal.status": "Statut",
  "validation.amountInvalid": "Saisissez un montant valide",
  "validation.amountInteger": "Le montant doit être un nombre entier",
  "validation.amountPositive": "Le montant doit être supérieur à 0",
  "validation.amountExceeds": "Le montant ne peut pas dépasser le reste de {remaining}",
  "validation.reasonRequired": "Un motif est requis",
  "error.generic": "Une erreur est survenue. Veuillez réessayer.",
  "nav.section": "Menu",
  "nav.overview": "Vue d'ensemble",
  "nav.details": "Détails de la transaction",
  "nav.eligibility": "Éligibilité au remboursement",
  "nav.initiate": "Lancer un remboursement",
  "nav.status": "Statut du remboursement",
  "nav.history": "Historique des remboursements",
  "chart.title": "Transactions quotidiennes",
  "chart.subtitle": "14 derniers jours",
  "chart.count": "Transactions",
  "chart.amount": "Montant (₹)",
  "chart.days": "{n} jours",
  "statusChart.title": "Répartition des statuts de remboursement",
  "statusChart.empty": "Aucun remboursement à afficher pour le moment.",
  "eligibility.eligible": "Éligible au remboursement",
  "eligibility.notEligible": "Non éligible au remboursement",
  "eligibility.status": "Transaction réussie",
  "eligibility.currency": "La devise est INR",
  "eligibility.remaining": "Montant remboursable restant",
  "eligibility.permission": "Vous avez l'autorisation de remboursement",
  "initiate.desc": "Lancez un remboursement total ou partiel pour cette transaction.",
  "status.totalRefunded": "Total remboursé",
  "status.remaining": "Restant",
  "status.count": "Remboursements",
  "status.none": "Aucun remboursement pour le moment.",
  "lang.label": "Langue",
  "theme.label": "Thème",
  "theme.light": "Clair",
  "theme.dark": "Sombre",
  "theme.system": "Système",
  "profile.label": "Compte",
  "profile.role": "Connecté en tant qu'Admin",
  "profile.settings": "Paramètres",
  "profile.signout": "Se déconnecter",
  "footer.rights": "FinPay Inc. Tous droits réservés.",
  "footer.secure": "Sécurisé et audité",
};

const de: Dict = {
  "app.tagline": "Zahlungen, richtig erstattet",
  "page.title": "Admin-Rückerstattung",
  "page.subtitle": "Transaktionsdetails und Rückerstattungssteuerung.",
  "page.viewAs": "Anzeigen als (Demo)",
  "role.admin": "Admin — MER-900 (kann erstatten)",
  "role.support": "Support — keine Erstattungsberechtigung",
  "role.otherMerchant": "Admin — MER-111 (falscher Bereich)",
  "common.loading": "Wird geladen…",
  "common.close": "Schließen",
  "txn.user": "Benutzer",
  "txn.merchant": "Händler",
  "txn.amount": "Betrag",
  "txn.paymentMethod": "Zahlungsmethode",
  "txn.remaining": "Erstattbarer Restbetrag",
  "refund.issue": "Rückerstattung veranlassen",
  "refund.notAllowed":
    "Rückerstattung nicht erlaubt (Status, Währung, Berechtigung oder Restbetrag prüfen)",
  "history.title": "Rückerstattungsverlauf",
  "history.empty": "Noch keine Rückerstattungen.",
  "modal.title": "Rückerstattung {id}",
  "modal.remaining": "Erstattbarer Restbetrag",
  "modal.amount": "Betrag ({currency})",
  "modal.reason": "Grund",
  "modal.amountPlaceholder": "Bis zu {remaining}",
  "modal.reasonPlaceholder": "Warum wird dies erstattet?",
  "modal.confirm": "Rückerstattung bestätigen",
  "modal.processing": "Wird verarbeitet…",
  "modal.successTitle": "Rückerstattung erstellt",
  "modal.refundId": "Rückerstattungs-ID",
  "modal.status": "Status",
  "validation.amountInvalid": "Gültigen Betrag eingeben",
  "validation.amountInteger": "Betrag muss eine ganze Zahl sein",
  "validation.amountPositive": "Betrag muss größer als 0 sein",
  "validation.amountExceeds": "Betrag darf den Rest von {remaining} nicht überschreiten",
  "validation.reasonRequired": "Ein Grund ist erforderlich",
  "error.generic": "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
  "nav.section": "Menü",
  "nav.overview": "Übersicht",
  "nav.details": "Transaktionsdetails",
  "nav.eligibility": "Rückerstattungsberechtigung",
  "nav.initiate": "Rückerstattung starten",
  "nav.status": "Rückerstattungsstatus",
  "nav.history": "Rückerstattungsverlauf",
  "chart.title": "Tägliche Transaktionen",
  "chart.subtitle": "Letzte 14 Tage",
  "chart.count": "Transaktionen",
  "chart.amount": "Betrag (₹)",
  "chart.days": "{n} Tage",
  "statusChart.title": "Aufschlüsselung der Rückerstattungsstatus",
  "statusChart.empty": "Noch keine Rückerstattungen zum Anzeigen.",
  "eligibility.eligible": "Für Rückerstattung berechtigt",
  "eligibility.notEligible": "Nicht für Rückerstattung berechtigt",
  "eligibility.status": "Transaktion erfolgreich",
  "eligibility.currency": "Währung ist INR",
  "eligibility.remaining": "Erstattbarer Restbetrag vorhanden",
  "eligibility.permission": "Sie haben die Rückerstattungsberechtigung",
  "initiate.desc": "Starten Sie eine vollständige oder teilweise Rückerstattung für diese Transaktion.",
  "status.totalRefunded": "Insgesamt erstattet",
  "status.remaining": "Verbleibend",
  "status.count": "Rückerstattungen",
  "status.none": "Noch keine Rückerstattungen.",
  "lang.label": "Sprache",
  "theme.label": "Design",
  "theme.light": "Hell",
  "theme.dark": "Dunkel",
  "theme.system": "System",
  "profile.label": "Konto",
  "profile.role": "Angemeldet als Admin",
  "profile.settings": "Einstellungen",
  "profile.signout": "Abmelden",
  "footer.rights": "FinPay Inc. Alle Rechte vorbehalten.",
  "footer.secure": "Gesichert & auditiert",
};

const DICTS: Record<Lang, Dict> = { en, hi, fr, de };

type I18nContextValue = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

const I18nContext = React.createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "finpay-lang";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = React.useState<Lang>("en");

  // Restore the saved language on mount (client only).
  React.useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY) as Lang | null;
    if (saved && saved in DICTS) setLangState(saved);
  }, []);

  const setLang = React.useCallback((l: Lang) => {
    setLangState(l);
    window.localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.setAttribute("lang", l);
  }, []);

  const t = React.useCallback(
    (key: string, params?: Record<string, string | number>) => {
      const dict = DICTS[lang];
      let str = dict[key] ?? en[key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          str = str.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
        }
      }
      return str;
    },
    [lang]
  );

  const value = React.useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const ctx = React.useContext(I18nContext);
  if (!ctx) throw new Error("useTranslation must be used within I18nProvider");
  return ctx;
}
