"use client";
import { Select } from "antd";
import React from "react";
import { useTranslation } from "react-i18next";
import "@/i18n/config";

const { Option } = Select;

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "zh-CN", label: "简体中文" },
];

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const currentLang = i18n.language?.startsWith("zh") ? "zh-CN" : "en";

  return (
    <Select
      value={currentLang}
      onChange={(value: string) => i18n.changeLanguage(value)}
      size="small"
      style={{ width: 110 }}
      variant="borderless"
    >
      {LANGUAGES.map((lang) => (
        <Option key={lang.code} value={lang.code}>
          {lang.label}
        </Option>
      ))}
    </Select>
  );
}
