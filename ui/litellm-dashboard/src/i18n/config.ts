import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

// Import translation resources
// Note: In a full implementation, these would be imported from separate JSON files
// For this proof of concept, we're using inline resources to demonstrate the architecture

const resources = {
  en: {
    translation: {
      language: {
        name: "English",
        switchTo: "Switch to English",
      },
      navigation: {
        usage: "Usage",
        keys: "Keys",
        teams: "Teams",
        users: "Users",
        models: "Models",
        logs: "Logs",
        settings: "Settings",
      },
      common: {
        search: "Search",
        filter: "Filter",
        export: "Export",
        loading: "Loading...",
        noData: "No data available",
        cancel: "Cancel",
        save: "Save",
        delete: "Delete",
        edit: "Edit",
        create: "Create",
      },
    },
  },
  "zh-CN": {
    translation: {
      language: {
        name: "简体中文",
        switchTo: "切换到中文",
      },
      navigation: {
        usage: "用量统计",
        keys: "密钥管理",
        teams: "团队管理",
        users: "用户管理",
        models: "模型管理",
        logs: "日志查询",
        settings: "系统设置",
      },
      common: {
        search: "搜索",
        filter: "筛选",
        export: "导出",
        loading: "加载中...",
        noData: "暂无数据",
        cancel: "取消",
        save: "保存",
        delete: "删除",
        edit: "编辑",
        create: "创建",
      },
    },
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    defaultNS: "translation",
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
