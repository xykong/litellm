import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import enCommon from "../locales/en/common.json";
import enNav from "../locales/en/nav.json";
import zhCNCommon from "../locales/zh-CN/common.json";
import zhCNNav from "../locales/zh-CN/nav.json";

const resources = {
  en: {
    nav: enNav,
    common: enCommon,
  },
  "zh-CN": {
    nav: zhCNNav,
    common: zhCNCommon,
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    defaultNS: "common",
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "litellm-language",
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
