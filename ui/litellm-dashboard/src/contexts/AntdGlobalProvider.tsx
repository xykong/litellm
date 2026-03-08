"use client";

import { setNotificationInstance } from "@/components/molecules/notifications_manager";
import "@/i18n/config";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { notification } from "antd";
import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

export default function AntdGlobalProvider({ children }: { children: React.ReactNode }) {
  const [api, contextHolder] = notification.useNotification();
  const initialized = useRef(false);
  const { i18n } = useTranslation();

  useEffect(() => {
    if (!initialized.current) {
      setNotificationInstance(api);
      initialized.current = true;
    }
  }, [api]);

  const antdLocale = i18n.language?.startsWith("zh") ? zhCN : enUS;

  return (
    <ConfigProvider locale={antdLocale}>
      {contextHolder}
      {children}
    </ConfigProvider>
  );
}
