"use client";

import UIThemeSettings from "@/components/ui_theme_settings";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const UIThemePage = () => {
  const { userId, userRole, accessToken } = useAuthorized();

  return <UIThemeSettings userID={userId} userRole={userRole} accessToken={accessToken} />;
};

export default withAdminAuth(UIThemePage);
